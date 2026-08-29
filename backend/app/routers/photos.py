"""Photo upload / serve / delete.

Storage is filesystem-only: images land in ``PHOTO_DIR`` (default ``./photos``).
On Railway that path should point at a mounted volume so photos survive
redeploys. Files are named ``<item_id>_<random>.<ext>``; the item's
``photo_url`` column stores the current one.

Only one file per item is kept: replacing or deleting a photo unlinks the
previous file, so the volume doesn't silently fill with orphans.
"""
from __future__ import annotations
import os
import secrets
from pathlib import Path
from fastapi import APIRouter, HTTPException, UploadFile, File, Response
from fastapi.responses import FileResponse
from ..db import conn

PHOTO_DIR = Path(os.environ.get("PHOTO_DIR", "./photos")).resolve()
PHOTO_DIR.mkdir(parents=True, exist_ok=True)

MAX_BYTES = 8 * 1024 * 1024  # 8 MB cap; phone photos compress well below this
ALLOWED_EXT = {"jpg", "jpeg", "png", "webp", "heic"}

URL_PREFIX = "/api/photos/"

router = APIRouter(prefix="/api", tags=["photos"])


def _ext_ok(name: str) -> str | None:
    if "." not in name:
        return None
    ext = name.rsplit(".", 1)[1].lower()
    return ext if ext in ALLOWED_EXT else None


def _path_for(photo_url: str | None) -> Path | None:
    """Resolve a stored photo_url to a file inside PHOTO_DIR, or None.

    Refuses anything that escapes PHOTO_DIR — photo_url is writable through
    PATCH /api/items/{id}, so it is untrusted input.
    """
    if not photo_url or not photo_url.startswith(URL_PREFIX):
        return None
    fname = photo_url[len(URL_PREFIX):]
    if not fname or "/" in fname or "\\" in fname or ".." in fname:
        return None
    path = (PHOTO_DIR / fname).resolve()
    if path.parent != PHOTO_DIR:
        return None
    return path


def _unlink(photo_url: str | None) -> None:
    path = _path_for(photo_url)
    if path:
        path.unlink(missing_ok=True)


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

    url = f"{URL_PREFIX}{fname}"
    async with conn() as c:
        async with c.cursor() as cur:
            await cur.execute(
                "SELECT photo_url FROM items WHERE id = %s AND deleted_at IS NULL FOR UPDATE",
                (item_id,),
            )
            row = await cur.fetchone()
            if row is None:
                dest.unlink(missing_ok=True)
                raise HTTPException(404, "item not found")
            previous = row[0]
            await cur.execute(
                "UPDATE items SET photo_url = %s WHERE id = %s", (url, item_id)
            )

    # The row now points at the new file, so dropping the old one is safe.
    if previous != url:
        _unlink(previous)
    return {"photo_url": url}


@router.delete("/items/{item_id}/photo", status_code=204)
async def delete_photo(item_id: str):
    """Remove an item's photo: clears the column and unlinks the file."""
    async with conn() as c:
        async with c.cursor() as cur:
            await cur.execute(
                "SELECT photo_url FROM items WHERE id = %s AND deleted_at IS NULL FOR UPDATE",
                (item_id,),
            )
            row = await cur.fetchone()
            if row is None:
                raise HTTPException(404, "item not found")
            previous = row[0]
            await cur.execute(
                "UPDATE items SET photo_url = NULL WHERE id = %s", (item_id,)
            )

    _unlink(previous)
    return Response(status_code=204)


@router.get("/photos/{fname}")
async def get_photo(fname: str):
    # Photos are considered non-sensitive; the filename embeds 8+ random chars
    # so guessing them is impractical.
    if "/" in fname or "\\" in fname or ".." in fname:
        raise HTTPException(400, "bad name")
    path = PHOTO_DIR / fname
    if not path.is_file():
        raise HTTPException(404)
    return FileResponse(path)
