"""Render a freezer label as a PIL Image ready for brother_ql.

Layout for DK-1201 (29x90 mm, 306x991 px @ 300 DPI, but brother_ql wants the
raster in landscape orientation → 991 wide, 306 tall):

    +------------------------------------------------+
    |  [QR]      NAME (up to 3 words, big)           |
    |  [QR]      2026-08-25                          |
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
) -> Image.Image:
    if size not in LABEL_SIZES:
        raise ValueError(f"unsupported label size: {size}")
    W, H = LABEL_SIZES[size]

    img = Image.new("1", (W, H), 1)  # 1-bit, white background
    draw = ImageDraw.Draw(img)

    # QR on the left, square, with a bit of margin.
    margin = 16
    qr_side = H - 2 * margin
    qr = qrcode.QRCode(
        version=None,
        error_correction=qrcode.constants.ERROR_CORRECT_M,
        box_size=10,
        border=1,
    )
    qr.add_data(url)
    qr.make(fit=True)
    qr_img = qr.make_image(fill_color="black", back_color="white").convert("1")
    qr_img = qr_img.resize((qr_side, qr_side), Image.NEAREST)
    img.paste(qr_img, (margin, margin))

    # Text area to the right of QR.
    text_x = margin + qr_side + margin
    text_w = W - text_x - margin

    date_str = added_at.strftime("%Y-%m-%d")
    date_font = _font(48)
    name_font = _fit_text(draw, name, text_w, start=110, min_=40)

    # Vertically stack name (top) and date (bottom) in the text area.
    name_bbox = draw.textbbox((0, 0), name, font=name_font)
    date_bbox = draw.textbbox((0, 0), date_str, font=date_font)
    name_h = name_bbox[3] - name_bbox[1]
    date_h = date_bbox[3] - date_bbox[1]
    gap = 16
    stack_h = name_h + gap + date_h
    y0 = (H - stack_h) // 2

    draw.text((text_x, y0 - name_bbox[1]), name, font=name_font, fill=0)
    draw.text((text_x, y0 + name_h + gap - date_bbox[1]), date_str, font=date_font, fill=0)

    return img
