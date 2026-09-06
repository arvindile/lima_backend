"""
One-time fix for an existing Postgres database: adds the new live-sync
columns to the `matches` table (vanguard_sets_won, sentinel_sets_won,
game_started_at, is_paused, paused_at, total_paused_seconds).

Why this was needed: Base.metadata.create_all() only creates tables that
don't exist yet — it never adds new columns to a table that's already
there. Without this, every request touching a match would fail with
"column matches.vanguard_sets_won does not exist" (the same class of bug
fixed in fix_status_columns.py, just for new columns instead of a locked
enum type).

Safe to re-run — every ADD COLUMN uses IF NOT EXISTS.

Run once, pointed at your production DATABASE_URL:

    $env:DATABASE_URL="postgresql+pg8000://...your Neon connection string..."
    python -m scripts.add_live_sync_columns
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import text

from app.database import engine

STATEMENTS = [
    "ALTER TABLE matches ADD COLUMN IF NOT EXISTS vanguard_sets_won INTEGER NOT NULL DEFAULT 0",
    "ALTER TABLE matches ADD COLUMN IF NOT EXISTS sentinel_sets_won INTEGER NOT NULL DEFAULT 0",
    "ALTER TABLE matches ADD COLUMN IF NOT EXISTS game_started_at TIMESTAMP",
    "ALTER TABLE matches ADD COLUMN IF NOT EXISTS is_paused BOOLEAN NOT NULL DEFAULT FALSE",
    "ALTER TABLE matches ADD COLUMN IF NOT EXISTS paused_at TIMESTAMP",
    "ALTER TABLE matches ADD COLUMN IF NOT EXISTS total_paused_seconds INTEGER NOT NULL DEFAULT 0",
]


def main():
    if engine.dialect.name != "postgresql":
        print("This database isn't Postgres — nothing to do (SQLite gets these via create_all() automatically).")
        return

    with engine.connect() as conn:
        for statement in STATEMENTS:
            print(f"Running: {statement}")
            conn.execute(text(statement))
        conn.commit()

    print("Done — matches table now has all the live-sync columns.")


if __name__ == "__main__":
    main()
