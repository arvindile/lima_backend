"""
One-time import of the national province/city/barangay list into the
database. Run this once after setting up the backend:

    python -m scripts.import_regions

Safe to re-run — it clears the table first, so re-running just refreshes
the data instead of duplicating it.

Uses a fresh database connection per batch (rather than one long-lived
connection for all ~39k rows) with automatic retries, since a single
connection held open over many round-trips to a remote database is more
likely to get dropped by the network partway through.
"""
import csv
import os
import sys
import time
import uuid

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import insert

from app.database import Base, SessionLocal, engine
from app.models import PhAddress

CSV_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data", "PH_Barangays_by_City_Municipality.csv")
BATCH_SIZE = 500
MAX_RETRIES = 5


def insert_batch_with_retry(batch):
    for attempt in range(1, MAX_RETRIES + 1):
        db = SessionLocal()
        try:
            db.execute(insert(PhAddress.__table__), batch)
            db.commit()
            return
        except Exception as e:
            db.rollback()
            if attempt == MAX_RETRIES:
                raise
            wait = attempt * 2
            print(f"  Batch failed ({e.__class__.__name__}), retrying in {wait}s... (attempt {attempt}/{MAX_RETRIES})")
            time.sleep(wait)
        finally:
            db.close()


def main():
    Base.metadata.create_all(bind=engine)

    setup_db = SessionLocal()
    try:
        existing_count = setup_db.query(PhAddress).count()
        if existing_count > 0:
            print(f"Clearing {existing_count} existing rows...")
            setup_db.query(PhAddress).delete()
            setup_db.commit()
    finally:
        setup_db.close()

    with open(CSV_PATH, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        batch = []
        total = 0

        for row in reader:
            batch.append({
                "id": uuid.uuid4().hex,
                "region": row["Region"],
                "province": row["Province"],
                "city_municipality": row["City/Municipality"],
                "type": row["Type"],
                "barangay": row["Barangay"],
            })
            if len(batch) >= BATCH_SIZE:
                insert_batch_with_retry(batch)
                total += len(batch)
                print(f"Imported {total} rows...")
                batch = []
                time.sleep(0.2)  # be gentle on the free-tier database

        if batch:
            insert_batch_with_retry(batch)
            total += len(batch)

    print(f"Done — imported {total} barangay rows.")


if __name__ == "__main__":
    main()
