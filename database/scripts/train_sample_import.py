from pathlib import Path

from bson import json_util
from pymongo import ReplaceOne

from mongo_db import connect_database

SAMPLE_DIR = Path(__file__).resolve().parents[1] / "nosql" / "sample_data"


def main():
    with connect_database() as db:
        for collection_name in ("StationCrowdDensity", "TrainServiceAlert"):
            path = SAMPLE_DIR / f"{collection_name}.json"
            documents = json_util.loads(path.read_text(encoding="utf-8"))
            operations = [
                ReplaceOne({"_id": document["_id"]}, document, upsert=True)
                for document in documents
            ]
            db[collection_name].bulk_write(operations)
            print(f"Loaded {len(documents):,} documents into {collection_name}")


if __name__ == "__main__":
    main()