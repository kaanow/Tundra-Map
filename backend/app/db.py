import os
from contextlib import asynccontextmanager
from psycopg_pool import AsyncConnectionPool

DATABASE_URL = os.environ["DATABASE_URL"]

pool = AsyncConnectionPool(DATABASE_URL, min_size=1, max_size=10, open=False)


async def startup():
    await pool.open()


async def shutdown():
    await pool.close()


@asynccontextmanager
async def conn():
    async with pool.connection() as c:
        yield c
