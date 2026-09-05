"""
One-time fix for an existing Postgres database: converts the `status`
columns on `matches` and `friendships` from a native Postgres ENUM type
(which locks in whatever values existed when the table was first created)
to plain VARCHAR (which accepts any string the Python code allows).

Why this was needed: adding PENDING/DECLINED to MatchStatus in Python code
does NOT retroactively teach an already-existing Postgres enum type about
those new values — Postgres rejects them at the database level, causing
500 errors on every request that touched status.

Safe to run against a database that's already on VARCHAR (it'll just be a
no-op in that case). NOT needed for SQLite — this only matters for Postgres.

Run once, pointed at your production DATABASE_URL:

    $env:DATABASE_URL="postgresql+pg8000://...your Neon connection string..."
    python -m scripts.fix_status_columns
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import text

from app.database import engine


def main():
    if engine.dialect.name != "postgresql":
        print("This database isn't Postgres — nothing to fix (SQLite doesn't have this issue).")
        return

    with engine.connect() as conn:
        print("Converting matches.status to VARCHAR...")
        conn.execute(text("ALTER TABLE matches ALTER COLUMN status TYPE VARCHAR(20) USING status::text"))

        print("Converting friendships.status to VARCHAR...")
        conn.execute(text("ALTER TABLE friendships ALTER COLUMN status TYPE VARCHAR(20) USING status::text"))

        conn.commit()

    print("Done — status columns are now plain text and will accept any value from the Python code.")


if __name__ == "__main__":
    main()
