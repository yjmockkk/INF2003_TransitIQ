import os
from datetime import datetime, timezone

import requests

from mongo_db import connect_database
from lta_api_request_handler import fetch_lta

URL = (
    "https://datamall2.mytransport.sg/"
    "ltaodataservice/v3/BusArrival"
)

# Bus interchanges spread across Singapore
BUS_STOPS = {
    "46009": "Woodlands Int",
    "54009": "Ang Mo Kio Int",
    "67009": "Sengkang Int",
    "75009": "Tampines Int",
    "52009": "Toa Payoh Int",
    "22009": "Boon Lay Int",
    "14009": "HarbourFront Int",
}


def parse_bus(bus, fetched_at):
    # NextBus2 and NextBus3 are blank when no more buses are coming
    if not bus or not bus.get("EstimatedArrival"):
        return None

    arrival = datetime.fromisoformat(bus["EstimatedArrival"])
    arrival = arrival.astimezone(timezone.utc)

    return {
        "estimated_arrival": arrival,
        "minutes_away": round(
            (arrival - fetched_at).total_seconds() / 60, 1
        ),
        "load": bus.get("Load"),
        "bus_type": bus.get("Type"),
        "wheelchair_accessible": bus.get("Feature") == "WAB",
        "monitored": bus.get("Monitored") == 1,
    }


def import_stop(db, session, key, stop_code):
    payload = fetch_lta(
        URL,
        key,
        params={"BusStopCode": stop_code},
        session=session,
    )

    fetched_at = datetime.now(timezone.utc)
    services = []

    for service in payload.get("Services", []):
        next_buses = []

        for slot in ("NextBus", "NextBus2", "NextBus3"):
            bus = parse_bus(service.get(slot), fetched_at)

            if bus is not None:
                next_buses.append(bus)

        services.append({
            "service_no": service["ServiceNo"],
            "operator": service["Operator"],
            "next_buses": next_buses,
        })

    # One document per bus stop per fetch
    db.BusArrival.insert_one({
        "bus_stop_code": stop_code,
        "bus_stop_name": BUS_STOPS[stop_code],
        "fetched_at": fetched_at,
        "service_count": len(services),
        "services": services,
        "source": "LTA DataMall",
    })

    print(
        f"{stop_code} ({BUS_STOPS[stop_code]}): "
        f"{len(services)} services saved",
        flush=True,
    )


def main():
    key = os.getenv("LTA_ACCOUNT_KEY", "").strip()

    if not key:
        raise SystemExit("Missing LTA_ACCOUNT_KEY in backend/.env")

    failed = False

    with connect_database() as db, requests.Session() as session:
        # Speeds up "latest arrivals at a stop" and history queries
        db.BusArrival.create_index(
            [("bus_stop_code", 1), ("fetched_at", -1)],
            name="stop_history",
        )

        for stop_code in BUS_STOPS:
            try:
                import_stop(db, session, key, stop_code)

            except (
                requests.RequestException,
                ValueError,
                KeyError,
                TypeError,
            ) as error:
                print(
                    f"{stop_code}: import failed ({type(error).__name__})",
                    flush=True,
                )
                failed = True

    if failed:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
