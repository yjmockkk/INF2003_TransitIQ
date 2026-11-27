import zipfile
from datetime import timedelta, timezone
from pathlib import Path

from bson import json_util

from mongo_db import connect_database

# Loads the saved bus arrival snapshots (31 Oct to 8 Nov 2026) into MongoDB.
# Everything it needs is in the repository; no internet connection is needed.
SAMPLE_ZIP = (
    Path(__file__).resolve().parents[1]
    / "nosql"
    / "sample_data"
    / "BusArrival.zip"
)

SGT = timezone(timedelta(hours=8))


def main():
    if not SAMPLE_ZIP.exists():
        raise SystemExit(f"Sample data not found: {SAMPLE_ZIP}")

    # The JSON is zipped because it is about 48 MB unzipped
    with zipfile.ZipFile(SAMPLE_ZIP) as archive:
        text = archive.read("BusArrival.json").decode("utf-8")

    # json_util reads MongoDB's export format ({"$date": ...}, {"$oid": ...})
    documents = json_util.loads(text)
    print(f"Read {len(documents)} snapshots from {SAMPLE_ZIP.name}")

    with connect_database() as db:
        # Start from an empty collection so running this again
        # does not create duplicates
        removed = db.BusArrival.delete_many({}).deleted_count

        if removed:
            print(f"Removed {removed} old snapshots")

        db.BusArrival.insert_many(documents)

        # Speeds up "latest arrivals at a stop" and history queries
        db.BusArrival.create_index(
            [("bus_stop_code", 1), ("fetched_at", -1)],
            name="stop_history",
        )

        first = db.BusArrival.find_one(sort=[("fetched_at", 1)])
        last = db.BusArrival.find_one(sort=[("fetched_at", -1)])
        stops = db.BusArrival.distinct("bus_stop_code")

        print(f"Saved {db.BusArrival.count_documents({})} snapshots for {len(stops)} stops")
        print(
            "From "
            + first["fetched_at"].astimezone(SGT).strftime("%d %b %Y %H:%M")
            + " to "
            + last["fetched_at"].astimezone(SGT).strftime("%d %b %Y %H:%M")
            + " (SGT)"
        )


if __name__ == "__main__":
    main()
