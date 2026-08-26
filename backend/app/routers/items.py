from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from ..auth import require_secret
from ..db import conn
from ..models import ItemIn, ItemOut, ItemPatch

router = APIRouter(prefix="/api/items", tags=["items"], dependencies=[Depends(require_secret)])

SELECT_COLS = """
    i.id, i.name, i.added_at, u1.name AS added_by,
    i.quantity, i.unit, i.source, i.notes, i.category, i.location,
    i.photo_url, i.consumed_at, u2.name AS consumed_by
"""

JOIN = """
    FROM items i
    LEFT JOIN users u1 ON u1.id = i.added_by
    LEFT JOIN users u2 ON u2.id = i.consumed_by
"""


async def _resolve_user(cur, name: Optional[str]):
    if not name:
        return None
    await cur.execute(
        "INSERT INTO users(name) VALUES (%s) ON CONFLICT (name) DO UPDATE SET name=EXCLUDED.name RETURNING id",
        (name.strip(),),
    )
    row = await cur.fetchone()
    return row[0]


@router.get("", response_model=list[ItemOut])
async def list_items(
    consumed: bool = Query(False, description="include consumed items"),
    q: Optional[str] = Query(None, description="name search"),
    category: Optional[str] = None,
    limit: int = Query(200, le=1000),
):
    where = []
    args: list = []
    if not consumed:
        where.append("i.consumed_at IS NULL")
    if q:
        where.append("i.name ILIKE %s")
        args.append(f"%{q}%")
    if category:
        where.append("i.category = %s")
        args.append(category)
    where_sql = ("WHERE " + " AND ".join(where)) if where else ""
    sql = f"SELECT {SELECT_COLS} {JOIN} {where_sql} ORDER BY i.added_at DESC LIMIT %s"
    args.append(limit)
    async with conn() as c:
        cur = await c.execute(sql, args)
        cols = [d.name for d in cur.description]
        return [dict(zip(cols, row)) for row in await cur.fetchall()]


@router.post("", response_model=ItemOut, status_code=201)
async def create_item(body: ItemIn):
    async with conn() as c:
        async with c.cursor() as cur:
            added_by_id = await _resolve_user(cur, body.added_by)
            await cur.execute(
                """
                INSERT INTO items (name, added_by, quantity, unit, source, notes, category, location)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                RETURNING id
                """,
                (body.name.strip(), added_by_id, body.quantity, body.unit, body.source,
                 body.notes, body.category, body.location),
            )
            (new_id,) = await cur.fetchone()
            await cur.execute(f"SELECT {SELECT_COLS} {JOIN} WHERE i.id = %s", (new_id,))
            cols = [d.name for d in cur.description]
            row = await cur.fetchone()
            return dict(zip(cols, row))


@router.get("/{item_id}", response_model=ItemOut)
async def get_item(item_id: str):
    async with conn() as c:
        cur = await c.execute(f"SELECT {SELECT_COLS} {JOIN} WHERE i.id = %s", (item_id,))
        row = await cur.fetchone()
        if not row:
            raise HTTPException(404, "not found")
        cols = [d.name for d in cur.description]
        return dict(zip(cols, row))


@router.patch("/{item_id}", response_model=ItemOut)
async def patch_item(item_id: str, body: ItemPatch):
    fields = body.model_dump(exclude_unset=True)
    if not fields:
        return await get_item(item_id)
    sets = ", ".join(f"{k} = %s" for k in fields)
    args = list(fields.values()) + [item_id]
    async with conn() as c:
        async with c.cursor() as cur:
            await cur.execute(f"UPDATE items SET {sets} WHERE id = %s", args)
            if cur.rowcount == 0:
                raise HTTPException(404, "not found")
    return await get_item(item_id)


@router.post("/{item_id}/consume", response_model=ItemOut)
async def consume_item(item_id: str, by: Optional[str] = None):
    async with conn() as c:
        async with c.cursor() as cur:
            consumed_by_id = await _resolve_user(cur, by)
            await cur.execute(
                "UPDATE items SET consumed_at = now(), consumed_by = %s WHERE id = %s AND consumed_at IS NULL",
                (consumed_by_id, item_id),
            )
    return await get_item(item_id)


@router.delete("/{item_id}", status_code=204)
async def delete_item(item_id: str):
    async with conn() as c:
        async with c.cursor() as cur:
            await cur.execute("DELETE FROM items WHERE id = %s", (item_id,))
            if cur.rowcount == 0:
                raise HTTPException(404, "not found")
