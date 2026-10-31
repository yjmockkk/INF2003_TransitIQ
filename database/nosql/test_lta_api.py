# Test that the LTA DataMall Bus Arrival API key works
import os
import sys
from datetime import datetime
from pathlib import Path

import requests
from dotenv import load_dotenv

# Load the .env file from the project root
project_folder = Path(__file__).resolve().parents[2]
load_dotenv(project_folder / ".env")

API_KEY = os.getenv("LTA_ACCOUNT_KEY")
URL = "https://datamall2.mytransport.sg/ltaodataservice/v3/BusArrival"

if not API_KEY:
    raise SystemExit("LTA_ACCOUNT_KEY not found. Check that it is in your .env file.")

# Use the bus stop code given on the command line, or LTA's sample stop
bus_stop_code = sys.argv[1] if len(sys.argv) > 1 else "83139"

try:
    response = requests.get(
        URL,
        headers={"AccountKey": API_KEY, "accept": "application/json"},
        params={"BusStopCode": bus_stop_code},
        timeout=15
    )
except requests.RequestException as error:
    raise SystemExit(f"Could not reach LTA DataMall: {error}")

if response.status_code != 200:
    raise SystemExit(f"Request failed with status {response.status_code}: {response.text[:200]}")

data = response.json()
services = data.get("Services", [])

if not services:
    print(f"Bus stop {bus_stop_code}: no arrival data (buses may not be in operation now).")
    raise SystemExit()

print(f"Bus stop {data.get('BusStopCode', bus_stop_code)}: {len(services)} services with arrival data\n")

now = datetime.now().astimezone()

for service in services:
    arrivals = []

    for key in ("NextBus", "NextBus2", "NextBus3"):
        bus = service.get(key) or {}
        eta_text = bus.get("EstimatedArrival")

        # NextBus2 and NextBus3 can be blank, e.g. late at night
        if not eta_text:
            continue

        # LTA advises rounding down to the nearest minute, and showing "Arr" under 1 minute
        eta = datetime.fromisoformat(eta_text)
        minutes = int((eta - now).total_seconds() // 60)
        label = "Arr" if minutes < 1 else f"{minutes} min"

        arrivals.append(f"{label} ({bus.get('Load')}, {bus.get('Type')})")

    print(f"  {service['ServiceNo']:>5}  {service['Operator']:<5} " + " | ".join(arrivals))
