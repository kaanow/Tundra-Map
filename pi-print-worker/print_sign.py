#!/usr/bin/env python3
"""Print a one-off sign: a QR plus a line of text, on the label printer.

Unlike an item label this isn't tied to a row in the database — nothing is
queued and nothing is recorded. It is for signs you stick somewhere and read
head-on, the freezer door being the case it was written for:

    ./print_sign.py --text "What's in the freezer?" --url https://cold.alti2.de

Environment comes from the same file the worker uses:

    set -a; . /etc/tundra-print.env; set +a

Use --save to render a PNG without printing.
"""
from __future__ import annotations
import argparse
import logging
import os
import sys

from render import render_sign

DEFAULT_LENGTH_MM = 93.0
DPI = 300


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--text", required=True, help="the words on the sign")
    ap.add_argument("--url", help="QR target (default: $PUBLIC_BASE_URL)")
    ap.add_argument("--length-mm", type=float, default=DEFAULT_LENGTH_MM,
                    help=f"tape used, in mm (default {DEFAULT_LENGTH_MM:g})")
    ap.add_argument("--label-size", default=os.environ.get("LABEL_SIZE", "62"),
                    help="brother_ql media name (default from $LABEL_SIZE)")
    ap.add_argument("--copies", type=int, default=1)
    ap.add_argument("--save", metavar="PATH", help="write a PNG instead of printing")
    args = ap.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(message)s")

    url = args.url or os.environ.get("PUBLIC_BASE_URL")
    if not url:
        ap.error("no --url given and PUBLIC_BASE_URL is not set")
    url = url.rstrip("/")

    img = render_sign(url=url, text=args.text,
                      length_dots=int(round(args.length_mm / 25.4 * DPI)))

    if args.save:
        img.save(args.save)
        print(f"wrote {args.save} ({img.width}x{img.height}px, "
              f"{img.height / DPI * 25.4:.0f}mm of tape)")
        return 0

    # Imported here so --save works on a machine without the printer stack.
    import printing
    try:
        identifier = printing.resolve_identifier()
        for n in range(args.copies):
            printing.send_image(img, label_size=args.label_size, identifier=identifier)
            print(f"sent copy {n + 1}/{args.copies} to {identifier}")
    except printing.PrinterUnreachable as e:
        print(f"printer unreachable: {e}", file=sys.stderr)
        print("(this tool prints immediately; it does not queue. Try again when "
              "the printer is on.)", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
