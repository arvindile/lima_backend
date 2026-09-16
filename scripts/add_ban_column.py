"""
One-time fix for an existing Postgres database: adds the is_banned
column to the `players` table.

Note: this is the ONLY migration needed for the reporting/blocking
feature. The new `blocks` and `reports` tables are brand new — Base.
metadata.create_all() DOES create missing tables automatically (it just
never adds columns to a table that already exists), so those two need
no manual step.

Safe to re-run — uses IF NOT EXISTS.

Run once, pointed at your production DATABASE_URL:

    $env:DATABASE_URL="postgresql+pg8000://...your Neon connection string..."
    python -m scripts.add_ban_column
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import text

from app.database import engine

STATEMENTS = [
    "ALTER TABLE players ADD COLUMN IF NOT EXISTS is_banned BOOLEAN NOT NULL DEFAULT FALSE",
]


def main():
    if engine.dialect.name != "postgresql":
        print("This database isn't Postgres — nothing to do (SQLite gets this via create_all() automatically).")
        return

    with engine.connect() as conn:
        for statement in STATEMENTS:
            print(f"Running: {statement}")
            conn.execute(text(statement))
        conn.commit()

    print("Done — players table now has is_banned.")


if __name__ == "__main__":
    main()
