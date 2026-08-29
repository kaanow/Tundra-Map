"""Render a freezer label as a PIL Image ready for brother_ql.

Portrait layout for continuous 62mm tape (DK-2205 sample and DK-22205 white):

    +---------------------+
    |                     |
    |       [QR QR]       |
    |       [QR QR]       |
    |       [QR QR]       |
    |                     |
    +---------------------+
    |   NAME (big)        |
    |   2026-08-25        |
    |                  id |
    +---------------------+

Dimensions are (width, height) in dots at 300 DPI. Width = printable dots for the
tape (696 for 62mm), height = tape length in feed direction.
"""
from __future__ import annotations
from datetime import datetime
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont
import qrcode

# Portrait: (width, height) at 300 DPI.
LABEL_SIZES = {
    "29x90":  (306, 991),   # DK-1201 die-cut address label
    "62x100": (696, 1109),  # DK-1202 shipping
    "17x54":  (165, 566),   # DK-1204 small address
    "62":     (696, 1050),  # DK-2205 continuous 62mm (~89mm long)
}

FONT_CANDIDATES = [
    "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
    "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",
    "/System/Library/Fonts/Helvetica.ttc",
]


def _font(size: int) -> ImageFont.FreeTypeFont:
    for p in FONT_CANDIDATES:
        if Path(p).exists():
            return ImageFont.truetype(p, size)
    return ImageFont.load_default()


def _fit_text(draw: ImageDraw.ImageDraw, text: str, max_w: int, start: int, min_: int = 24) -> ImageFont.FreeTypeFont:
    """Pick the largest font size where `text` fits in `max_w` pixels."""
    for size in range(start, min_ - 1, -2):
        f = _font(size)
        if draw.textlength(text, font=f) <= max_w:
            return f
    return _font(min_)


def render_label(
    *,
    url: str,
    name: str,
    added_at: datetime,
    size: str = "62",
    item_id: str | None = None,
) -> Image.Image:
    if size not in LABEL_SIZES:
        raise ValueError(f"unsupported label size: {size}")
    W, H = LABEL_SIZES[size]

    img = Image.new("1", (W, H), 1)
    draw = ImageDraw.Draw(img)

    # QR: centered horizontally in the top square (W x W). ECC-H (~30% recovery)
    # so scans still work under freezer frost / adhesive scuffs.
    qr = qrcode.QRCode(
        version=None,
        error_correction=qrcode.constants.ERROR_CORRECT_H,
        box_size=10,
        border=2,
    )
    qr.add_data(url)
    qr.make(fit=True)
    qr_img = qr.make_image(fill_color="black", back_color="white").convert("1")
    qr_side = W  # fills full width
    qr_img = qr_img.resize((qr_side, qr_side), Image.NEAREST)
    img.paste(qr_img, (0, 0))

    # Text area under QR.
    margin = 20
    text_top = qr_side + 10
    text_bottom = H - margin
    text_area_h = text_bottom - text_top
    text_w = W - 2 * margin

    date_str = added_at.strftime("%Y-%m-%d")

    # Fit the name as large as possible on ONE line in the text area width.
    name_font = _fit_text(draw, name, text_w, start=140, min_=48)
    date_font = _font(56)
    id_font = _font(36) if item_id else None

    name_bbox = draw.textbbox((0, 0), name, font=name_font)
    date_bbox = draw.textbbox((0, 0), date_str, font=date_font)
    id_bbox = draw.textbbox((0, 0), item_id, font=id_font) if item_id and id_font else None

    name_h = name_bbox[3] - name_bbox[1]
    date_h = date_bbox[3] - date_bbox[1]
    id_h = id_bbox[3] - id_bbox[1] if id_bbox else 0

    gap = 12
    id_gap = 8
    stack_h = name_h + gap + date_h + (id_gap + id_h if id_bbox else 0)
    y0 = text_top + max(0, (text_area_h - stack_h) // 2)

    # Left-align name and date; right-align id.
    draw.text((margin, y0 - name_bbox[1]), name, font=name_font, fill=0)
    y1 = y0 + name_h + gap
    draw.text((margin, y1 - date_bbox[1]), date_str, font=date_font, fill=0)
    if id_bbox and id_font:
        y2 = y1 + date_h + id_gap
        id_w = id_bbox[2] - id_bbox[0]
        draw.text((W - margin - id_w, y2 - id_bbox[1]), item_id, font=id_font, fill=0)

    return img
