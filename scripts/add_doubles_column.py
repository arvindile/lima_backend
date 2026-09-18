"""
One-time fix for an existing Postgres database: adds the columns needed
for doubles support to the `players` and `matches` tables.

Safe to re-run — everything uses IF NOT EXISTS.

Run once, pointed at your production DATABASE_URL:

    $env:DATABASE_URL="postgresql+pg8000://...your Neon connection string..."
    python -m scripts.add_doubles_columns
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import text

from app.database import engine

STATEMENTS = [
    "ALTER TABLE players ADD COLUMN IF NOT EXISTS doubles_points INTEGER NOT NULL DEFAULT 0",
    "ALTER TABLE players ADD COLUMN IF NOT EXISTS doubles_matches_played INTEGER NOT NULL DEFAULT 0",
    "ALTER TABLE players ADD COLUMN IF NOT EXISTS doubles_wins INTEGER NOT NULL DEFAULT 0",
    "ALTER TABLE players ADD COLUMN IF NOT EXISTS doubles_losses INTEGER NOT NULL DEFAULT 0",
    # category uses native_enum=False (plain text column) — same pattern
    # as MatchStatus/FriendshipStatus, so no Postgres ALTER TYPE dance is
    # needed to add new values later.
    "ALTER TABLE matches ADD COLUMN IF NOT EXISTS category VARCHAR NOT NULL DEFAULT 'SINGLES'",
    "ALTER TABLE matches ADD COLUMN IF NOT EXISTS vanguard_partner_id VARCHAR",
    "ALTER TABLE matches ADD COLUMN IF NOT EXISTS sentinel_partner_id VARCHAR",
    "ALTER TABLE matches ADD COLUMN IF NOT EXISTS vanguard_partner_accepted BOOLEAN NOT NULL DEFAULT FALSE",
    "ALTER TABLE matches ADD COLUMN IF NOT EXISTS sentinel_accepted BOOLEAN NOT NULL DEFAULT FALSE",
    "ALTER TABLE matches ADD COLUMN IF NOT EXISTS sentinel_partner_accepted BOOLEAN NOT NULL DEFAULT FALSE",
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

    print("Done — players and matches tables now have the doubles-support columns.")


if __name__ == "__main__":
    main()
