import os
from contextlib import asynccontextmanager
from pathlib import Path
from fastapi import FastAPI, Depends
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from . import db
from .auth import require_secret
from .routers import items, print_jobs, photos

STATIC_DIR = Path(__file__).parent / "static"


@asynccontextmanager
async def lifespan(app: FastAPI):
    await db.startup()
    yield
    await db.shutdown()


app = FastAPI(title="tundra-map", lifespan=lifespan)
app.include_router(items.router)
app.include_router(print_jobs.router)
app.include_router(photos.router)


@app.get("/api/health")
async def health():
    async with db.conn() as c:
        cur = await c.execute("SELECT 1")
        (one,) = await cur.fetchone()
    return {"ok": one == 1, "public_base_url": os.environ.get("PUBLIC_BASE_URL", "")}


@app.get("/api/config", dependencies=[Depends(require_secret)])
async def app_config():
    return {"public_base_url": os.environ.get("PUBLIC_BASE_URL", "")}


# Serve the built PWA. Any unknown path falls through to index.html so the
# SPA router can handle it.
if STATIC_DIR.exists():
    app.mount("/assets", StaticFiles(directory=STATIC_DIR / "assets"), name="assets")

    @app.get("/{full_path:path}", include_in_schema=False)
    async def spa(full_path: str):
        candidate = STATIC_DIR / full_path
        if full_path and candidate.is_file():
            return FileResponse(candidate)
        return FileResponse(STATIC_DIR / "index.html")
