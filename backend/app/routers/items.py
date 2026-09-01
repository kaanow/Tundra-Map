from typing import Optional
from fastapi import APIRouter, HTTPException, Query, Response
from ..db import conn
from ..models import ItemIn, ItemOut, ItemPatch

# No auth: reaching the freezer is already a physical-access problem, and
# nothing here destroys data. Delete sets a flag and leaves the row, so the
# worst a stranger with a URL can do is hide or add noise, and both are
# recoverable.
router = APIRouter(prefix="/api/items", tags=["items"])

SELECT_COLS = """
    i.id, i.name, i.added_at,
    i.quantity, i.unit, i.source, i.notes, i.category, i.location,
    i.photo_url, i.consumed_at, i.deleted_at
"""

JOIN = "FROM items i"

# Soft-deleted rows stay in the table but are hidden from every route that
# browses. Only the single-item route, which you can reach solely by knowing
# the ID, will show one.
LIVE = "i.deleted_at IS NULL"



async def _fetch(item_id: str, *, include_deleted: bool = False) -> dict:
    where = "WHERE i.id = %s" if include_deleted else f"WHERE i.id = %s AND {LIVE}"
    async with conn() as c:
        cur = await c.execute(f"SELECT {SELECT_COLS} {JOIN} {where}", (item_id,))
        row = await cur.fetchone()
        if not row:
            raise HTTPException(404, "not found")
        cols = [d.name for d in cur.description]
        return dict(zip(cols, row))


@router.get("", response_model=list[ItemOut])
async def list_items(
    consumed: bool = Query(False, description="include consumed items"),
    q: Optional[str] = Query(None, description="name search"),
    category: Optional[str] = None,
    stale_days: Optional[int] = Query(None, ge=1, le=3650,
                                      description="only items added more than N days ago"),
    limit: int = Query(200, le=1000),
):
    where = [LIVE]
    args: list = []
    if not consumed:
        where.append("i.consumed_at IS NULL")
    if q:
        where.append("i.name ILIKE %s")
        args.append(f"%{q}%")
    if category:
        where.append("i.category = %s")
        args.append(category)
    if stale_days is not None:
        where.append("i.added_at < now() - make_interval(days => %s)")
        args.append(stale_days)
    where_sql = "WHERE " + " AND ".join(where)
    sql = f"SELECT {SELECT_COLS} {JOIN} {where_sql} ORDER BY i.added_at DESC LIMIT %s"
    args.append(limit)
    async with conn() as c:
        cur = await c.execute(sql, args)
        cols = [d.name for d in cur.description]
        return [dict(zip(cols, row)) for row in await cur.fetchall()]


@router.get("/stats/categories")
async def category_stats():
    """Buckets by category for filtering; also surfaces stale counts."""
    async with conn() as c:
        cur = await c.execute("""
            SELECT
                COALESCE(category, '') AS category,
                count(*) FILTER (WHERE consumed_at IS NULL)                                                   AS active,
                count(*) FILTER (WHERE consumed_at IS NULL AND added_at < now() - interval '90 days')          AS stale_90,
                count(*) FILTER (WHERE consumed_at IS NULL AND added_at < now() - interval '180 days')         AS stale_180
            FROM items
            WHERE deleted_at IS NULL
            GROUP BY 1
            ORDER BY 1
        """)
        cols = [d.name for d in cur.description]
        return [dict(zip(cols, row)) for row in await cur.fetchall()]


@router.post("", response_model=ItemOut, status_code=201)
async def create_item(body: ItemIn):
    async with conn() as c:
        async with c.cursor() as cur:
            await cur.execute(
                """
                INSERT INTO items (name, quantity, unit, source, notes, category, location)
                VALUES (%s, %s, %s, %s, %s, %s, %s)
                RETURNING id
                """,
                (body.name.strip(), body.quantity, body.unit, body.source,
                 body.notes, body.category, body.location),
            )
            (new_id,) = await cur.fetchone()
    return await _fetch(new_id)


@router.get("/{item_id}", response_model=ItemOut)
async def get_item(item_id: str):
    """Deleted items are visible here on purpose.

    Knowing the ID means you are almost certainly holding the printed label,
    and a physical thing in the freezer is worth showing even if someone
    removed it from the list. The response carries `deleted_at` so the client
    can say so plainly and offer to undelete.
    """
    return await _fetch(item_id, include_deleted=True)


@router.patch("/{item_id}", response_model=ItemOut)
async def patch_item(item_id: str, body: ItemPatch):
    fields = body.model_dump(exclude_unset=True)
    if not fields:
        return await _fetch(item_id)
    sets = ", ".join(f"{k} = %s" for k in fields)
    args = list(fields.values()) + [item_id]
    async with conn() as c:
        async with c.cursor() as cur:
            await cur.execute(
                f"UPDATE items SET {sets} WHERE id = %s AND deleted_at IS NULL", args
            )
            if cur.rowcount == 0:
                raise HTTPException(404, "not found")
    return await _fetch(item_id)


@router.post("/{item_id}/consume", response_model=ItemOut)
async def consume_item(item_id: str):
    async with conn() as c:
        async with c.cursor() as cur:
            await cur.execute(
                """
                UPDATE items SET consumed_at = now()
                WHERE id = %s AND consumed_at IS NULL AND deleted_at IS NULL
                """,
                (item_id,),
            )
    return await _fetch(item_id)


@router.post("/{item_id}/unconsume", response_model=ItemOut)
async def unconsume_item(item_id: str):
    """Undo a consume — the normal lifecycle is reversible."""
    async with conn() as c:
        async with c.cursor() as cur:
            await cur.execute(
                """
                UPDATE items SET consumed_at = NULL
                WHERE id = %s AND deleted_at IS NULL
                """,
                (item_id,),
            )
            if cur.rowcount == 0:
                raise HTTPException(404, "not found")
    return await _fetch(item_id)


@router.delete("/{item_id}", status_code=204)
async def delete_item(item_id: str):
    """Soft delete: flag the row and leave it in the table.

    The item disappears from every browsing route. It stays reachable by ID,
    so scanning its label still works and offers an undelete.
    """
    async with conn() as c:
        async with c.cursor() as cur:
            await cur.execute(
                """
                UPDATE items SET deleted_at = now()
                WHERE id = %s AND deleted_at IS NULL
                """,
                (item_id,),
            )
            if cur.rowcount == 0:
                raise HTTPException(404, "not found")
    return Response(status_code=204)


@router.post("/{item_id}/undelete", response_model=ItemOut)
async def undelete_item(item_id: str):
    """Bring a deleted item back. Only discoverable from the item's own page,
    which you need the ID to reach."""
    async with conn() as c:
        async with c.cursor() as cur:
            await cur.execute(
                "UPDATE items SET deleted_at = NULL WHERE id = %s",
                (item_id,),
            )
            if cur.rowcount == 0:
                raise HTTPException(404, "not found")
    return await _fetch(item_id)
