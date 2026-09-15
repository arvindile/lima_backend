"""
One-time fix for an existing Postgres database: adds the columns needed
for account recovery (email + password reset code) to the `players`
table.

Why this was needed: Base.metadata.create_all() only creates tables that
don't exist yet — it never adds new columns to a table that's already
there. Without this, login/registration will fail with something like
"column players.email does not exist".

Safe to re-run — everything uses IF NOT EXISTS.

Run once, pointed at your production DATABASE_URL:

    $env:DATABASE_URL="postgresql+pg8000://...your Neon connection string..."
    python -m scripts.add_password_reset_columns
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import text

from app.database import engine

STATEMENTS = [
    "ALTER TABLE players ADD COLUMN IF NOT EXISTS email VARCHAR",
    "ALTER TABLE players ADD COLUMN IF NOT EXISTS password_reset_code VARCHAR",
    "ALTER TABLE players ADD COLUMN IF NOT EXISTS password_reset_expires_at TIMESTAMP",
    "CREATE UNIQUE INDEX IF NOT EXISTS ix_players_email ON players (email)",
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

    print("Done — players table now has email, password_reset_code, and password_reset_expires_at.")


if __name__ == "__main__":
    main()
