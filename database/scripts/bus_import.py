# Import necessary libraries
import json
from pathlib import Path
from decimal import Decimal, InvalidOperation
from getpass import getpass
import mysql.connector

# Locate local bus JSON sample datasets
BASE_DIR = Path(__file__).resolve().parents[2]
DATASET_DIR = BASE_DIR / "datasets" / "bus" / "json"


# Retrieve datasets from local sample files
def load_sample_data(filename):
    file_path = DATASET_DIR / filename

    with open(file_path, "r", encoding="utf-8-sig") as file:
        data = json.load(file)

    if isinstance(data, dict):
        data = data.get("value")

    if not isinstance(data, list):
        raise ValueError(f"Invalid dataset format: {filename}")

    if not data:
        raise ValueError(f"No records found in {filename}")

    if not all(isinstance(record, dict) for record in data):
        raise ValueError(f"Invalid records in {filename}")

    print(f"{filename}: loaded {len(data)} records")

    return data

# Convert empty values to SQL NULL
def clean_value(value):
    if value is None:
        return None

    value = str(value).strip()

    if value in ("", "-"):
        return None

    return value

# Validate numeric values
def clean_number(value):
    value = clean_value(value)

    if value is None:
        return None

    try:
        number = Decimal(value)

        if not number.is_finite():
            return None

        return number

    except InvalidOperation:
        return None

# Retrieve sample datasets before connecting to MySQL
try:
    print("\n=== Loading Local Sample Datasets ===")

    bus_stops = load_sample_data("BusStops.json")
    bus_services = load_sample_data("BusServices.json")
    bus_routes = load_sample_data("BusRoutes.json")

except (OSError, ValueError) as error:
    raise SystemExit(f"Sample data error: {error}")

print("\n=== Local Sample Data ===")
print("Bus Stops:", len(bus_stops))
print("Bus Services:", len(bus_services))
print("Bus Routes:", len(bus_routes))

# Connect to MySQL
connection = None
cursor = None

try:
    connection = mysql.connector.connect(
        host="localhost",
        port=3306,
        user="root",
        password=getpass("MySQL password: "),
        database="Transitiq"
    )

    cursor = connection.cursor()
    print("\nConnected to MySQL!")

    # Start with fresh bus data for each import
    print("\n=== Clearing Existing Bus Data ===")
    connection.start_transaction()

    cursor.execute("DELETE FROM BusRoute")
    cursor.execute("DELETE FROM BusService")
    cursor.execute("DELETE FROM BusStop")

    print("Existing bus records cleared.")

    # Import BusStop records
    print("\n=== Sample Data: BusStop ===")

    insert_bus_stop = """
    INSERT INTO BusStop (
        bus_stop_code,
        road_name,
        description,
        latitude,
        longitude
    )
    VALUES (%s, %s, %s, %s, %s)
    ON DUPLICATE KEY UPDATE
        road_name = VALUES(road_name),
        description = VALUES(description),
        latitude = VALUES(latitude),
        longitude = VALUES(longitude)
    """

    stops_processed = 0
    stops_skipped = 0
    valid_stops = set()

    for stop in bus_stops:
        try:
            stop_code = clean_value(stop.get("BusStopCode"))
            road_name = clean_value(stop.get("RoadName"))
            description = clean_value(stop.get("Description"))
            latitude = clean_number(stop.get("Latitude"))
            longitude = clean_number(stop.get("Longitude"))

            # Check required values and identify missing fields
            required_fields = {
                "BusStopCode": stop_code,
                "RoadName": road_name,
                "Description": description,
                "Latitude": latitude,
                "Longitude": longitude
            }

            missing_fields = [
                field for field, value in required_fields.items()
                if value is None
            ]

            if missing_fields:
                print(
                    "Skipping BusStop:",
                    stop_code,
                    "- missing fields:",
                    ", ".join(missing_fields)
                )
                stops_skipped += 1
                continue

            if not (-90 <= latitude <= 90):
                raise ValueError("Latitude must be between -90 and 90")

            if not (-180 <= longitude <= 180):
                raise ValueError("Longitude must be between -180 and 180")

            cursor.execute(insert_bus_stop, (
                stop_code,
                road_name,
                description,
                latitude,
                longitude
            ))

            valid_stops.add(stop_code)
            stops_processed += 1

        except ValueError as error:
            print("Skipping BusStop:", stop.get("BusStopCode"), error)
            stops_skipped += 1

        except mysql.connector.Error as error:
            print("BusStop import failed:", stop.get("BusStopCode"), error)
            raise

    print("Records inserted or updated:", stops_processed)
    print("Records skipped:", stops_skipped)

    # Import BusService records
    print("\n=== Sample Data: BusService ===")

    insert_bus_service = """
    INSERT INTO BusService (
        service_no,
        direction,
        operator,
        category,
        origin_code,
        destination_code,
        am_peak_freq,
        am_offpeak_freq,
        pm_peak_freq,
        pm_offpeak_freq
    )
    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
    ON DUPLICATE KEY UPDATE
        operator = VALUES(operator),
        category = VALUES(category),
        origin_code = VALUES(origin_code),
        destination_code = VALUES(destination_code),
        am_peak_freq = VALUES(am_peak_freq),
        am_offpeak_freq = VALUES(am_offpeak_freq),
        pm_peak_freq = VALUES(pm_peak_freq),
        pm_offpeak_freq = VALUES(pm_offpeak_freq)
    """

    services_processed = 0
    services_skipped = 0
    valid_services = set()

    for service in bus_services:
        try:
            service_no = clean_value(service.get("ServiceNo"))
            direction_value = clean_value(service.get("Direction"))
            operator = clean_value(service.get("Operator"))
            category = clean_value(service.get("Category"))
            origin = clean_value(service.get("OriginCode"))
            destination = clean_value(service.get("DestinationCode"))

            # Check required values and identify missing fields
            required_fields = {
                "ServiceNo": service_no,
                "Direction": direction_value,
                "Operator": operator,
                "Category": category,
                "OriginCode": origin,
                "DestinationCode": destination
            }

            missing_fields = [
                field for field, value in required_fields.items()
                if value is None
            ]

            if missing_fields:
                print(
                    "Skipping BusService:",
                    service_no,
                    "- missing fields:",
                    ", ".join(missing_fields)
                )
                services_skipped += 1
                continue

            direction = int(direction_value)

            if direction not in (1, 2):
                raise ValueError("Direction must be 1 or 2")

            # Check foreign-key references
            if (
                origin not in valid_stops
                or destination not in valid_stops
            ):
                print(
                    "Skipping BusService:",
                    service_no,
                    "Direction:", direction,
                    "- missing origin or destination bus stop"
                )
                services_skipped += 1
                continue

            cursor.execute(insert_bus_service, (
                service_no,
                direction,
                operator,
                category,
                origin,
                destination,
                clean_value(service.get("AM_Peak_Freq")),
                clean_value(service.get("AM_Offpeak_Freq")),
                clean_value(service.get("PM_Peak_Freq")),
                clean_value(service.get("PM_Offpeak_Freq"))
            ))

            valid_services.add((service_no, direction))
            services_processed += 1

        except ValueError as error:
            print("Skipping BusService:", service.get("ServiceNo"), error)
            services_skipped += 1

        except mysql.connector.Error as error:
            print("BusService import failed:", service.get("ServiceNo"), error)
            raise

    print("Records inserted or updated:", services_processed)
    print("Records skipped:", services_skipped)

    # Import BusRoute records
    print("\n=== Sample Data: BusRoute ===")

    insert_bus_route = """
    INSERT INTO BusRoute (
        service_no,
        direction,
        stop_seq,
        bus_stop_code,
        distance,
        wd_first_bus,
        wd_last_bus,
        sat_first_bus,
        sat_last_bus,
        sun_first_bus,
        sun_last_bus
    )
    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
    ON DUPLICATE KEY UPDATE
        bus_stop_code = VALUES(bus_stop_code),
        distance = VALUES(distance),
        wd_first_bus = VALUES(wd_first_bus),
        wd_last_bus = VALUES(wd_last_bus),
        sat_first_bus = VALUES(sat_first_bus),
        sat_last_bus = VALUES(sat_last_bus),
        sun_first_bus = VALUES(sun_first_bus),
        sun_last_bus = VALUES(sun_last_bus)
    """

    routes_processed = 0
    routes_skipped = 0

    for route in bus_routes:
        try:
            service_no = clean_value(route.get("ServiceNo"))
            direction_value = clean_value(route.get("Direction"))
            sequence_value = clean_value(route.get("StopSequence"))
            bus_stop_code = clean_value(route.get("BusStopCode"))
            distance = clean_number(route.get("Distance"))

            # Check required values and identify missing fields
            required_fields = {
                "ServiceNo": service_no,
                "Direction": direction_value,
                "StopSequence": sequence_value,
                "BusStopCode": bus_stop_code,
                "Distance": distance
            }

            missing_fields = [
                field for field, value in required_fields.items()
                if value is None
            ]

            if missing_fields:
                print(
                    "Skipping BusRoute:",
                    service_no,
                    "- missing fields:",
                    ", ".join(missing_fields)
                )
                routes_skipped += 1
                continue

            direction = int(direction_value)

            if direction not in (1, 2):
                raise ValueError("Direction must be 1 or 2")
            stop_seq = int(sequence_value)

            if stop_seq < 1:
                raise ValueError("StopSequence must be at least 1")

            if distance < 0:
                raise ValueError("Distance cannot be negative")

            service_key = (service_no, direction)

            # Check foreign-key references
            if (
                service_key not in valid_services
                or bus_stop_code not in valid_stops
            ):
                print(
                    "Skipping BusRoute:",
                    service_key,
                    "Stop:", bus_stop_code,
                    "- missing service or bus stop reference"
                )
                routes_skipped += 1
                continue

            cursor.execute(insert_bus_route, (
                service_no,
                direction,
                stop_seq,
                bus_stop_code,
                distance,
                clean_value(route.get("WD_FirstBus")),
                clean_value(route.get("WD_LastBus")),
                clean_value(route.get("SAT_FirstBus")),
                clean_value(route.get("SAT_LastBus")),
                clean_value(route.get("SUN_FirstBus")),
                clean_value(route.get("SUN_LastBus"))
            ))

            routes_processed += 1

        except ValueError as error:
            print(
                "Skipping BusRoute:",
                route.get("ServiceNo"),
                route.get("StopSequence"),
                error
            )
            routes_skipped += 1

        except mysql.connector.Error as error:
            print(
                "BusRoute import failed:",
                route.get("ServiceNo"),
                route.get("StopSequence"),
                error
            )
            raise

    print("Records inserted or updated:", routes_processed)
    print("Records skipped:", routes_skipped)

    # Save changes
    connection.commit()

    print("\n=== Import Completed ===")
    print(
        "Total records processed:",
        stops_processed + services_processed + routes_processed
    )
    print(
        "Total records skipped:",
        stops_skipped + services_skipped + routes_skipped
    )

    # Verify database counts
    print("\n=== Current MySQL Database Totals ===")

    for table in ("BusStop", "BusService", "BusRoute"):
        cursor.execute(f"SELECT COUNT(*) FROM {table}")
        total = cursor.fetchone()[0]
        print(f"{table}: {total} total rows")

except Exception:
    if connection is not None and connection.is_connected():
        connection.rollback()
    raise

finally:
    if cursor is not None:
        cursor.close()

    if connection is not None and connection.is_connected():
        connection.close()

    print("Database connection closed.")
