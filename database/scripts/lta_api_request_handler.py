import hashlib
import json
import math
import time
from email.utils import parsedate_to_datetime
from pathlib import Path

import requests

PROJECT_ROOT = Path(__file__).resolve().parents[2]
CACHE_FOLDER = PROJECT_ROOT / ".cache" / "lta"


class LtaRateLimited(requests.RequestException):
    pass


def get_wait_seconds(header, fallback):
    if not header:
        return fallback

    try:
        return max(60, int(header))
    except ValueError:
        try:
            retry_time = parsedate_to_datetime(header)
            return max(60, retry_time.timestamp() - time.time())
        except (TypeError, ValueError, OverflowError):
            return fallback


def fetch_lta(url, account_key, params=None, session=None):
    # Both importers use the same waiting period for the same key.
    key_id = hashlib.sha256(account_key.encode()).hexdigest()[:16]
    state_file = CACHE_FOLDER / f"{key_id}.json"

    state = {"retry_at": 0, "failures": 0}

    if state_file.exists():
        state = json.loads(state_file.read_text(encoding="utf-8"))

    remaining = state["retry_at"] - time.time()

    if remaining > 0:
        raise LtaRateLimited(
            f"LTA requests paused for another {math.ceil(remaining)} seconds"
        )

    client = session if session is not None else requests

    response = client.get(
        url,
        headers={
            "AccountKey": account_key,
            "Accept": "application/json",
        },
        params=params,
        timeout=20,
    )

    if response.status_code == 429:
        failures = min(state["failures"] + 1, 4)

        # Without Retry-After: wait 10, 20, 40, then 60 minutes.
        fallback = min(600 * (2 ** (failures - 1)), 3600)

        wait = get_wait_seconds(
            response.headers.get("Retry-After"),
            fallback,
        )

        CACHE_FOLDER.mkdir(parents=True, exist_ok=True)

        temporary_file = state_file.with_suffix(".tmp")
        temporary_file.write_text(
            json.dumps({
                "retry_at": time.time() + wait,
                "failures": failures,
            }),
            encoding="utf-8",
        )
        temporary_file.replace(state_file)

        response.close()

        print(
            f"LTA request limit reached. "
            f"Pausing requests for {math.ceil(wait)} seconds.",
            flush=True,
        )
        raise LtaRateLimited("LTA returned HTTP 429")

    response.raise_for_status()
    payload = response.json()

    # A successful request clears the previous rate-limit state.
    state_file.unlink(missing_ok=True)

    return payload