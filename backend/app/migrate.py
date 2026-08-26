"""Idempotent migration runner. Runs every .sql in migrations/ in name order.

Kept dead simple: a tiny `schema_migrations` table records which files have
already been applied. Works on Railway (Postgres) and on the dev machine.
"""
from __future__ import annotations
import os
import sys
from pathlib import Path
import psycopg

MIGRATIONS_DIR = Path(__file__).resolve().parent.parent / "migrations"


def main() -> int:
    db_url = os.environ["DATABASE_URL"]
    if not MIGRATIONS_DIR.exists():
        print(f"no migrations dir at {MIGRATIONS_DIR}")
        return 0
    with psycopg.connect(db_url, autocommit=True) as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS schema_migrations (
                name       text PRIMARY KEY,
                applied_at timestamptz NOT NULL DEFAULT now()
            )
        """)
        cur = conn.execute("SELECT name FROM schema_migrations")
        applied = {r[0] for r in cur.fetchall()}
        for path in sorted(MIGRATIONS_DIR.glob("*.sql")):
            if path.name in applied:
                continue
            print(f"applying {path.name}...", flush=True)
            with conn.transaction():
                conn.execute(path.read_text())
                conn.execute(
                    "INSERT INTO schema_migrations (name) VALUES (%s)",
                    (path.name,),
                )
            print(f"  ok", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
