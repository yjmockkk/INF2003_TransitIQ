# Import necessary libraries
import csv
from pathlib import Path
from getpass import getpass
import mysql.connector

# Locate the dataset folder
project_folder = Path(__file__).resolve().parents[2]
dataset_folder = project_folder / "datasets"

# Function to read CSV files
def load_csv(filename):
    file_path = dataset_folder / filename

    with open(file_path, "r", encoding="utf-8-sig", newline="") as file:
        return list(csv.DictReader(file))

# Function to convert empty values to NULL
def clean_value(value):
    if value is None or value.strip() in ("", "-"):
        return None
    return value.strip()

# Load the three CSV datasets
bus_stops = load_csv("bus_stops.csv")
bus_services = load_csv("bus_services.csv")
bus_routes = load_csv("bus_routes.csv")

print("Bus Stops:", len(bus_stops))
print("Bus Services:", len(bus_services))
print("Bus Routes:", len(bus_routes))

# Connect to MySQL database
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

    # Import BusStop records
    insert_bus_stop = """
    INSERT INTO BusStop
    (bus_stop_code, road_name, description, latitude, longitude)
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
            cursor.execute(insert_bus_stop, (
                stop["BusStopCode"],
                stop["RoadName"],
                stop["Description"],
                stop["Latitude"],
                stop["Longitude"]
            ))

            valid_stops.add(stop["BusStopCode"])
            stops_processed += 1

        except (ValueError, mysql.connector.Error) as error:
            print("Skipping BusStop:", stop["BusStopCode"], error)
            stops_skipped += 1

    print("\nBusStop records processed:", stops_processed)
    print("BusStop records skipped:", stops_skipped)

    # Import BusService records
    insert_bus_service = """
    INSERT INTO BusService (
        service_no, direction, operator, category,
        origin_code, destination_code,
        am_peak_freq, am_offpeak_freq,
        pm_peak_freq, pm_offpeak_freq
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
            service_no = service["ServiceNo"]
            direction = int(service["Direction"])

            origin = clean_value(service["OriginCode"])
            destination = clean_value(service["DestinationCode"])

            # Check foreign-key references
            if origin not in valid_stops or destination not in valid_stops:
                print(
                    "Skipping BusService:",
                    service_no,
                    "Direction:", direction,
                    "- missing bus stop"
                )
                services_skipped += 1
                continue

            cursor.execute(insert_bus_service, (
                service_no,
                direction,
                service["Operator"],
                service["Category"],
                origin,
                destination,
                clean_value(service.get("AM_Peak_Freq")),
                clean_value(service.get("AM_Offpeak_Freq")),
                clean_value(service.get("PM_Peak_Freq")),
                clean_value(service.get("PM_Offpeak_Freq"))
            ))

            valid_services.add((service_no, direction))
            services_processed += 1

        except (ValueError, mysql.connector.Error) as error:
            print("Skipping BusService:", service.get("ServiceNo"), error)
            services_skipped += 1

    print("\nBusService records processed:", services_processed)
    print("BusService records skipped:", services_skipped)

    # Import BusRoute records
    insert_bus_route = """
    INSERT INTO BusRoute (
        service_no, direction, stop_seq, bus_stop_code,
        distance, wd_first_bus, wd_last_bus,
        sat_first_bus, sat_last_bus,
        sun_first_bus, sun_last_bus
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
            service_no = route["ServiceNo"]
            direction = int(route["Direction"])
            stop_seq = int(route["StopSequence"])
            bus_stop_code = route["BusStopCode"]
            distance = clean_value(route["Distance"])

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
                    "- missing reference"
                )
                routes_skipped += 1
                continue

            # Distance is NOT NULL in BusRoute
            if distance is None:
                print(
                    "Skipping BusRoute:",
                    service_key,
                    "Sequence:", stop_seq,
                    "- missing distance"
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

        except (ValueError, mysql.connector.Error) as error:
            print(
                "Skipping BusRoute:",
                route.get("ServiceNo"),
                route.get("StopSequence"),
                error
            )
            routes_skipped += 1

    print("\nBusRoute records processed:", routes_processed)
    print("BusRoute records skipped:", routes_skipped)

    # Save changes
    connection.commit()
    print("\nImport completed successfully!")

    # Verify database record counts
    for table in ("BusStop", "BusService", "BusRoute"):
        cursor.execute(f"SELECT COUNT(*) FROM {table}")
        total = cursor.fetchone()[0]
        print(f"{table} total database records: {total}")


except mysql.connector.Error as error:
    if connection is not None:
        connection.rollback()

    print("\nMySQL error:", error)


finally:
    # Close database connection
    if cursor is not None:
        cursor.close()

    if connection is not None and connection.is_connected():
        connection.close()

    print("Database connection closed.")
