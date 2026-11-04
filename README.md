# INF2003_TransitIQ

Repository for the INF2003 Database Systems group project.

TransitIQ organises Singapore bus and train information. Structured reference data (bus stops, services, routes, train stations and lines) is stored in **MySQL**. Time-based operational data (station crowd density and train service alerts) is stored in **MongoDB**. A **Flask** backend exposes the data as JSON endpoints, and includes a test page for checking every query.

## Contents

1. [Overview](#1-overview)
2. [Prerequisites](#2-prerequisites)
3. [Install the Python packages](#3-install-the-python-packages)
4. [Configure `.env` and the LTA API key](#4-configure-env-and-the-lta-api-key)
5. [Set up MySQL](#5-set-up-mysql)
6. [Set up MongoDB](#6-set-up-mongodb)
7. [Run the app](#7-run-the-app)
8. [API reference](#8-api-reference)
9. [Troubleshooting](#9-troubleshooting)

---

## 1. Overview

| Component | Technology | Holds |
|---|---|---|
| Relational database | MySQL 8.0, database `Transitiq` | `BusStop`, `BusService`, `BusRoute`, `TrainLine`, `TrainStation`, `StationLine`, `StationConnection` |
| NoSQL database | MongoDB, database `TransitIQ` | `StationCrowdDensity`, `TrainServiceAlert` |
| Backend | Flask (`backend/`) | JSON API over the databases, plus an API test page |
| Frontend | `frontend/templates`, `frontend/static` | Web pages and the API tester |

### Repository layout

| Folder | Contents |
|---|---|
| `backend/` | Flask app, routes, database connection code, `.env.example` |
| `database/sql/` | MySQL scripts (database creation, schema, views) |
| `database/nosql/` | MongoDB design files |
| `database/scripts/` | Python import scripts (`bus_import.py`, `train_import.py`, `density_import.py`, `alerts_import.py`) |
| `datasets/` | Train CSV and Excel datasets |
| `frontend/` | `templates/` and `static/` |

### Setup at a glance

Do these in order. Each step is explained in the sections below.

1. Install the Python packages (section 3).
2. Create `backend/.env` and get an LTA API key (section 4).
3. Create the MySQL database and tables, then run the bus and train imports (section 5).
4. Create the train views and fill `StationConnection` (section 5.5).
5. Install MongoDB, then run the two NoSQL imports (section 6).
6. Start the Flask server (section 7).

---

## 2. Prerequisites

- Python 3 installed
- MySQL Server 8.0 installed and running locally
- MySQL Workbench or DBeaver (or another MySQL client)
- MongoDB Community Server and MongoDB Compass (see section 6)
- An LTA DataMall API key (see section 4)
- The train CSV datasets present in `datasets/train/csv/`

---

## 3. Install the Python packages

From the project root, run:

```
pip install -r requirements.txt
```

This installs the packages the project uses: Flask, `mysql-connector-python`, `python-dotenv`, `requests` and `pymongo`. If you use a virtual environment, activate it first.

If any package is reported as missing, install it directly with the same Python that runs the scripts:

```
python -m pip install flask mysql-connector-python python-dotenv requests pymongo
```

To confirm the install worked:

```
python -c "import flask, mysql.connector, dotenv, requests, pymongo; print('ok')"
```

---

## 4. Configure `.env` and the LTA API key

### 4.1 Create your own `.env` file

The `.env` file stores **your own** database login details. It is not included in the repository, so each member must create it on their own computer. Do not copy another member's `.env`, because the password, port and username may not match your setup.

1. In `backend/`, make a copy of `.env.example` and name the copy `.env`. You should now have both files side by side.
2. Open `.env` and fill in each value with the details of **your own** servers:

```
# MySQL (used by the Flask backend)
DB_HOST=your_host
DB_PORT=your_port
DB_USER=your_user
DB_PASSWORD=your_mysql_password
DB_NAME=Transitiq

# MongoDB (used by the NoSQL import scripts)
MONGO_URI=mongodb://localhost:27017/
MONGO_DB=TransitIQ
LTA_ACCOUNT_KEY=your_actual_key
```

Replace `your_actual_key` with your LTA Account Key.

If you change `.env` while the server is running, stop the server with `Ctrl+C` and start it again.

To find your MySQL port, run this in MySQL Workbench:

```sql
SELECT @@port, VERSION();
```

The version should say `8.0.x`. If it says MariaDB, you are connected to the wrong server.

### 4.2 Get an LTA DataMall API key

1. Go to [LTA DataMall](https://datamall.lta.gov.sg/) and request API access at [https://datamall.lta.gov.sg/content/datamall/en/request-for-api.html](https://datamall.lta.gov.sg/content/datamall/en/request-for-api.html).
2. Register and obtain your Account Key.
3. Keep the key private.

The same key is used in two places:

| Used by | How to provide it |
|---|---|
| `bus_import.py` (MySQL bus data) | `LTA_API_KEY` environment variable in the terminal (see below) |
| `density_import.py`, `alerts_import.py` (MongoDB data) | `LTA_ACCOUNT_KEY` in `backend/.env` (see 4.1) |

To set the key for `bus_import.py`, open a terminal in the project root.

For macOS/Linux:

```
export LTA_API_KEY='YOUR_LTA_API_KEY'
```

For Windows PowerShell:

```
$env:LTA_API_KEY = "YOUR_LTA_API_KEY"
```

Replace `YOUR_LTA_API_KEY` with your actual key. Important notes:

- The key must be set in the same terminal session that runs `bus_import.py`.
- When you open a new terminal session, you may need to set it again.
- The importer needs an internet connection to retrieve LTA data.

---

## 5. Set up MySQL

Two Python scripts populate the `Transitiq` MySQL database with bus and train information:

| Script | Tables populated | Dataset source |
|---|---|---|
| `bus_import.py` | `BusStop`, `BusService`, `BusRoute` | LTA DataMall API (Bus Stops, Bus Services and Bus Routes) |
| `train_import.py` | `TrainLine`, `TrainStation`, `StationLine` | `datasets/train/csv/` (converted from the original Excel datasets) |

### Data sources

**Bus datasets.** The bus datasets are retrieved directly from Singapore's Land Transport Authority (LTA) DataMall API using an API key. The three datasets used are:

- **Bus Stops:** bus stop codes, road names, descriptions and geographical coordinates.
- **Bus Services:** bus service numbers, directions, operators, categories, origins, destinations and frequency information.
- **Bus Routes:** the sequence of bus stops along each service, route distances and first/last bus timings.

Initially, limited JSON samples from LTA DataMall were used to examine the dataset structures. These samples were insufficient for populating the relational database, so the implementation was updated to retrieve the complete datasets directly through the LTA DataMall API. The import script retrieves them using API pagination and populates the MySQL tables.

**Train datasets.** The original train datasets were provided in Excel format (`Train-Station-Codes-and-Chinese-Names.xls` and `Train-Line-Codes.xlsx`). They were converted into CSV format to make importing the station and line information into MySQL easier.

### 5.1 Create the database and tables

The import scripts do not create tables. They must exist before either script runs.

1. Open MySQL Workbench or DBeaver and connect to your local MySQL server.
2. Execute `database/sql/create_database.sql` to create the `Transitiq` database.
3. Run the table definitions from the schema files in `database/sql/`, for both the bus tables and the train tables (`train_schema.sql`).
4. Verify that the tables were created:

```sql
USE Transitiq;

SHOW TABLES;
```

The database should contain these seven tables:

- `BusStop`
- `BusService`
- `BusRoute`
- `TrainLine`
- `TrainStation`
- `StationLine`
- `StationConnection`

`StationConnection` is created empty by `train_schema.sql`. It stores a copy of the station-to-station connections defined by the view `v_name_graph`, so route lookups are fast. It is filled in section 5.5, after the train data has been imported.

### 5.2 Verify the train dataset files

Ensure that the following train datasets are available:

```
datasets/train/csv/
├── train_stations.csv
└── train_lines.csv

datasets/train/excel/
├── Train Station Codes and Chinese Names.xlsx
└── Train Line Codes.xlsx
```

CSV files must be saved as **CSV UTF-8 (Comma delimited)** so that special characters and Chinese station names load correctly.

The bus import script does not need local CSV or JSON files, because it retrieves the bus datasets directly from LTA DataMall.

### 5.3 Check the MySQL connection settings in the import scripts

The import scripts use these local database settings:

```
host="localhost"
port=3306
user="root"
database="Transitiq"
```

**Change `host`, `port` or `user` in the scripts if your MySQL setup differs.** The password is requested when a script runs, so it is never stored in the file.

These settings are separate from `backend/.env`, which is used by the Flask backend. Make sure both point at the same MySQL server.

### 5.4 Run the import scripts

From the project root, with the LTA API key set (section 4.2), run:

```
python database/scripts/bus_import.py
python database/scripts/train_import.py
```

Enter your MySQL password when prompted each time. The bus and train scripts populate separate tables and can be run in either order.

#### Bus import process

The bus import script performs these operations:

1. Authenticates with LTA DataMall using the API key.
2. Retrieves the complete Bus Stops, Bus Services and Bus Routes datasets using `$skip` pagination, with up to 500 records per request.
3. Connects to the `Transitiq` MySQL database.
4. Clears the existing records from the three bus tables, in the order `BusRoute`, `BusService`, `BusStop`.
5. Imports the retrieved records in the order `BusStop`, `BusService`, `BusRoute`.
6. Validates mandatory fields, numeric values and foreign-key references before insertion.
7. Skips records that fail validation and displays the reasons.
8. Commits the imported data and displays the final database row counts.

The import order is important because `BusService` references `BusStop`, while `BusRoute` references both `BusService` and `BusStop`. The script uses `ON DUPLICATE KEY UPDATE` to handle records with existing primary keys.

**Important:** each run performs a fresh import by clearing and repopulating the bus tables. Any existing bus records, including manually added test data, will be removed. Back up important data before running the script. The train tables are not intentionally cleared by the bus importer.

#### Bus import results

These results were obtained from a successful LTA DataMall API import:

| Table | Source records | Records processed | Records skipped |
|---|---|---|---|
| `BusStop` | 5209 | 5209 | 0 |
| `BusService` | 804 | 801 | 3 |
| `BusRoute` | 26946 | 26946 | 0 |
| Total | 32959 | 32956 | 3 |

Three bus services (291, 293 and 307) were skipped because the API returned missing `OriginCode` and `DestinationCode` values. These records could not satisfy the `NOT NULL` and foreign-key constraints defined in the `BusService` table.

The final MySQL row counts after the fresh import were:

```
BusStop: 5209 total rows
BusService: 801 total rows
BusRoute: 26946 total rows
```

The source record counts may change when the LTA datasets are updated.

#### Train import process

`train_import.py` reads the converted train CSV datasets and populates the `TrainLine`, `TrainStation` and `StationLine` tables. The expected output is:

```
TrainLine records processed: 11
TrainStation records processed: 213
StationLine records processed: 213
Import completed successfully!
```

Check these counts against the actual output when you run the script. Both scripts can be run again safely: existing rows are updated rather than duplicated.

### 5.5 Create the train views and fill `StationConnection`

Do this after the train import in section 5.4, because the views read the imported train tables.

1. Execute `database/sql/train_view.sql` in MySQL Workbench or DBeaver. This creates the train views (including `v_name_graph`, which defines the station-to-station connections), then empties `StationConnection` and refills it from `v_name_graph`.
2. Check that the table was filled and matches the view:

```sql
USE Transitiq;

SELECT COUNT(*) FROM v_name_graph;
SELECT COUNT(*) FROM StationConnection;
```

Both counts should be the same and greater than zero. If both are 0, the train import has not run yet. Run it, then run `train_view.sql` again.

#### When the train data changes

`StationConnection` is a stored copy, so it is not updated automatically. If station data changes (stations added, edited or deleted, or the train import is re-run with different data), re-run `train_view.sql` to refresh it. The file can be run any number of times.

Changes that do not affect station names, codes or lines (for example, renaming a line) do not require a refresh.

The train route queries in the API read from `StationConnection`. If it is empty, route requests return no results.

### 5.6 Verify the MySQL import

After running both import scripts and `train_view.sql`, execute these queries in MySQL Workbench or DBeaver:

```sql
USE Transitiq;

-- Bus tables
SELECT COUNT(*) AS total_bus_stops FROM BusStop;
SELECT COUNT(*) AS total_bus_services FROM BusService;
SELECT COUNT(*) AS total_bus_routes FROM BusRoute;

-- Train tables
SELECT COUNT(*) AS total_train_lines FROM TrainLine;
SELECT COUNT(*) AS total_train_stations FROM TrainStation;
SELECT COUNT(*) AS total_station_lines FROM StationLine;

-- Train route table
SELECT COUNT(*) AS total_station_connections FROM StationConnection;
```

- The bus table counts should reflect the successfully imported LTA records after the fresh import. Counts may differ from the API source totals if records are skipped due to missing values, foreign-key constraints or duplicate primary keys.
- `StationConnection` should have the same number of rows as `v_name_graph`.
- The bus import can be re-run to refresh the bus data from LTA DataMall. The API key and an internet connection must be available whenever the script retrieves new data.

---

## 6. Set up MongoDB

MongoDB stores the time-based operational data: station crowd density and train service alerts.

### 6.1 Install MongoDB

1. Download [MongoDB Community Server](https://www.mongodb.com/try/download/community).
2. Choose Windows, then MSI.
3. Run the installer and select **Complete**.
4. Keep **Install MongoD as a Service** checked.
5. Install MongoDB Compass when offered.

Open Compass and connect using:

```
mongodb://localhost:27017
```

**Do not create the database or collections manually. The import scripts create them.**

### 6.2 Check your settings

The NoSQL scripts read `MONGO_URI`, `MONGO_DB` and `LTA_ACCOUNT_KEY` from `backend/.env`. Make sure you added them in section 4.1, below the MySQL settings.

### 6.3 Import the data

From the project root, run:

```
python database/scripts/density_import.py
python database/scripts/alerts_import.py
```

The scripts automatically create this database and these collections:

```
TransitIQ
├── StationCrowdDensity
└── TrainServiceAlert
```

### 6.4 Check your data

Refresh MongoDB Compass, open `TransitIQ`, and select each collection to view its documents.

---

## 7. Run the app

The Flask backend in `backend/` exposes the bus and train data from the `Transitiq` MySQL database as JSON endpoints. The frontend calls these endpoints.

Before starting, complete sections 3 to 5. The API only reads and writes tables that already exist and contain data.

### 7.1 Start the server

In the `backend/` folder:

```
python app.py
```

The server starts at `http://localhost:5000`. Leave the terminal open while you use the API. Press `Ctrl+C` to stop the server.

### 7.2 Check the connection

Open this URL in a browser:

```
http://localhost:5000/api/health
```

A working setup returns the database name and MySQL version:

```
{"status": "ok", "db": "Transitiq", "version": "8.0.x"}
```

### 7.3 Test the endpoints

Open `http://localhost:5000/` for the API tester page. It has a button for each endpoint, and shows the HTTP status, response time, the raw JSON and a results table. Try these in order:

1. **GET lines**: should list 11 lines with station counts.
2. **GET stations**: search for `bishan`, or for `碧山` to test Chinese search.
3. **GET station** with code `NS17`: shows the station, its line and interchange codes.
4. **GET line stations** with code `NSL`: stations in numeric order (NS1, NS2, ... NS10).
5. **POST create**, **PUT update**, then **DELETE** using the default `TEST1` values. Delete your test station afterwards so it does not stay in the database.

### 7.4 Test the bus endpoints

Select **Bus** on the API tester page. The bus controls are organised into:

- **Browse Bus Data:** list services, search stops, and retrieve the ordered stops for a service and direction.
- **Manage Bus Records:** create, read, update and delete records in `BusStop`, `BusService` and `BusRoute`.
- **Bus Analysis:** find direct connections, identify well-connected stops, and compare operators.

The page is a temporary API tester for demonstrating the backend and handing over request/response examples to the frontend developer.

#### Primary keys and updates

| Table | Primary key | Example |
|---|---|---|
| `BusStop` | `bus_stop_code` | `TEST01` |
| `BusService` | `service_no` + `direction` | `SER39B`, `1` |
| `BusRoute` | `service_no` + `direction` + `stop_seq` | `SER39B`, `1`, `1` |

To update a record, enter its **existing primary key** and change its other fields. Keep all primary-key fields unchanged. For the two composite keys, every key component is needed to identify one record. `PUT` supports partial updates: omitted fields remain unchanged. Blank inputs in the tester are omitted; they do not clear the stored value.

A `404` response means no record matches the key in the request URL. Check the key using **Read** or **View created records**, then retry. Changing the key in the inputs makes Update target a different record; it does not rename the original key.

#### Suggested CRUD demonstration

Use new keys that do not already exist in your database. Placeholder text is an example only and is not submitted unless you enter it.

1. Create two bus stops, `TEST01` and `TEST02`, with road names, descriptions and valid coordinates.
2. Read `TEST01`, change its description, click **Update**, then **Read** again to confirm the saved value.
3. Create service `SER39B`, direction `1`, using `TEST01` as its origin and `TEST02` as its destination.
4. Read that service, change its category or frequency, update it, then read it again.
5. Create a route entry for `SER39B`, direction `1`, sequence `1`, referencing `TEST01` and distance `0`.
6. Read the route entry, change its distance or a bus time, update it, then read it again.
7. Delete the route entry, then the service, then the two test stops.

Create stops before referencing them in a service or route, and create the service/direction before its route entries. Delete dependent records first, because foreign keys prevent deleting records that are still referenced.

#### Created records versus all records

**View created records** uses browser `localStorage` to remember the primary keys of successful creations made through the tester. It fetches their current database values, so successful updates are visible. Successfully deleted records are removed from the list, and records that return `404` are removed when the list is refreshed.

This is browser-local tracking, not user ownership stored in MySQL. Records created before tracking was installed, through another browser, or through another API client are not automatically included. Clearing browser storage removes the tracking list but does not delete database records. Changing the hostname or port creates a separate browser-storage scope; use the same address when demonstrating this feature.

**View all stops**, **View all services**, and **View all routes** use the normal list endpoints and include imported data together with manually created records. Stop and route lists return up to 50 records by default, with a maximum requested limit of 500; these controls do not display the entire database at once. The services list currently has no pagination.

### Project files

| File | Purpose |
|---|---|
| `backend/app.py` | Starts the Flask app, registers the routes, serves the test page |
| `backend/config.py` | Reads the database settings from `.env` |
| `backend/db.py` | MySQL connection pool, `query()` for reads, `transaction()` for writes |
| `backend/routes/train.py` | Train endpoints (read and CRUD) |
| `backend/routes/bus.py` | Bus browsing and CRUD endpoints for the three bus tables |
| `backend/routes/bus_analysis.py` | Direct connections, stop connectivity and operator comparison |
| `backend/routes/train_analytics.py` | Train analytics and route endpoints |
| `backend/.env.example` | Template for your own `.env` |
| `frontend/templates/api_tester.html` | Test page with a button for each endpoint |

---

## 8. API reference

### Train endpoints

| Method | Path | Description |
|---|---|---|
| GET | `/api/train/stations?q=&line=&limit=&offset=` | Search stations by English name, Chinese name or code; filter by line code |
| GET | `/api/train/stations/<code>` | One station with its line and interchange codes |
| GET | `/api/train/lines` | All lines with station counts |
| GET | `/api/train/lines/<code>` | One line with its station count |
| GET | `/api/train/lines/<code>/stations` | Stations on a line, in numeric order |
| POST | `/api/train/stations` | Create a station and link it to a line |
| PUT | `/api/train/stations/<code>` | Update a station's names (and optionally its line) |
| DELETE | `/api/train/stations/<code>` | Delete a station |
| POST | `/api/train/lines` | Create a line |
| PUT | `/api/train/lines/<code>` | Update a line's names |
| DELETE | `/api/train/lines/<code>` | Delete a line (blocked while it still has stations) |

Request body for creating a station:

```json
{
  "station_code": "TEST1",
  "station_name_english": "Test Station",
  "station_name_chinese": "测试站",
  "line_code": "NSL"
}
```

### Train analytics endpoints

These use the views created in section 5.5, so run `train_view.sql` first.

| Method | Path | Description |
|---|---|---|
| GET | `/api/train/analytics/line-sizes` | Stations per line, share of the network and size rank |
| GET | `/api/train/analytics/interchanges?min_lines=2` | Stations that appear on at least `min_lines` lines |
| GET | `/api/train/analytics/line-connections` | Each pair of lines and the interchanges they share |
| GET | `/api/train/analytics/stations/<code>/neighbours` | The stations before and after a station on its line |
| GET | `/api/train/analytics/above-average-lines` | Lines with more stations than the average line |
| GET | `/api/train/analytics/interchange-share` | Share of each line's stations that are interchanges |
| GET | `/api/train/analytics/route?from=NS1&to=NE17` | Route with the fewest line changes |
| GET | `/api/train/analytics/shortest-route?from=NS1&to=NE17` | Route with the fewest stops (a line change does not count as a stop) |

The shortest-route endpoint reads from `StationConnection`, so fill that table first (section 5.5).

### Bus browsing and CRUD endpoints

All paths below use the `/api/bus` prefix. Primary-key values in the path identify the record; they are not editable fields in an update body.

| Method | Path | Description |
|---|---|---|
| GET | `/api/bus/stops?q=&limit=50` | Search stops by code, road name or description; blank search lists stops |
| GET | `/api/bus/stops/<bus_stop_code>` | Read one stop |
| POST | `/api/bus/stops` | Create a stop |
| PUT | `/api/bus/stops/<bus_stop_code>` | Update non-key fields of an existing stop |
| DELETE | `/api/bus/stops/<bus_stop_code>` | Delete a stop if no records reference it |
| GET | `/api/bus/services` | List services |
| GET | `/api/bus/services/<service_no>/<direction>` | Read one service and direction |
| POST | `/api/bus/services` | Create a service and direction |
| PUT | `/api/bus/services/<service_no>/<direction>` | Update non-key fields of an existing service/direction |
| DELETE | `/api/bus/services/<service_no>/<direction>` | Delete a service/direction if no route entries reference it |
| GET | `/api/bus/services/<service_no>/route?direction=1` | Retrieve the ordered stops along a service/direction |
| GET | `/api/bus/routes?limit=50` | List route entries |
| GET | `/api/bus/routes/<service_no>/<direction>/<stop_seq>` | Read one route entry |
| POST | `/api/bus/routes` | Create a route entry |
| PUT | `/api/bus/routes/<service_no>/<direction>/<stop_seq>` | Update non-key fields of an existing route entry |
| DELETE | `/api/bus/routes/<service_no>/<direction>/<stop_seq>` | Delete a route entry |

#### Create request bodies

Send JSON with `Content-Type: application/json`. Stop codes and bus times should be strings to preserve leading zeros. `TEST` and `SER` are example prefixes, not required naming rules.

**BusStop:** all five fields are required.

```json
{
  "bus_stop_code": "TEST01",
  "road_name": "Victoria St",
  "description": "Test bus stop",
  "latitude": 1.300757,
  "longitude": 103.856110
}
```

**BusService:** service number, direction, operator, category, origin and destination are required. The four frequency fields are optional. Create both referenced stops first.

```json
{
  "service_no": "SER39B",
  "direction": 1,
  "operator": "SMRT",
  "category": "TRUNK",
  "origin_code": "TEST01",
  "destination_code": "TEST02",
  "am_peak_freq": "07-08",
  "am_offpeak_freq": "09-19",
  "pm_peak_freq": "10-15",
  "pm_offpeak_freq": "09-19"
}
```

**BusRoute:** service number, direction, sequence, stop code and distance are required. The six time fields are optional. The referenced service/direction and bus stop must exist first.

```json
{
  "service_no": "SER39B",
  "direction": 1,
  "stop_seq": 1,
  "bus_stop_code": "TEST01",
  "distance": 0,
  "wd_first_bus": "0510",
  "wd_last_bus": "2309",
  "sat_first_bus": "0509",
  "sat_last_bus": "2309",
  "sun_first_bus": "0509",
  "sun_last_bus": "2309"
}
```

#### Update request bodies

Send only the non-key fields to change. For example:

`PUT /api/bus/stops/TEST01`

```json
{
  "description": "Updated test bus stop"
}
```

`PUT /api/bus/services/SER39B/1`

```json
{
  "category": "TRUNK",
  "am_peak_freq": "08-10"
}
```

`PUT /api/bus/routes/SER39B/1/1`

```json
{
  "distance": 0.5,
  "wd_first_bus": "0530"
}
```

A successful update returns `200`, including when the supplied values are unchanged. Read the same URL with `GET` to verify the current database values. The tester automatically performs this read after Create and Update and fills the inputs with the returned values.

API clients may send JSON `null` to clear an optional frequency or time column. The tester's blank inputs do not send `null`; omitted fields retain their current values on update.

#### Bus validation and database constraints

| Rule | Enforced by |
|---|---|
| Unique stop code; unique service/direction; unique service/direction/sequence | MySQL primary keys |
| Required columns cannot contain SQL `NULL` | MySQL `NOT NULL` constraints |
| Service origin/destination and route stop must reference existing stops | MySQL foreign keys |
| Route service/direction must reference an existing service/direction | MySQL composite foreign key |
| Required create fields and non-empty update bodies | Flask validation |
| Direction is `1` or `2`; stop sequence is a positive integer | Flask validation |
| Latitude is between -90 and 90; longitude between -180 and 180 | Flask validation |
| Coordinates and distance are finite; distance is nonnegative | Flask validation |
| Bus times contain four digits with minutes from `00` to `59` | Flask validation |
| Update field names come from an allowlist; values use SQL parameters | Flask query construction |

Times use `HHMM`, such as `0530`. After-midnight hours such as `2530` are accepted. Database column lengths and other schema constraints still apply. `db.query()` handles reads, while `db.transaction()` commits successful writes and rolls back writes that raise an exception.

### Bus analysis endpoints

These endpoints query the bus tables directly; no additional SQL views are required for these three Flask queries.

| Method | Path | Description |
|---|---|---|
| GET | `/api/bus/analysis/direct-connections?origin_code=01012&destination_code=01023` | Find services that visit the origin before the destination in the same direction |
| GET | `/api/bus/analysis/stop-connectivity` | List stops served by at least five distinct service numbers |
| GET | `/api/bus/analysis/operator-comparison` | Compare operators by service count, service/direction count, average route distance and longest route distance |

The direct-connections query uses a self-join on `BusRoute` and compares stop sequences. Stop connectivity uses joins, grouping, `COUNT(DISTINCT ...)` and `HAVING`. Operator comparison uses a derived table to obtain the maximum cumulative distance for each service/direction, then aggregates those route distances by operator. Its `total_routes` counts service/direction groups, not individual route-stop entries.

Origin and destination are required and must differ for the direct-connections endpoint. No matching connection returns an empty `data` array.

#### Bus response examples

A single-record read returns an array containing one record:

```json
{
  "data": [
    {
      "bus_stop_code": "TEST01",
      "road_name": "Victoria St",
      "description": "Updated test bus stop",
      "latitude": "1.300757",
      "longitude": "103.856110"
    }
  ],
  "count": 1
}
```

Decimal database values may be serialised as strings. Successful writes return a `message` object rather than a `data` array; creation returns `201`, while updates and deletes return `200`. Bus analysis responses currently contain `data` without a `count` field.

Invalid input returns `400`. A missing record returns `404`. The detailed bus database error handler maps duplicate keys and foreign-key conflicts to `409`, selected column/type constraint errors to `400`, and other database errors to `500`. If using the simplified handler that returns only `"Database query failed"`, database errors instead return `500`; retain the detailed handler to expose the specific status codes.

### Response format

Successful list/read responses generally use this shape (bus writes and analysis exceptions are described above):

```
{"data": [...], "count": 11}
```

Errors use this shape:

```
{"error": "Station not found"}
```

| Status | Meaning |
|---|---|
| 200 | OK |
| 201 | Created |
| 400 | Missing or invalid input, or the referenced line does not exist |
| 404 | Station or line not found, or no route found |
| 409 | Duplicate code, or delete blocked because other records depend on it |
| 500 | Unexpected database error |

---

## 9. Troubleshooting

### Setup and imports

| Problem | Fix |
|---|---|
| `ModuleNotFoundError: mysql` | Run section 3 again, using the same Python that runs the script |
| `ModuleNotFoundError: No module named 'requests'` | Run section 3 |
| `ModuleNotFoundError: No module named 'pymongo'` | Run section 3 |
| `LTA_API_KEY is not set` | Set the environment variable in the same terminal (section 4.2) |
| LTA API returns 401 or 403 | Check the API key and access permissions |
| LTA API returns 429 | Reduce request frequency and retry later |
| `Table ... doesn't exist` | Execute the database creation and schema scripts first (section 5.1) |
| `Table ... StationConnection doesn't exist` | Run `train_schema.sql` before `train_view.sql` |
| `View ... doesn't exist` | Run `train_view.sql` (section 5.5) |
| `Can't connect to MySQL server` | Start the MySQL service and check the `host` and `port` values |
| `Access denied` | Check the MySQL username, password and permissions |
| `FileNotFoundError` | Check the train CSV filenames and folder structure |
| Garbled Chinese text | Re-export the train CSVs as UTF-8 |
| Bus records skipped | Check the reported missing fields, invalid values or foreign-key references |
| Different database row counts | Review skipped records, duplicate keys and the API source record counts |
| Bus table clearing fails | Check whether other tables reference the bus tables through foreign keys |
| Route API returns no route, or `StationConnection` has 0 rows | Run the train import, then re-run `train_view.sql` |
| Route results look out of date after changing stations | Re-run `train_view.sql` to refresh `StationConnection` |
| `Error Code: 1175` when refreshing a table | Use `TRUNCATE TABLE <name>;` instead of `DELETE` (Workbench Safe Updates blocks `DELETE` without `WHERE`) |
| MongoDB scripts cannot connect | Make sure the MongoDB service is running and `MONGO_URI` in `backend/.env` is correct |
| MongoDB scripts fail on the LTA call | Check that `LTA_ACCOUNT_KEY` is set in `backend/.env` |

### Running the API

| Problem | Fix |
|---|---|
| `Import "flask" could not be resolved` (VS Code) | Run section 3, then pick the right interpreter with `Ctrl+Shift+P`, then Python: Select Interpreter |
| `ModuleNotFoundError` when starting the server | Run `python -m pip install -r requirements.txt` so pip uses the same Python |
| `Authentication plugin 'auth_gssapi_client' is not supported` | Another server (usually MariaDB) is answering on your port, or the password is wrong. Check `.env` and set `DB_PORT` to the MySQL 8.0 port from `SELECT @@port` |
| `Can't connect to MySQL server` when starting the API | Start the MySQL service and check `DB_HOST` and `DB_PORT` in `.env` |
| `/api/health` fails | Check every value in `.env` and that `DB_NAME` is `Transitiq` |
| Test page at `/` is blank | Check that `frontend/templates/api_tester.html` exists |
| Port 5000 already in use | Stop the other program, or change `port=5000` in `app.py` |

### Bus CRUD troubleshooting

| Problem | Fix |
|---|---|
| Update returns `404` / `Record not found` | Keep the existing primary key unchanged. For services, include the correct direction; for routes, include the correct direction and stop sequence. Read the same URL first. |
| Update returns `400` | Supply at least one editable non-key field, check the validation message, and use the required value formats. |
| Duplicate-key error when creating | Choose a new primary key, or use Update for the existing record. |
| Foreign-key error when creating/updating | Create referenced stops first, then the service/direction, then route entries. |
| Delete blocked by foreign keys | Remove or update dependent records before deleting their parent stop or service. |
| `AttributeError: module 'db' has no attribute 'get_connection'` | Use the project's existing `with db.transaction() as cursor:` helper for writes. |
| View created records is empty although database rows exist | The list only tracks creations made through the tester in this browser and at this hostname/port. Use the normal list endpoints to inspect other records. |
| Test records disappear after running the bus importer | The importer clears and repopulates all three bus tables. Create fresh test records after importing. |
| A successful write is followed by a read error | The write may already be committed. Read the record before retrying Create to avoid a duplicate-key error. |
