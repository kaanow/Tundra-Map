from typing import Optional
from fastapi import APIRouter, HTTPException
from ..db import conn
from ..models import PrintJobOut

router = APIRouter(prefix="/api", tags=["print"])


@router.post("/items/{item_id}/print", response_model=PrintJobOut, status_code=202)
async def enqueue_print(item_id: str):
    async with conn() as c:
        async with c.cursor() as cur:
            await cur.execute(
                "SELECT 1 FROM items WHERE id = %s AND deleted_at IS NULL", (item_id,)
            )
            if not await cur.fetchone():
                raise HTTPException(404, "item not found")
            await cur.execute(
                """
                INSERT INTO print_jobs (item_id)
                VALUES (%s)
                RETURNING id, item_id, requested_at, printed_at, error, attempts
                """,
                (item_id,),
            )
            row = await cur.fetchone()
            cols = [d.name for d in cur.description]
            return dict(zip(cols, row))


@router.get("/print-jobs", response_model=list[PrintJobOut])
async def list_recent(limit: int = 50):
    async with conn() as c:
        cur = await c.execute(
            """
            SELECT id, item_id, requested_at, printed_at, error, attempts
            FROM print_jobs
            ORDER BY id DESC
            LIMIT %s
            """,
            (limit,),
        )
        cols = [d.name for d in cur.description]
        return [dict(zip(cols, row)) for row in await cur.fetchall()]
