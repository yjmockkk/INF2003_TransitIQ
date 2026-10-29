# Import necessary libraries
import csv
import re
from pathlib import Path
from getpass import getpass
import mysql.connector


# Locate the dataset folder
project_folder = Path(__file__).resolve().parents[2]
dataset_folder = project_folder / "datasets"


# Station-code prefix -> line_code (matches LTA line codes where one exists)
PREFIX_TO_LINE = {
    "BP": "BP",
    "CC": "CCL",
    "CE": "CE",
    "CG": "CG",
    "DT": "DTL",
    "EW": "EWL",
    "NE": "NEL",
    "NS": "NSL",
    "PE": "PG", "PW": "PG", "PTC": "PG",
    "SE": "SK", "SW": "SK", "STC": "SK",
    "TE": "TEL",
}

# Line names for codes that group several station-file lines
LINE_NAME_OVERRIDE = {
    "PG": "Punggol LRT",
    "SK": "Sengkang LRT",
}


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


# Function to remove stray spaces inside Chinese names
def clean_chinese(value):
    value = clean_value(value)
    if value is None:
        return None
    return re.sub(r"\s+", "", value)


# Function to get the letter prefix of a station code (e.g. NS12 -> NS)
def get_prefix(station_code):
    match = re.match(r"^([A-Za-z]+)", station_code)
    return match.group(1).upper() if match else None


# Load the two CSV datasets
train_stations = load_csv("train/csv/train_stations.csv")
train_line_codes = load_csv("train/csv/train_lines.csv")

print("Train Stations:", len(train_stations))
print("Train Line descriptions:", len(train_line_codes))

# LTA line codes found in the line-code file (used to validate line_code values)
lta_line_codes = {
    clean_value(row.get("MRT/LRT Line"))
    for row in train_line_codes
    if clean_value(row.get("MRT/LRT Line"))
}


# Build TrainLine records from the distinct lines in the station file
lines = {}
for row in train_stations:
    code = clean_value(row.get("stn_code"))
    if code is None:
        continue

    line_code = PREFIX_TO_LINE.get(get_prefix(code))
    if line_code is None or line_code in lines:
        continue

    name_en = LINE_NAME_OVERRIDE.get(line_code, clean_value(row.get("mrt_line_english")))
    name_zh = clean_chinese(row.get("mrt_line_chinese"))
    lines[line_code] = (name_en, name_zh)

# Note line codes that are not in the LTA line-code file
for line_code in lines:
    if line_code not in lta_line_codes:
        print("Note: line code", line_code, "not in train_lines.csv")


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


    # Import TrainLine records
    insert_train_line = """
    INSERT INTO TrainLine
    (line_code, line_name_english, line_name_chinese)
    VALUES (%s, %s, %s)
    ON DUPLICATE KEY UPDATE
        line_name_english = VALUES(line_name_english),
        line_name_chinese = VALUES(line_name_chinese)
    """


    lines_processed = 0
    lines_skipped = 0
    valid_lines = set()


    for line_code, (name_en, name_zh) in lines.items():
        try:
            if name_en is None or name_zh is None:
                print("Skipping TrainLine:", line_code, "- missing name")
                lines_skipped += 1
                continue

            cursor.execute(insert_train_line, (line_code, name_en, name_zh))

            valid_lines.add(line_code)
            lines_processed += 1


        except (ValueError, mysql.connector.Error) as error:
            print("Skipping TrainLine:", line_code, error)
            lines_skipped += 1


    print("\nTrainLine records processed:", lines_processed)
    print("TrainLine records skipped:", lines_skipped)


    # Import TrainStation records
    insert_train_station = """
    INSERT INTO TrainStation
    (station_code, station_name_english, station_name_chinese)
    VALUES (%s, %s, %s)
    ON DUPLICATE KEY UPDATE
        station_name_english = VALUES(station_name_english),
        station_name_chinese = VALUES(station_name_chinese)
    """


    stations_processed = 0
    stations_skipped = 0
    valid_stations = {}


    for station in train_stations:
        try:
            station_code = clean_value(station.get("stn_code"))
            name_en = clean_value(station.get("mrt_station_english"))
            name_zh = clean_chinese(station.get("mrt_station_chinese"))

            # Station names are NOT NULL in TrainStation
            if station_code is None or name_en is None or name_zh is None:
                print("Skipping TrainStation:", station_code, "- missing value")
                stations_skipped += 1
                continue

            cursor.execute(insert_train_station, (station_code, name_en, name_zh))

            valid_stations[station_code] = PREFIX_TO_LINE.get(get_prefix(station_code))
            stations_processed += 1


        except (ValueError, mysql.connector.Error) as error:
            print("Skipping TrainStation:", station.get("stn_code"), error)
            stations_skipped += 1


    print("\nTrainStation records processed:", stations_processed)
    print("TrainStation records skipped:", stations_skipped)


    # Import StationLine records
    insert_station_line = """
    INSERT IGNORE INTO StationLine (line_code, station_code)
    VALUES (%s, %s)
    """


    links_processed = 0
    links_skipped = 0


    for station_code, line_code in valid_stations.items():
        try:
            # Check foreign-key references
            if line_code not in valid_lines:
                print(
                    "Skipping StationLine:",
                    station_code,
                    "- missing line", line_code
                )
                links_skipped += 1
                continue

            cursor.execute(insert_station_line, (line_code, station_code))
            links_processed += 1


        except (ValueError, mysql.connector.Error) as error:
            print("Skipping StationLine:", station_code, error)
            links_skipped += 1


    print("\nStationLine records processed:", links_processed)
    print("StationLine records skipped:", links_skipped)


    # Save changes
    connection.commit()
    print("\nImport completed successfully!")


    # Verify database record counts
    for table in ("TrainLine", "TrainStation", "StationLine"):
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