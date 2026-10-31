import hashlib
import json
import os
from datetime import datetime, timezone

import requests

from mongo_db import connect_database
from lta_api_request_handler import fetch_lta

URL = (
    "https://datamall2.mytransport.sg/"
    "ltaodataservice/TrainServiceAlerts"
)


def import_alerts(db, session, key):
    response_data = fetch_lta(
        URL,
        key,
        session=session,
    )

    payload = response_data["value"]

    if not isinstance(payload, dict):
        raise ValueError("Unexpected train service response")

    status = str(payload.get("Status"))

    if status not in ("1", "2"):
        raise ValueError("Unexpected train service status")

    # Compare the complete service-status content.
    fingerprint = hashlib.sha256(
        json.dumps(
            payload,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
        ).encode("utf-8")
    ).hexdigest()

    fetched_at = datetime.now(timezone.utc)

    latest = db.TrainServiceAlert.find_one(
        {"fingerprint": {"$exists": True}},
        sort=[("fetched_at", -1)],
    )

    if latest and latest["fingerprint"] == fingerprint:
        db.TrainServiceAlert.update_one(
            {"_id": latest["_id"]},
            {"$max": {"last_seen_at": fetched_at}},
        )

        print(
            "Train alerts: response unchanged; "
            "last confirmed time updated",
            flush=True,
        )

    else:
        db.TrainServiceAlert.insert_one({
            "source": "LTA DataMall",
            "status": status,
            "payload": payload,
            "fingerprint": fingerprint,
            "fetched_at": fetched_at,
            "last_seen_at": fetched_at,
        })

        print(
            "Train alerts: new service-status snapshot saved",
            flush=True,
        )


def main():
    key = os.getenv("LTA_ACCOUNT_KEY", "").strip()

    if not key:
        raise SystemExit("Missing LTA_ACCOUNT_KEY in backend/.env")

    with connect_database() as db, requests.Session() as session:
        try:
            import_alerts(db, session, key)

        except (
            requests.RequestException,
            ValueError,
            KeyError,
            TypeError,
        ) as error:
            print(
                f"Train alerts: import failed "
                f"({type(error).__name__})",
                flush=True,
            )
            raise SystemExit(1)


if __name__ == "__main__":
    main()