"""Tundra-Map print worker.

Keeps a single Postgres connection open, LISTENs on `print_jobs`, and prints
each queued job on the Brother QL-810W. Falls back to polling every 30s in
case a NOTIFY is missed (e.g., DB reconnect).

The printer is treated as something that comes and goes. It lives on DHCP, it
gets switched off overnight, and the worker may well boot before it does. So
nothing here touches the printer at startup, the address is resolved lazily at
print time, and a job that can't reach the printer stays queued rather than
failing — it prints when the printer comes back.
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

import printing
from printing import PrinterUnreachable
from render import render_label

log = logging.getLogger("tundra-print")
logging.basicConfig(
    level=os.environ.get("LOG_LEVEL", "INFO"),
    format="%(asctime)s %(levelname)s %(message)s",
)

DATABASE_URL   = os.environ["DATABASE_URL"]
PUBLIC_BASE    = os.environ.get("PUBLIC_BASE_URL", "http://localhost:8000").rstrip("/")
PRINTER_BACKEND = printing.PRINTER_BACKEND  # "file" writes PNGs instead
LABEL_SIZE     = os.environ.get("LABEL_SIZE", "62")
FILE_BACKEND_DIR = os.environ.get("FILE_BACKEND_DIR", "/tmp/tundra-labels")
POLL_FALLBACK_SEC = 30

# Backoff between attempts while the printer is unreachable.
RETRY_BASE_SEC = 15
RETRY_MAX_SEC = 300

_shutdown = False

# Set when the printer is unreachable; suppresses attempts until it passes.
_retry_after = 0.0
_retry_delay = 0.0
_unreachable_streak = 0


def _handle_signal(sig, frame):
    global _shutdown
    log.info("received %s; shutting down", sig)
    _shutdown = True


signal.signal(signal.SIGTERM, _handle_signal)
signal.signal(signal.SIGINT, _handle_signal)


def item_url(item_id: str) -> str:
    # Short and secretless: fewer characters means coarser QR modules, which
    # survive freezer frost and scuffing. The app has no auth, so a bare item
    # URL is all a scanning phone needs.
    return f"{PUBLIC_BASE}/i/{item_id}"


def _print_to_file(img, item_id: str) -> None:
    """Dry-run mode: save the rendered label to disk instead of printing."""
    os.makedirs(FILE_BACKEND_DIR, exist_ok=True)
    ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    dest = os.path.join(FILE_BACKEND_DIR, f"{ts}_{item_id}.png")
    img.save(dest)
    log.info("wrote label to %s (file backend; no printer)", dest)


def print_label(name: str, added_at: datetime, item_id: str) -> None:
    img = render_label(url=item_url(item_id), name=name, added_at=added_at,
                       size=LABEL_SIZE, item_id=item_id)
    if PRINTER_BACKEND == "file":
        _print_to_file(img, item_id)
        return

    # Resolving first means an offline printer costs one short probe rather
    # than a full raster conversion.
    printing.send_image(img, label_size=LABEL_SIZE)


def claim_and_print_one(conn: psycopg.Connection) -> str:
    """Claim the oldest pending job and try to print it.

    Returns one of:
      "none"    — nothing queued
      "printed" — done
      "retry"   — printer unreachable; job left queued for a later attempt
      "failed"  — real error; job marked with it and taken out of the queue
    """
    with conn.transaction():
        cur = conn.execute(
            """
            SELECT pj.id, pj.item_id, pj.attempts, i.name, i.added_at
            FROM print_jobs pj
            JOIN items i ON i.id = pj.item_id
            WHERE pj.printed_at IS NULL AND pj.error IS NULL
              AND i.deleted_at IS NULL
            ORDER BY pj.id
            FOR UPDATE SKIP LOCKED
            LIMIT 1
            """
        )
        row = cur.fetchone()
        if not row:
            return "none"
        job_id, item_id, attempts, name, added_at = row
        log.info("printing job=%s item=%s name=%r", job_id, item_id, name)
        try:
            print_label(name=name, added_at=added_at, item_id=item_id)
        except PrinterUnreachable as e:
            # Deliberately leaves error NULL so the job stays in the queue.
            conn.execute(
                "UPDATE print_jobs SET attempts = attempts + 1 WHERE id = %s", (job_id,)
            )
            _note_unreachable(job_id, e)
            return "retry"
        except Exception as e:  # noqa: BLE001 — a real fault; record and move on
            log.exception("print failed for job %s", job_id)
            conn.execute(
                "UPDATE print_jobs SET attempts = attempts + 1, error = %s WHERE id = %s",
                (f"{type(e).__name__}: {e}"[:500], job_id),
            )
            return "failed"
        conn.execute(
            "UPDATE print_jobs SET printed_at = now(), attempts = attempts + 1 WHERE id = %s",
            (job_id,),
        )
    return "printed"


def _note_unreachable(job_id: int, err: Exception) -> None:
    """Arm the backoff, and log without filling the journal overnight."""
    global _retry_after, _retry_delay, _unreachable_streak
    _retry_delay = min(max(_retry_delay * 2, RETRY_BASE_SEC), RETRY_MAX_SEC)
    _retry_after = time.monotonic() + _retry_delay
    _unreachable_streak += 1
    # First failure is worth a warning; after that only occasionally, since an
    # overnight power-off is expected and shouldn't look like an incident.
    if _unreachable_streak == 1 or _unreachable_streak % 10 == 0:
        log.warning("job %s waiting on the printer (%s); attempt %d, next try in %ds",
                    job_id, err, _unreachable_streak, int(_retry_delay))


def _note_reachable() -> None:
    global _retry_after, _retry_delay, _unreachable_streak
    if _unreachable_streak:
        log.info("printer is back after %d attempts", _unreachable_streak)
    _retry_after = 0.0
    _retry_delay = 0.0
    _unreachable_streak = 0


def drain(conn: psycopg.Connection) -> None:
    """Print everything queued, unless we're waiting out an offline printer."""
    if time.monotonic() < _retry_after:
        return
    while not _shutdown:
        outcome = claim_and_print_one(conn)
        if outcome == "none":
            return
        if outcome == "retry":
            return  # backoff is armed; try again on a later poll
        if outcome == "printed":
            _note_reachable()


def main() -> int:
    log.info("starting; printer=%s backend=%s seed=%s host=%s size=%s",
             printing.PRINTER_MODEL, PRINTER_BACKEND, printing.PRINTER_IDENT,
             printing.PRINTER_HOST or "-", LABEL_SIZE)
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
