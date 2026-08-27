"""Render a freezer label as a PIL Image ready for brother_ql.

Layout for DK-1201 (29x90 mm, 306x991 px @ 300 DPI, but brother_ql wants the
raster in landscape orientation → 991 wide, 306 tall):

    +------------------------------------------------+
    |[QRQR]     NAME (up to 3 words, big)            |
    |[QRQR]     2026-08-25                           |
    |[QRQR]     id                                   |
    +------------------------------------------------+
"""
from __future__ import annotations
from datetime import datetime
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont
import qrcode

# Physical geometry per Brother spec at 300 DPI.
LABEL_SIZES = {
    "29x90": (991, 306),   # DK-1201 addr label, landscape
    "62x100": (1109, 696),  # DK-1202 shipping
    "17x54": (566, 165),    # DK-1204 small addr
}

# Fallback font search. Any DejaVu is fine.
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


def _fit_text(draw: ImageDraw.ImageDraw, text: str, max_w: int, start: int, min_: int = 20) -> ImageFont.FreeTypeFont:
    """Pick the largest font size where `text` fits in `max_w` pixels."""
    for size in range(start, min_ - 1, -2):
        f = _font(size)
        w = draw.textlength(text, font=f)
        if w <= max_w:
            return f
    return _font(min_)


def render_label(
    *,
    url: str,
    name: str,
    added_at: datetime,
    size: str = "29x90",
    item_id: str | None = None,
) -> Image.Image:
    if size not in LABEL_SIZES:
        raise ValueError(f"unsupported label size: {size}")
    W, H = LABEL_SIZES[size]

    img = Image.new("1", (W, H), 1)  # 1-bit, white background
    draw = ImageDraw.Draw(img)

    # QR fills the full label height on the left. ECC-H (~30% damage
    # recovery) + border=4 (standard quiet zone) so scans still work with
    # freezer frost / adhesive scuffs.
    qr_side = H
    qr = qrcode.QRCode(
        version=None,
        error_correction=qrcode.constants.ERROR_CORRECT_H,
        box_size=10,
        border=4,
    )
    qr.add_data(url)
    qr.make(fit=True)
    qr_img = qr.make_image(fill_color="black", back_color="white").convert("1")
    qr_img = qr_img.resize((qr_side, qr_side), Image.NEAREST)
    img.paste(qr_img, (0, 0))

    # Text area to the right of QR.
    margin = 16
    text_x = qr_side + margin
    text_w = W - text_x - margin

    date_str = added_at.strftime("%Y-%m-%d")
    date_font = _font(48)
    name_font = _fit_text(draw, name, text_w, start=110, min_=40)
    id_font_size = 26
    id_font = _font(id_font_size) if item_id else None

    # Vertically stack name (big) + date (medium) + id (small) in the text area.
    name_bbox = draw.textbbox((0, 0), name, font=name_font)
    date_bbox = draw.textbbox((0, 0), date_str, font=date_font)
    name_h = name_bbox[3] - name_bbox[1]
    date_h = date_bbox[3] - date_bbox[1]
    gap = 14
    id_gap = 10
    id_h = 0
    if item_id and id_font:
        id_bbox = draw.textbbox((0, 0), item_id, font=id_font)
        id_h = id_bbox[3] - id_bbox[1]
    stack_h = name_h + gap + date_h + (id_gap + id_h if item_id else 0)
    y0 = (H - stack_h) // 2

    draw.text((text_x, y0 - name_bbox[1]), name, font=name_font, fill=0)
    draw.text((text_x, y0 + name_h + gap - date_bbox[1]), date_str, font=date_font, fill=0)
    if item_id and id_font:
        draw.text((text_x, y0 + name_h + gap + date_h + id_gap - id_bbox[1]), item_id, font=id_font, fill=0)

    return img
