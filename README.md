# INF2003_TransitIQ

Repository for the INF2003 Database Systems group project.

TransitIQ organises Singapore bus and train information. Structured reference data (bus stops, services, routes, train stations and lines) is stored in **MySQL**. Time-based operational data (station crowd density and train service alerts) is stored in **MongoDB**. A **Flask** backend exposes the data as JSON endpoints, and includes a test page for checking every query.

## 1. Prerequisites

- Python 3 installed
- MySQL Server 8.0 installed and running locally
- MySQL Workbench or DBeaver (or another MySQL client)
- MongoDB Community Server and MongoDB Compass 
- The train CSV datasets present in `datasets/train/csv/`

---

## 2. Install the Python packages

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

## 3. Configure your database connections

### 3.1 Create your own `.env` file

Create a local `.env` with the connection settings for your own MySQL and MongoDB servers.

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
```

If you change `.env` while the server is running, stop the server with `Ctrl+C` and start it again.

---

## 4. Set up MySQL

### 4.1 Create the database and tables

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

### 4.2 Verify the bus and train dataset files

Ensure that the following bus and train datasets are available:

```
datasets/bus/json
├── BusRoutes.json
└── BusServices.json
└── BusStops.json

datasets/train/csv/
├── train_stations.csv
└── train_lines.csv

datasets/train/excel/
├── Train Station Codes and Chinese Names.xlsx
└── Train Line Codes.xlsx
```

CSV files must be saved as **CSV UTF-8 (Comma delimited)** so that special characters and Chinese station names load correctly.

### 4.3 Check the MySQL connection settings in the import scripts

The import scripts use these local database settings:

```
host="localhost"
port=3306
user="root"
database="Transitiq"
```

**Change `host`, `port` or `user` in the scripts if your MySQL setup differs.** 

These settings are separate from `backend/.env`, which is used by the Flask backend. Make sure both point at the same MySQL server.

### 4.4 Run the import scripts

From the project root, load the bundled files into MySQL.

```
python database/scripts/bus_import.py
python database/scripts/train_import.py
```

Enter your MySQL password when prompted each time. The bus and train scripts populate separate tables and can be run in either order.

### Bus Import Process
Ensure the three JSON files are available in `datasets/bus/json/`.

From the project root, run:

    python database/scripts/bus_import.py

Enter your MySQL password when prompted.

The bus import script performs the following operations:

1. Loads and checks the three local JSON datasets.
2. Connects to the `Transitiq` MySQL database.
3. Clears existing records in the order:
   `BusRoute` → `BusService` → `BusStop`.
4. Imports records in the order:
   `BusStop` → `BusService` → `BusRoute`.
5. Checks required fields, numeric values and foreign-key references.
6. Skips invalid records and displays the reasons.
7. Commits the import and displays the final row counts. MySQL errors trigger a rollback.

The import order is important because `BusService` references `BusStop`, while `BusRoute` references both `BusService` and `BusStop`.

The script uses `ON DUPLICATE KEY UPDATE` to handle records with existing primary keys.

<b>Important:</b> Each execution performs a fresh import by clearing and repopulating the bus tables. Any existing bus records, including manually added test data, will be removed. Back up important data before running the script. The train tables are not intentionally cleared by the bus importer.

### Bus Import Results
The following results were obtained from a successful import:

| Table | Source records | Records processed | Records skipped |
|---|---|---|---|
| BusStop | 5210 | 5210 | 0 |
| BusService | 805 | 802 | 3 |
| BusRoute | 26972 | 26972 | 0 |
| Total | 32987 | 32984 | 3 |

Three bus services (291, 293 and 307) were skipped because the data returned missing `OriginCode` and `DestinationCode` values.

These records could not satisfy the NOT NULL and foreign-key constraints defined in the `BusService` table.

The final MySQL database counts after the fresh import were:

    BusStop: 5210 total rows
    BusService: 802 total rows
    BusRoute: 26972 total rows

Note: The source record counts may change when the LTA datasets are updated.

#### Optional: Refresh the saved bus datasets
The included JSON files can be imported directly. To retrieve fresh
datasets from LTA DataMall, run:

    python database/scripts/retrieve_bus_data.py

An LTA DataMall Account Key and internet connection are required. The script retrieves all pages and saves the three JSON files in `datasets/bus/json/`, backing up previous files automatically.

Retrieval does not modify MySQL. Run `bus_import.py` afterwards to load the refreshed files into the database.

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
### 4.5 Create the train views and fill `StationConnection`

Do this after the train import in section 4.4, because the views read the imported train tables.

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

### 4.6 Verify the MySQL import

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

---

## 5. Set up MongoDB

MongoDB stores the time-based operational data: station crowd density, train service alerts and bus arrival snapshots.

### 5.1 Install MongoDB

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

### 5.2 Check your settings

The sample importers and Flask read `MONGO_URI` and `MONGO_DB` from `backend/.env` (section 3.1). If your local database already contains live data, you can set `MONGO_DB` to a fresh name such as `TransitIQ_demo` for the sample demo.

### 5.3 Load the train crowd and service alert samples

Run the one-time importer from the project root.

```powershell
python database/scripts/train_sample_import.py
```

The importer reads two bundled files from `database/nosql/sample_data/` and prints the following counts.

| Sample file | MongoDB collection | Sample documents |
|---|---|---:|
| `StationCrowdDensity.json` | `StationCrowdDensity` | 86,466 |
| `TrainServiceAlert.json` | `TrainServiceAlert` | 5 |

The importer creates the collections and their indexes through `mongo_db.py`. Rerunning it replaces matching sample documents by `_id`. The train crowd and alert features use the saved snapshots and require no LTA API key.

### 5.4 Check your data

In MongoDB Compass, open the database named by `MONGO_DB` and check the **Documents** and **Indexes** tabs for both collections. After starting Flask (section 6), open `http://localhost:5000/crowd-dashboard` to view crowd levels, busy-hour summaries and the latest saved service alert.

### 5.5 Load the bus arrival sample data (no API key needed)

Bus arrival monitoring uses saved snapshots from the LTA DataMall Bus Arrival API. A snapshot of every service at each of 10 bus stops was taken about every 15 minutes from 31 Oct to 8 Nov 2026 (with a few gaps), giving 3,417 snapshots. They are stored in `database/nosql/sample_data/BusArrival.zip`.

From the project root, run:

```
python database/scripts/bus_arrival_sample_import.py
```

Expected output:

```
Read 3417 snapshots from BusArrival.zip
Saved 3417 snapshots for 10 stops
From 31 Oct 2026 20:53 to 08 Nov 2026 00:11 (SGT)
```

The script reads the zip directly, so there is no need to unzip it or import it through Compass. It creates the `BusArrival` collection and its index. It empties the collection before loading, so it is safe to run again.

The 10 monitored stops are:

| Stop code | Name | Stop code | Name |
|---|---|---|---|
| 46009 | Woodlands Int | 22009 | Boon Lay Int |
| 54009 | Ang Mo Kio Int | 14009 | HarbourFront Int |
| 67009 | Sengkang Int | 08057 | Dhoby Ghaut Stn |
| 75009 | Tampines Int | 09047 | Orchard Stn/Tang Plaza |
| 52009 | Toa Payoh Int | 17171 | Clementi Stn |

#### Bus arrival endpoints

Start the app (section 6), then try these. The Bus arrivals box on the test page uses `/latest`.

| Method | Path | Description |
|---|---|---|
| GET | `/api/bus-arrivals/stops` | Monitored stops with snapshot counts and date range |
| GET | `/api/bus-arrivals/75009/latest` | Latest snapshot for a stop |
| GET | `/api/bus-arrivals/75009/history?service=10&hours=24` | Past snapshots for one service at a stop |
| GET | `/api/bus-arrivals/75009/average-wait?hours=24` | Average, shortest and longest wait per service (aggregation pipeline) |
| GET | `/api/bus-arrivals/75009/crowding?hours=24` | Share of buses with seats, standing room or limited standing (aggregation pipeline) |
| PUT | `/api/bus-arrivals/75009/name` | Rename a stop in all its snapshots. Body: `{"bus_stop_name": "Tampines Bus Interchange"}` |
| DELETE | `/api/bus-arrivals/old?days=7` | Delete snapshots older than the given number of days |

Notes:

- `hours` is between 1 and 168 (default 24). The window counts back from the stop's newest snapshot, not from the current time, so the analytics also work on the saved data.
- On the test page, a snapshot older than 15 minutes shows the arrival times as they were recorded, with the date and time it was taken.
- **Warning:** `DELETE /api/bus-arrivals/old?days=7` counts from today, so it deletes all of the sample data. If that happens, run `bus_arrival_sample_import.py` again.

#### Optional: collect live bus arrivals

`database/scripts/bus_arrival_import.py` fetches the current arrivals for the 10 stops from LTA DataMall and adds one snapshot per stop each time it runs. It needs `LTA_ACCOUNT_KEY` in `backend/.env`. The app does not run it automatically, and it is not needed for the rest of the project.

---

## 6. Run the app

In the `backend/` folder:

```
python app.py
```

The server starts at `http://localhost:5000`. Leave the terminal open while you use the API. Press `Ctrl+C` to stop the server.

## 7. Troubleshooting

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
| The train crowd dashboard shows no saved data | Check `MONGO_DB` in `backend/.env` and run `train_sample_import.py` (section 5.3) |
| Bus arrival endpoints return no data, or `/latest` returns 404 | Run `bus_arrival_sample_import.py` (section 5.5) and use one of the 10 monitored stop codes |
| Bus arrival `history` returns no rows | Check that the service stops at that stop (see `/latest` for the services there) |

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

## 8. LTA data and API key security

- **The sample-data setup runs without an LTA DataMall API key.** The optional live bus tools use a key to request fresh data from LTA. Keep credentials private and exclude `backend/.env` from submission archives.
- **What the data contains.** The saved LTA data is public transport information: bus stops, services, routes, arrival times, bus load and bus type, plus train crowd levels and service alerts. It contains no personal data. It is used for this academic project under the LTA DataMall terms of use.
- **If a key is exposed** (for example in a screenshot or chat), request a new key from LTA DataMall and update your own `.env`.
