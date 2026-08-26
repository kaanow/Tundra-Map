"""Tundra-Map print worker.

Keeps a single Postgres connection open, LISTENs on `print_jobs`, and prints
each queued job on the Brother QL-810W. Falls back to polling every 30s in
case a NOTIFY is missed (e.g., DB reconnect).
"""
from __future__ import annotations
import logging
import os
import select
import signal
import sys
import time
from datetime import datetime, timezone
from typing import Optional

import psycopg

from render import render_label

log = logging.getLogger("tundra-print")
logging.basicConfig(
    level=os.environ.get("LOG_LEVEL", "INFO"),
    format="%(asctime)s %(levelname)s %(message)s",
)

DATABASE_URL   = os.environ["DATABASE_URL"]
PUBLIC_BASE    = os.environ.get("PUBLIC_BASE_URL", "http://localhost:8000").rstrip("/")
SHARED_SECRET  = os.environ.get("SHARED_SECRET", "")
PRINTER_MODEL  = os.environ.get("PRINTER_MODEL", "QL-810W")
PRINTER_BACKEND = os.environ.get("PRINTER_BACKEND", "pyusb")  # "file" writes PNGs instead
PRINTER_IDENT  = os.environ.get("PRINTER_IDENT", "usb://0x04f9:0x209c")
LABEL_SIZE     = os.environ.get("LABEL_SIZE", "29x90")
FILE_BACKEND_DIR = os.environ.get("FILE_BACKEND_DIR", "/tmp/tundra-labels")
POLL_FALLBACK_SEC = 30

_shutdown = False


def _handle_signal(sig, frame):
    global _shutdown
    log.info("received %s; shutting down", sig)
    _shutdown = True


signal.signal(signal.SIGTERM, _handle_signal)
signal.signal(signal.SIGINT, _handle_signal)


def item_url(item_id: str) -> str:
    if SHARED_SECRET:
        return f"{PUBLIC_BASE}/i/{item_id}?k={SHARED_SECRET}"
    return f"{PUBLIC_BASE}/i/{item_id}"


def _print_to_file(img, item_id: str) -> None:
    """Dry-run mode: save the rendered label to disk instead of printing."""
    import os
    os.makedirs(FILE_BACKEND_DIR, exist_ok=True)
    ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    dest = os.path.join(FILE_BACKEND_DIR, f"{ts}_{item_id}.png")
    img.save(dest)
    log.info("wrote label to %s (file backend; no printer)", dest)


def print_label(name: str, added_at: datetime, item_id: str) -> None:
    img = render_label(url=item_url(item_id), name=name, added_at=added_at, size=LABEL_SIZE)
    if PRINTER_BACKEND == "file":
        _print_to_file(img, item_id)
        return
    # Import brother_ql lazily so the worker can start on machines that lack
    # pyusb / libusb (e.g., the dev box) as long as they're only using file mode.
    from brother_ql.backends.helpers import send
    from brother_ql.conversion import convert
    from brother_ql.raster import BrotherQLRaster

    qlr = BrotherQLRaster(PRINTER_MODEL)
    qlr.exception_on_warning = True
    instructions = convert(
        qlr=qlr,
        images=[img],
        label=LABEL_SIZE,
        rotate="0",
        threshold=70.0,
        dither=False,
        compress=False,
        red=False,
        dpi_600=False,
        hq=True,
        cut=True,
    )
    send(instructions=instructions, printer_identifier=PRINTER_IDENT, backend_identifier=PRINTER_BACKEND, blocking=True)


def claim_and_print_one(conn: psycopg.Connection) -> bool:
    """Claim the oldest pending job, print it, mark done. Returns True if one was processed."""
    with conn.transaction():
        cur = conn.execute(
            """
            SELECT pj.id, pj.item_id, pj.attempts, i.name, i.added_at
            FROM print_jobs pj
            JOIN items i ON i.id = pj.item_id
            WHERE pj.printed_at IS NULL AND pj.error IS NULL
            ORDER BY pj.id
            FOR UPDATE SKIP LOCKED
            LIMIT 1
            """
        )
        row = cur.fetchone()
        if not row:
            return False
        job_id, item_id, attempts, name, added_at = row
        log.info("printing job=%s item=%s name=%r", job_id, item_id, name)
        try:
            print_label(name=name, added_at=added_at, item_id=item_id)
        except Exception as e:  # noqa: BLE001 — surface any printer error into the DB
            log.exception("print failed for job %s", job_id)
            conn.execute(
                "UPDATE print_jobs SET attempts = attempts + 1, error = %s WHERE id = %s",
                (f"{type(e).__name__}: {e}"[:500], job_id),
            )
            return True
        conn.execute(
            "UPDATE print_jobs SET printed_at = now(), attempts = attempts + 1 WHERE id = %s",
            (job_id,),
        )
    return True


def drain(conn: psycopg.Connection) -> None:
    while claim_and_print_one(conn):
        if _shutdown:
            return


def main() -> int:
    log.info("starting; printer=%s backend=%s ident=%s size=%s",
             PRINTER_MODEL, PRINTER_BACKEND, PRINTER_IDENT, LABEL_SIZE)
    while not _shutdown:
        try:
            with psycopg.connect(DATABASE_URL, autocommit=True) as conn:
                conn.execute("LISTEN print_jobs")
                log.info("connected + LISTENing")
                drain(conn)  # catch anything queued while we were down
                while not _shutdown:
                    # Wait up to POLL_FALLBACK_SEC for a NOTIFY.
                    if select.select([conn], [], [], POLL_FALLBACK_SEC) == ([], [], []):
                        # Timed out. Do a fallback poll and loop.
                        drain(conn)
                        continue
                    # Consume any queued notifies (we don't care about payloads;
                    # we always drain the queue).
                    for _ in conn.notifies(timeout=0.1):
                        pass
                    drain(conn)
        except Exception:  # noqa: BLE001
            log.exception("worker loop crashed; reconnecting in 5s")
            time.sleep(5)
    log.info("bye")
    return 0


if __name__ == "__main__":
    sys.exit(main())
