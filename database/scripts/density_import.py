import os
from datetime import datetime, timezone

import requests

from mongo_db import connect_database

URL = (
    "https://datamall2.mytransport.sg/"
    "ltaodataservice/PCDRealTime"
)

TRAIN_LINES = ["NSL", "EWL", "NEL", "CCL", "DTL", "TEL"]


def parse_date(value):
    date = datetime.fromisoformat(value.replace("Z", "+00:00"))

    if date.tzinfo is None:
        raise ValueError("LTA timestamp has no timezone")

    return date.astimezone(timezone.utc)


def import_line(db, session, key, line):
    response = session.get(
        URL,
        headers={
            "AccountKey": key,
            "Accept": "application/json",
        },
        params={"TrainLine": line},
        timeout=20,
    )
    response.raise_for_status()

    rows = response.json()["value"]
    if not isinstance(rows, list):
        raise ValueError("Unexpected crowd response")

    fetched_at = datetime.now(timezone.utc)
    documents = []

    # Validate the response before storing its observations.
    for row in rows:
        start = parse_date(row["StartTime"])
        end = parse_date(row["EndTime"])

        if end <= start:
            raise ValueError("Invalid observation window")

        documents.append({
            "line_code": line,
            "station_code": row["Station"],
            "start_time": start,
            "end_time": end,
            "crowd_level": row["CrowdLevel"],
            "source": "LTA DataMall",
            "fetched_at": fetched_at,
        })

    for document in documents:
        unique_key = {
            field: document[field]
            for field in (
                "line_code",
                "station_code",
                "start_time",
                "end_time",
            )
        }

        db.StationCrowdDensity.update_one(
            unique_key,
            {
                "$set": document,
                "$setOnInsert": {
                    "first_fetched_at": fetched_at,
                },
            },
            upsert=True,
        )

    print(f"{line}: saved {len(documents)} station observations")


def main():
    key = os.getenv("LTA_ACCOUNT_KEY")
    if not key:
        raise SystemExit("Missing LTA_ACCOUNT_KEY in backend/.env")

    failed = False

    with connect_database() as db, requests.Session() as session:
        for line in TRAIN_LINES:
            try:
                import_line(db, session, key, line)
            except (
                requests.RequestException,
                ValueError,
                KeyError,
                TypeError,
            ) as error:
                print(f"{line}: import failed ({type(error).__name__})")
                failed = True

    if failed:
        raise SystemExit(1)


if __name__ == "__main__":
    main()