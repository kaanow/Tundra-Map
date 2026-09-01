#!/usr/bin/env python3
"""Print a one-off sign: a QR plus a line of text, on the label printer.

Unlike an item label this isn't tied to a row in the database — nothing is
queued and nothing is recorded. It is for signs you stick somewhere and read
head-on, the freezer door being the case it was written for.

By default this RENDERS ONLY and writes a PNG. Tape costs money, so putting
anything on it takes an explicit --print:

    ./print_sign.py --text "What's in the freezer?"            # preview
    ./print_sign.py --text "What's in the freezer?" --print    # actually print

Signs default to the same tape length as item labels. Going bigger is a
deliberate act: --length-mm above the item-label size needs --big as well.

Environment comes from the same file the worker uses:

    set -a; . /etc/tundra-print.env; set +a
"""
from __future__ import annotations
import argparse
import logging
import os
import sys

from render import LABEL_SIZES as render_sizes, render_sign

DPI = 300

# Match the item labels rather than inventing a size. render.py owns the number.
_ACROSS, _ALONG = render_sizes["62"]
DEFAULT_LENGTH_MM = _ALONG / DPI * 25.4


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--text", required=True, help="the words on the sign")
    ap.add_argument("--url", help="QR target (default: $PUBLIC_BASE_URL)")
    ap.add_argument("--length-mm", type=float, default=DEFAULT_LENGTH_MM,
                    help=f"tape used, in mm (default {DEFAULT_LENGTH_MM:.0f}, "
                         f"same as an item label)")
    ap.add_argument("--big", action="store_true",
                    help=f"allow --length-mm above {DEFAULT_LENGTH_MM:.0f}mm")
    ap.add_argument("--no-rotate", dest="rotate", action="store_false",
                    help="hang the way it prints instead of turning it "
                         "(costs much more tape for the same size)")
    ap.add_argument("--print", dest="do_print", action="store_true",
                    help="actually send it to the printer (default: preview only)")
    ap.add_argument("--label-size", default=os.environ.get("LABEL_SIZE", "62"),
                    help="brother_ql media name (default from $LABEL_SIZE)")
    ap.add_argument("--copies", type=int, default=1)
    ap.add_argument("--save", metavar="PATH",
                    help="where to write the preview PNG (default: ./sign-preview.png)")
    args = ap.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(message)s")

    url = args.url or os.environ.get("PUBLIC_BASE_URL")
    if not url:
        ap.error("no --url given and PUBLIC_BASE_URL is not set")
    url = url.rstrip("/")

    if args.length_mm > DEFAULT_LENGTH_MM and not args.big:
        ap.error(
            f"--length-mm {args.length_mm:g} is bigger than an item label "
            f"({DEFAULT_LENGTH_MM:.0f}mm). Tape is expensive — pass --big if "
            f"you really mean it."
        )

    img = render_sign(url=url, text=args.text, rotate=args.rotate,
                      length_dots=int(round(args.length_mm / 25.4 * DPI)))

    if not args.do_print:
        dest = args.save or "sign-preview.png"
        img.save(dest)
        print(f"wrote {dest} ({img.width}x{img.height}px, "
              f"{img.height / DPI * 25.4:.0f}mm of tape)")
        print("preview only — add --print to send it to the printer")
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
