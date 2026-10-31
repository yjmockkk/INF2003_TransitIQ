import os
from datetime import datetime, timezone

import requests

from mongo_db import connect_database
from lta_api_request_handler import fetch_lta

URL = (
    "https://datamall2.mytransport.sg/"
    "ltaodataservice/PCDRealTime"
)

TRAIN_LINES = [
    "CCL", "CEL", "CGL", "DTL", "EWL", "NEL",
    "NSL", "BPL", "SLRT", "PLRT", "TEL",
]

def parse_date(value):
    if not isinstance(value, str):
        raise ValueError("LTA timestamp must be a string")

    date = datetime.fromisoformat(value.replace("Z", "+00:00"))

    if date.tzinfo is None:
        raise ValueError("LTA timestamp has no timezone")

    return date.astimezone(timezone.utc)

def import_line(db, session, key, line):
    payload = fetch_lta(
        URL,
        key,
        params={"TrainLine": line},
        session=session,
    )

    rows = payload["value"]

    if not isinstance(rows, list):
        raise ValueError("Unexpected crowd response")

    fetched_at = datetime.now(timezone.utc)
    documents = []

    # Validate all observations before writing this response.
    for row in rows:
        start = parse_date(row["StartTime"])
        end = parse_date(row["EndTime"])
        station = row["Station"]
        level = row["CrowdLevel"]

        if end <= start:
            raise ValueError("Invalid observation window")

        if not isinstance(station, str) or not station:
            raise ValueError("Invalid station code")

        if level not in ("l", "m", "h", "NA"):
            raise ValueError("Unexpected crowd level")

        documents.append({
            "line_code": line,
            "station_code": station,
            "start_time": start,
            "end_time": end,
            "crowd_level": level,
            "source": "LTA DataMall",
            "fetched_at": fetched_at,
        })

    inserted = 0
    changed = 0
    unchanged = 0

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

        previous = db.StationCrowdDensity.find_one(
            unique_key,
            {"crowd_level": 1},
        )

        result = db.StationCrowdDensity.update_one(
            unique_key,
            {
                "$set": document,
                "$setOnInsert": {
                    "first_fetched_at": fetched_at,
                },
            },
            upsert=True,
        )

        if result.upserted_id is not None:
            inserted += 1
        elif (
            previous is not None
            and previous.get("crowd_level") == document["crowd_level"]
        ):
            unchanged += 1
        else:
            changed += 1

    print(
        f"{line}: {inserted} new, "
        f"{changed} changed, "
        f"{unchanged} unchanged",
        flush=True,
    )

def main():
    key = os.getenv("LTA_ACCOUNT_KEY", "").strip()

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
                print(
                    f"{line}: import failed ({type(error).__name__})",
                    flush=True,
                )
                failed = True

    if failed:
        raise SystemExit(1)


if __name__ == "__main__":
    main()