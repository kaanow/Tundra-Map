"""Shared printer plumbing: where the printer is, and how to talk to it.

Both the worker and the one-off label tool go through here, so the two hard-won
QL-810W details live in exactly one place:

  * the raster must be sent in TWO-COLOUR form (RGB + red=True) even for a
    black-only label. Single-colour mode is silently rejected — the LED blinks
    red, status comes back 0x02 with no error bit set, and nothing prints.
  * the printer must be in Raster command mode (Device Settings in its web UI).
    It ships as "P-touch Template", which fails the same silent way.
"""
from __future__ import annotations
import logging
import os
from typing import Optional

import discover

log = logging.getLogger("tundra-print.printing")

PRINTER_MODEL = os.environ.get("PRINTER_MODEL", "QL-810W")
PRINTER_BACKEND = os.environ.get("PRINTER_BACKEND", "network")
PRINTER_IDENT = os.environ.get("PRINTER_IDENT", "tcp://192.168.4.133:9100")
PRINTER_HOST = os.environ.get("PRINTER_HOST")  # optional mDNS name


class PrinterUnreachable(Exception):
    """The printer isn't answering. Transient by assumption — never a failure."""


def _seed_address() -> tuple[Optional[str], int]:
    """Split PRINTER_IDENT (tcp://host:port) into a host hint and a port."""
    ident = PRINTER_IDENT or ""
    if ident.startswith("tcp://"):
        host, _, port = ident[len("tcp://"):].partition(":")
        return (host or None, int(port) if port.isdigit() else 9100)
    return (None, 9100)


def resolve_identifier() -> str:
    """Current printer address as a brother_ql identifier, or raise."""
    if PRINTER_BACKEND != "network":
        return PRINTER_IDENT
    seed_host, port = _seed_address()
    found = discover.find_printer(
        model=PRINTER_MODEL,
        port=port,
        seed_host=seed_host,
        mdns_host=PRINTER_HOST,
        cache_path=discover.cache_path_from_env(),
    )
    if not found:
        raise PrinterUnreachable(
            f"no printer answering on :{port} (tried {seed_host or 'no seed'}"
            f"{', ' + PRINTER_HOST if PRINTER_HOST else ''}, then mDNS, then a sweep)"
        )
    return f"tcp://{found}"


def send_image(img, *, label_size: str, identifier: str | None = None) -> None:
    """Raster `img` and send it. Raises PrinterUnreachable if it can't be reached."""
    identifier = identifier or resolve_identifier()

    # Imported lazily so a machine without pyusb/libusb can still render.
    from brother_ql.backends.helpers import send
    from brother_ql.conversion import convert
    from brother_ql.raster import BrotherQLRaster

    qlr = BrotherQLRaster(PRINTER_MODEL)
    qlr.exception_on_warning = True
    instructions = convert(
        qlr=qlr,
        images=[img.convert("RGB")],   # RGB + red=True => two-colour format
        label=label_size,
        rotate="0",
        threshold=70.0,
        dither=False,
        compress=True,
        red=True,
        dpi_600=False,
        hq=True,
        cut=True,
    )
    try:
        send(instructions=instructions, printer_identifier=identifier,
             backend_identifier=PRINTER_BACKEND, blocking=True)
    except OSError as e:
        # Went away between the probe and the send, or the USB node vanished.
        raise PrinterUnreachable(f"{identifier}: {e}") from e
