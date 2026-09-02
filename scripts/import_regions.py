"""
One-time import of the national province/city/barangay list into the
database. Run this once after setting up the backend:

    python -m scripts.import_regions

Safe to re-run — it clears the table first, so re-running just refreshes
the data instead of duplicating it.
"""
import csv
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.database import Base, SessionLocal, engine
from app.models import PhAddress

CSV_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data", "PH_Barangays_by_City_Municipality.csv")
BATCH_SIZE = 1000


def main():
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()

    try:
        existing_count = db.query(PhAddress).count()
        if existing_count > 0:
            print(f"Clearing {existing_count} existing rows...")
            db.query(PhAddress).delete()
            db.commit()

        with open(CSV_PATH, newline="", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            batch = []
            total = 0

            for row in reader:
                batch.append({
                    "id": __import__("uuid").uuid4().hex,
                    "region": row["Region"],
                    "province": row["Province"],
                    "city_municipality": row["City/Municipality"],
                    "type": row["Type"],
                    "barangay": row["Barangay"],
                })
                if len(batch) >= BATCH_SIZE:
                    db.bulk_insert_mappings(PhAddress, batch)
                    db.commit()
                    total += len(batch)
                    print(f"Imported {total} rows...")
                    batch = []

            if batch:
                db.bulk_insert_mappings(PhAddress, batch)
                db.commit()
                total += len(batch)

        print(f"Done — imported {total} barangay rows.")
    finally:
        db.close()


if __name__ == "__main__":
    main()
