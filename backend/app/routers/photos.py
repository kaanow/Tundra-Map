"""Photo upload / serve.

Storage is filesystem-only: images land in ``PHOTO_DIR`` (default ``./photos``).
On Railway that path should point at a mounted volume so photos survive
redeploys. Files are named ``<item_id>_<random>.<ext>`` so the same item can
have multiple photos over its life; the item's ``photo_url`` column stores the
most recent one.
"""
from __future__ import annotations
import os
import secrets
from pathlib import Path
from fastapi import APIRouter, HTTPException, UploadFile, File
from fastapi.responses import FileResponse
from ..db import conn

PHOTO_DIR = Path(os.environ.get("PHOTO_DIR", "./photos")).resolve()
PHOTO_DIR.mkdir(parents=True, exist_ok=True)

MAX_BYTES = 8 * 1024 * 1024  # 8 MB cap; phone photos compress well below this
ALLOWED_EXT = {"jpg", "jpeg", "png", "webp", "heic"}

router = APIRouter(prefix="/api", tags=["photos"])


def _ext_ok(name: str) -> str | None:
    if "." not in name:
        return None
    ext = name.rsplit(".", 1)[1].lower()
    return ext if ext in ALLOWED_EXT else None


@router.post("/items/{item_id}/photo")
async def upload_photo(item_id: str, file: UploadFile = File(...)):
    ext = _ext_ok(file.filename or "") or "jpg"
    fname = f"{item_id}_{secrets.token_urlsafe(6)}.{ext}"
    dest = PHOTO_DIR / fname
    written = 0
    with dest.open("wb") as f:
        while True:
            chunk = await file.read(1024 * 64)
            if not chunk:
                break
            written += len(chunk)
            if written > MAX_BYTES:
                dest.unlink(missing_ok=True)
                raise HTTPException(413, "photo too large (max 8 MB)")
            f.write(chunk)

    url = f"/api/photos/{fname}"
    async with conn() as c:
        async with c.cursor() as cur:
            await cur.execute(
                "UPDATE items SET photo_url = %s WHERE id = %s",
                (url, item_id),
            )
            if cur.rowcount == 0:
                dest.unlink(missing_ok=True)
                raise HTTPException(404, "item not found")
    return {"photo_url": url}


@router.get("/photos/{fname}")
async def get_photo(fname: str):
    # Photos are considered non-sensitive; the filename embeds 8+ random chars
    # so guessing them is impractical. Skipping the shared-key check keeps
    # <img src=...> tags simple.
    if "/" in fname or "\\" in fname or ".." in fname:
        raise HTTPException(400, "bad name")
    path = PHOTO_DIR / fname
    if not path.is_file():
        raise HTTPException(404)
    return FileResponse(path)
