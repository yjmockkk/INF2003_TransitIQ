"""Save complete LTA bus datasets to datasets/bus/json; does not access MySQL."""
import json
import os
import shutil
import tempfile
from datetime import datetime
from getpass import getpass
from pathlib import Path

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

# Save this script as database/scripts/retrieve_bus_data.py.
BASE_DIR = Path(__file__).resolve().parents[2]
DATASET_DIR = BASE_DIR / "datasets" / "bus" / "json"
BASE_URL = "https://datamall2.mytransport.sg/ltaodataservice"
DATASETS = ("BusStops", "BusServices", "BusRoutes")


def retrieve_dataset(session, dataset):
    records = []
    skip = 0
    previous_page = None

    while True:
        response = session.get(
            f"{BASE_URL}/{dataset}",
            params={"$skip": skip},
            timeout=(10, 60),
        )
        response.raise_for_status()
        payload = response.json()
        page = payload.get("value") if isinstance(payload, dict) else None

        if not isinstance(page, list) or not all(isinstance(row, dict) for row in page):
            raise ValueError(f"{dataset}: invalid JSON response")

        if not page:
            break

        fingerprint = json.dumps(page, sort_keys=True)
        if fingerprint == previous_page:
            raise ValueError(f"{dataset}: repeated page; stopped to avoid saving incomplete data")
        previous_page = fingerprint

        records.extend(page)
        skip += len(page)
        print(f"{dataset}: retrieved {len(records)} records", flush=True)

    if not records:
        raise ValueError(f"{dataset}: no records returned")

    return {"value": records}


def save_datasets(datasets):
    DATASET_DIR.mkdir(parents=True, exist_ok=True)
    backup_dir = DATASET_DIR / "backups" / datetime.now().strftime("%Y%m%d_%H%M%S_%f")

    for dataset, payload in datasets.items():
        destination = DATASET_DIR / f"{dataset}.json"
        temporary = None
        try:
            with tempfile.NamedTemporaryFile(
                mode="w", encoding="utf-8", dir=DATASET_DIR,
                suffix=".tmp", delete=False,
            ) as file:
                temporary = Path(file.name)
                json.dump(payload, file, ensure_ascii=False, indent=2)
                file.write("\n")

            if destination.exists():
                backup_dir.mkdir(parents=True, exist_ok=True)
                shutil.copy2(destination, backup_dir / destination.name)

            temporary.replace(destination)
            print(f"Saved {len(payload['value'])} records: {destination}")
        finally:
            if temporary is not None:
                temporary.unlink(missing_ok=True)

    if backup_dir.exists():
        print(f"Previous JSON files backed up to: {backup_dir}")


def main():
    api_key = (
        os.getenv("LTA_API_KEY") or os.getenv("LTA_ACCOUNT_KEY")
        or getpass("LTA DataMall Account Key: ")
    ).strip()
    if not api_key:
        raise ValueError("An LTA DataMall Account Key is required")

    retry = Retry(
        total=3, backoff_factor=1,
        status_forcelist=(429, 500, 502, 503, 504),
        allowed_methods=("GET",), respect_retry_after_header=True,
    )

    with requests.Session() as session:
        session.headers.update({"AccountKey": api_key, "Accept": "application/json"})
        session.mount("https://", HTTPAdapter(max_retries=retry))

        # Download every dataset successfully before replacing any saved files.
        datasets = {
            dataset: retrieve_dataset(session, dataset)
            for dataset in DATASETS
        }

    save_datasets(datasets)
    print("Download complete. MySQL has not been changed.")


if __name__ == "__main__":
    try:
        main()
    except (requests.RequestException, ValueError, OSError) as error:
        raise SystemExit(f"Download failed: {error}")
