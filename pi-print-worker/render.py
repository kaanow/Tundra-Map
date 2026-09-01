"""Render a freezer label as a PIL Image ready for brother_ql.

The label is authored the way you read it — QR on top, text beneath — and
rotated 90 degrees at the end for printing. That rotation is the whole point:
it puts the label's long axis across the tape width, which buys a much larger
QR for the same length of tape. You turn the strip to read it.

    authored (read this way)          printed (comes off the tape this way)
    +----------------+
    |   [########]   |                +---------------------------+
    |   [########]   |   rotate 90    |  ]##[  s'thgiht nekcihC   |
    |   [########]   |  ----------->  |  ]##[  13-80-6202  46598  |
    |                |                +---------------------------+
    | Chicken thighs |                 696 dots across the tape
    | 2026-08-31  id |                 390 dots along it (33 mm)
    +----------------+

Sizes below are the PRINTED raster: (across-tape dots, along-tape dots). The
across-tape figure is the printable width brother_ql expects for the media,
which is narrower than the physical backing paper (696 dots, not 62 mm of
paper). The along-tape figure is ours to choose on continuous tape.
"""
from __future__ import annotations
from datetime import datetime
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont
import qrcode

DPI = 300
MM = DPI / 25.4

LABEL_SIZES = {
    "62":     (696, 390),   # DK-2205 continuous 62mm, cut at 33mm
    "62x100": (696, 1109),  # DK-1202 shipping
    "29x90":  (306, 991),   # DK-1201 die-cut address label
    "17x54":  (165, 566),   # DK-1204 small address
}

# Share of the authored width given to the QR. The rest is the text block.
QR_WIDTH_SHARE = 0.90

FONT_CANDIDATES_BOLD = [
    "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
    "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",
]
FONT_CANDIDATES_REGULAR = [
    "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    "/usr/share/fonts/truetype/liberation/LiberationSans.ttf",
]


def _mm(v: float) -> int:
    return int(round(v * MM))


def _font(size: int, bold: bool = True) -> ImageFont.FreeTypeFont:
    for p in (FONT_CANDIDATES_BOLD if bold else FONT_CANDIDATES_REGULAR):
        if Path(p).exists():
            return ImageFont.truetype(p, max(size, 8))
    return ImageFont.load_default()


def _fit(draw, text: str, max_w: int, max_h: int, start: int,
         min_: int = 18, bold: bool = True) -> ImageFont.FreeTypeFont:
    """Largest font at which `text` fits both the width and the height given."""
    for size in range(start, min_ - 1, -2):
        f = _font(size, bold)
        b = draw.textbbox((0, 0), text, font=f)
        if (b[2] - b[0]) <= max_w and (b[3] - b[1]) <= max_h:
            return f
    return _font(min_, bold)


def _wrap(draw, text: str, font: ImageFont.FreeTypeFont, max_w: int) -> list[str]:
    """Greedy word wrap. A single word wider than max_w gets its own line."""
    lines: list[str] = []
    current = ""
    for word in text.split():
        trial = f"{current} {word}".strip()
        if not current or draw.textlength(trial, font=font) <= max_w:
            current = trial
        else:
            lines.append(current)
            current = word
    if current:
        lines.append(current)
    return lines or [text]


def _measure(draw, lines, font, leading) -> tuple[int, list[int]]:
    heights = [draw.textbbox((0, 0), ln, font=font)[3] -
               draw.textbbox((0, 0), ln, font=font)[1] for ln in lines]
    return sum(heights) + leading * (len(lines) - 1), heights


def _fit_wrapped(draw, text: str, max_w: int, max_h: int, start: int,
                 min_: int = 18, max_lines: int = 3):
    """Largest font at which `text`, wrapped, fits the box.

    A narrow label leaves the name width-bound with vertical room to spare;
    wrapping spends that room on a bigger font instead of white space.
    """
    for size in range(start, min_ - 1, -2):
        f = _font(size, True)
        lines = _wrap(draw, text, f, max_w)
        if len(lines) > max_lines:
            continue
        if any(draw.textlength(ln, font=f) > max_w for ln in lines):
            continue  # an unbreakable word still overflows
        leading = max(2, int(size * 0.12))
        total, heights = _measure(draw, lines, f, leading)
        if total <= max_h:
            return f, lines, leading, total, heights
    f = _font(min_, True)
    lines = _wrap(draw, text, f, max_w)[:max_lines]
    leading = max(2, int(min_ * 0.12))
    total, heights = _measure(draw, lines, f, leading)
    return f, lines, leading, total, heights


def _qr(url: str, side_px: int) -> Image.Image:
    # ECC-H (~30% recoverable) with a proper quiet zone, so scans survive
    # frost, scuffing and a bit of adhesive haze.
    qr = qrcode.QRCode(
        version=None,
        error_correction=qrcode.constants.ERROR_CORRECT_H,
        box_size=10,
        border=2,
    )
    qr.add_data(url)
    qr.make(fit=True)
    img = qr.make_image(fill_color="black", back_color="white").convert("1")
    return img.resize((side_px, side_px), Image.NEAREST)


def render_label(
    *,
    url: str,
    name: str,
    added_at: datetime,
    size: str = "62",
    item_id: str | None = None,
) -> Image.Image:
    """Return the label in PRINT orientation, ready to hand to brother_ql."""
    if size not in LABEL_SIZES:
        raise ValueError(f"unsupported label size: {size}")
    print_w, print_h = LABEL_SIZES[size]

    # Author transposed, then rotate at the end.
    W, H = print_h, print_w
    img = Image.new("1", (W, H), 1)
    draw = ImageDraw.Draw(img)

    pad = _mm(1.5)
    qr_side = min(int(W * QR_WIDTH_SHARE), H - pad * 2)
    img.paste(_qr(url, qr_side), ((W - qr_side) // 2, pad))

    # Text block fills what's left under the QR.
    tx = pad
    ty = pad + qr_side + _mm(1.5)
    tw = W - pad * 2
    th = H - ty - pad
    if th <= _mm(3):
        return img.rotate(90, expand=True)

    date_str = added_at.strftime("%Y-%m-%d")

    # Reserve a strip for the date/id line, then give the rest to the name.
    footer_h = max(_mm(3.0), int(th * 0.22))
    gap = _mm(1.0)
    name_font, name_lines, leading, name_h, line_hs = _fit_wrapped(
        draw, name, tw, th - footer_h - gap, start=int(th * 0.8)
    )

    date_font = _fit(draw, date_str, int(tw * 0.62), footer_h,
                     start=footer_h, bold=False)
    db = draw.textbbox((0, 0), date_str, font=date_font)

    id_font = ib = None
    if item_id:
        id_font = _fit(draw, item_id, int(tw * 0.34), footer_h,
                       start=footer_h, bold=False)
        ib = draw.textbbox((0, 0), item_id, font=id_font)

    line2_h = max(db[3] - db[1], (ib[3] - ib[1]) if ib else 0)
    y = ty + max(0, (th - (name_h + gap + line2_h)) // 2)

    for line, lh in zip(name_lines, line_hs):
        b = draw.textbbox((0, 0), line, font=name_font)
        draw.text((tx, y - b[1]), line, font=name_font, fill=0)
        y += lh + leading
    y2 = y - leading + gap
    draw.text((tx, y2 - db[1]), date_str, font=date_font, fill=0)
    if item_id and id_font and ib:
        id_w = draw.textlength(item_id, font=id_font)
        draw.text((tx + tw - id_w, y2 - ib[1]), item_id, font=id_font, fill=0)

    # Long axis across the tape: this is what makes the big QR affordable.
    return img.rotate(90, expand=True)
