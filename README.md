# INF2003_TransitIQ

Repository for the INF2003 Database Systems group project.

TransitIQ organises Singapore bus and train information. Structured reference data (bus stops, services, routes, train stations and lines) is stored in **MySQL**. Time-based operational data (station crowd density and train service alerts) is stored in **MongoDB**. A **Flask** backend exposes the data as JSON endpoints, and includes a test page for checking every query.

## 1. Prerequisites

- Python 3 installed
- MySQL Server 8.0 installed and running locally
- MySQL Workbench or DBeaver (or another MySQL client)
- MongoDB Community Server and MongoDB Compass 
- An LTA DataMall API key 
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

## 3. Configure `.env` and the LTA API key

### 3.1 Create your own `.env` file

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

### 3.2 Get an LTA DataMall API key

1. Go to [LTA DataMall](https://datamall.lta.gov.sg/) and request API access at [https://datamall.lta.gov.sg/content/datamall/en/request-for-api.html](https://datamall.lta.gov.sg/content/datamall/en/request-for-api.html).
2. Register and obtain your Account Key.
3. Keep the key private.

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

### 4.2 Verify the train dataset files

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

From the project root, with the LTA API key set (section 4.2), run:

```
python database/scripts/bus_import.py
python database/scripts/train_import.py
```

Enter your MySQL password when prompted each time. The bus and train scripts populate separate tables and can be run in either order.

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
- The bus import can be re-run to refresh the bus data from LTA DataMall. The API key and an internet connection must be available whenever the script retrieves new data.

---

## 5. Set up MongoDB

MongoDB stores the time-based operational data: station crowd density and train service alerts.

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

The NoSQL scripts read `MONGO_URI`, `MONGO_DB` and `LTA_ACCOUNT_KEY` from `backend/.env`. Make sure you added them in section 3.1, below the MySQL settings.

### 5.3 Import the data

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

### 5.4 Check your data

Refresh MongoDB Compass, open `TransitIQ`, and select each collection to view its documents.

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
