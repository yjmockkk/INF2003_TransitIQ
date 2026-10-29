import hashlib
import json
import os
from datetime import datetime, timezone

import requests

from mongo_db import connect_database

URL = (
    "https://datamall2.mytransport.sg/"
    "ltaodataservice/TrainServiceAlerts"
)


def main():
    key = os.getenv("LTA_ACCOUNT_KEY")
    if not key:
        raise SystemExit("Missing LTA_ACCOUNT_KEY in backend/.env")

    with connect_database() as db:
        response = requests.get(
            URL,
            headers={
                "AccountKey": key,
                "Accept": "application/json",
            },
            timeout=20,
        )
        response.raise_for_status()

        payload = response.json()["value"]

        if (
            not isinstance(payload, dict)
            or str(payload.get("Status")) not in ("1", "2")
        ):
            raise ValueError("Unexpected train service response")

        fingerprint = hashlib.sha256(
            json.dumps(
                payload,
                sort_keys=True,
                separators=(",", ":"),
            ).encode()
        ).hexdigest()

        now = datetime.now(timezone.utc)

        latest = db.TrainServiceAlert.find_one(
            {"fingerprint": {"$exists": True}},
            sort=[("fetched_at", -1)],
        )

        if latest and latest["fingerprint"] == fingerprint:
            db.TrainServiceAlert.update_one(
                {"_id": latest["_id"]},
                {"$max": {"last_seen_at": now}},
            )
            print("Service status unchanged; last confirmed time updated.")
        else:
            db.TrainServiceAlert.insert_one({
                "source": "LTA DataMall",
                "status": str(payload["Status"]),
                "payload": payload,
                "fingerprint": fingerprint,
                "fetched_at": now,
                "last_seen_at": now,
            })
            print("New service-status snapshot saved.")


if __name__ == "__main__":
    main()