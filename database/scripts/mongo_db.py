import os
from contextlib import contextmanager
from pathlib import Path

from dotenv import load_dotenv
from pymongo import MongoClient
from pymongo.errors import CollectionInvalid

PROJECT_ROOT = Path(__file__).resolve().parents[2]
load_dotenv(PROJECT_ROOT / "backend" / ".env")


def setup_database(db):
    for name in ("StationCrowdDensity", "TrainServiceAlert"):
        try:
            db.create_collection(name)
        except CollectionInvalid:
            pass  # Collection already exists; preserve it.

    db.StationCrowdDensity.create_index(
        [
            ("line_code", 1),
            ("station_code", 1),
            ("start_time", 1),
            ("end_time", 1),
        ],
        unique=True,
        name="unique_station_window",
        partialFilterExpression={
            "station_code": {"$type": "string"}
        },
    )

    db.StationCrowdDensity.create_index(
        [("station_code", 1), ("start_time", -1)],
        name="station_history",
    )

    db.TrainServiceAlert.create_index(
        [("fetched_at", -1)],
        name="alert_history",
    )


@contextmanager
def connect_database():
    with MongoClient(
        os.getenv("MONGO_URI", "mongodb://localhost:27017/"),
        serverSelectionTimeoutMS=5000,
        tz_aware=True,
    ) as client:
        client.admin.command("ping")

        db = client[os.getenv("MONGO_DB", "TransitIQ")]
        setup_database(db)

        yield db


if __name__ == "__main__":
    with connect_database() as db:
        print(f"Database ready: {db.name}")
        print("Collections ready:")
        print("- StationCrowdDensity")
        print("- TrainServiceAlert")