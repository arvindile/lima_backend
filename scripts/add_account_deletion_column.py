"""
One-time fix for an existing Postgres database: adds the new is_deleted
column to the `players` table (used by the account-deletion feature).

Why this was needed: Base.metadata.create_all() only creates tables that
don't exist yet — it never adds new columns to a table that's already
there. Without this, DELETE /players/me and login would fail with
"column players.is_deleted does not exist".

Safe to re-run — the ADD COLUMN uses IF NOT EXISTS.

Run once, pointed at your production DATABASE_URL:

    $env:DATABASE_URL="postgresql+pg8000://...your Neon connection string..."
    python -m scripts.add_account_deletion_column
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import text

from app.database import engine

STATEMENTS = [
    "ALTER TABLE players ADD COLUMN IF NOT EXISTS is_deleted BOOLEAN NOT NULL DEFAULT FALSE",
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

    print("Done — players table now has is_deleted.")


if __name__ == "__main__":
    main()
