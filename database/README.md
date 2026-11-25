## Importing the Data into MySQL

Two Python scripts are used to populate the `Transitiq` MySQL database with bus and train information:

| Script | Tables populated | Dataset files |
|---|---|---|
| `bus_import.py` | `BusStop`, `BusService`, `BusRoute` | Saved LTA JSON files in `datasets/bus/json/` |
| `train_import.py` | `TrainLine`, `TrainStation`, `StationLine` | `datasets/train/csv/` (converted from original Excel datasets) |

## Data Sources
### Bus datasets
The bus datasets are retrieved from Singapore's Land Transport Authority (LTA) DataMall and saved locally as JSON files.

The three datasets used are:
- <b>Bus Stops:</b> Contains bus stop codes, road names, descriptions and geographical coordinates.
- <b>Bus Services:</b> Contains bus service numbers, directions, operators, categories, origins, destinations and frequency information.
- <b>Bus Routes:</b> Contains the sequence of bus stops along each service, route distances and first/last bus timings.

`bus_import.py` reads these saved files and imports them into MySQL. It does not call the LTA API, so an LTA API key and internet access are not required for the bus import.

### Train datasets
The original train datasets were provided in Excel format (`Train-Station-Codes-and-Chinese-Names.xls` and `Train-Line-Codes.xlsx`). 

These files were converted into CSV format to facilitate importing the train station and line information into MySQL.

### Prerequisites
Before running the import scripts, ensure that:
- Python 3 installed
- MySQL Server 8.0 is installed and running locally
- MySQL Workbench/DBeaver (or another MySQL client is available)
- An LTA DataMall API key is available for retrieving the datasets.
- The bus JSON and train CSV datasets are present in the required directory.

### Step 1: Install Python Dependencies

In a terminal, run:
From the TransitIQ project root directory, install the required packages:
    
    pip install -r requirements.txt

Alternatively, install the MySQL connector individually:
    
    pip install mysql-connector-python

If using the project's virtual environment, activate it before installing dependencies.

### Step 2: Create the Database and Tables
The import scripts do not create tables. They must exist before either script runs.

1. Open MySQL Workbench/DBeaver and connect to your local MySQL server.
2. Execute `database/sql/create_database.sql` to create the Transitiq database.
3. Run the table definitions from the schema files in `database/sql/`, for both the bus tables (`BusStop`, `BusService`, `BusRoute`) and the train tables (`TrainStation`, `TrainLine`, `StationLine`).
4. Verify that the tables were created successfully.
       
       USE Transitiq;

       SHOW TABLES;

    The database should contain these seven tables:

   - BusStop
   - BusService
   - BusRoute
   - TrainLine
   - TrainStation
   - StationLine
   - StationConnection

    `StationConnection` is created empty by `train_schema.sql`. It stores a copy of the
   station-to-station connections in the view `v_name_graph`, so route lookups are fast.
   It is filled in Step 7, after the train data has been imported.

### Step 3: Verify the Train Dataset Files

Ensure that the following train datasets are available:

### Train CSV datasets

    datasets/train/csv/
    ├── train_stations.csv
    └── train_lines.csv

### Original train Excel datasets

    datasets/train/excel
    ├── Train Station Codes and Chinese Names.xlsx
    └── Train Line Codes.xlsx

CSV files should use UTF-8 encoding to preserve special characters and Chinese station names.

### Step 4: Verify the Bus Dataset Files

Ensure that the following saved LTA JSON datasets are available:

    datasets/bus/json/
    ├── BusStops.json
    ├── BusServices.json
    └── BusRoutes.json

`bus_import.py` reads these local files. An LTA API key and
internet connection are not required for importing them.

If the files are missing or need refreshing, follow
“Optional: Refresh the saved bus datasets” below.

### Step 5: Verify MySQL Connection Settings
The import scripts use the following local database settings:

    host="localhost"
    port=3306
    user="root"
    database="Transitiq"

Update the `host`, `port` or `user` if your MySQL setup differs. 
The password is requested when a script runs, so it is never stored in the file.

### Step 6: Run the scripts
From the TransitIQ project root directory, run:

### Import bus datasets
    python database/scripts/bus_import.py

### Import train datasets
    python database/scripts/train_import.py

Enter your MySQL password when prompted. 

The bus and train scripts populate separate tables and can be executed independently.

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


### Train Import Process
The `train_import.py` script reads the converted train CSV datasets and populates the `TrainLine`, `TrainStation` and `StationLine` tables.

The expected processing counts from the existing train import implementation are:

    TrainLine records processed: 11
    TrainStation records processed: 213
    StationLine records processed: 213
    Import completed successfully!

These counts should be verified against the actual output when running the script.

### Step 7: Create the Train Views and Fill StationConnection

Do this after the train import in Step 6, because the views read the imported train tables.

1. Execute `database/sql/train_view.sql` in MySQL Workbench/DBeaver. This creates the train
   views (including `v_name_graph`, which defines the station-to-station connections), then
   empties `StationConnection` and refills it from `v_name_graph`.
2. Check that the table was filled and matches the view:

       USE Transitiq;

       SELECT COUNT(*) FROM v_name_graph;
       SELECT COUNT(*) FROM StationConnection;

   Both counts should be the same and greater than zero. If both are 0, the train import
   (Step 6) has not run yet. Run it, then run `train_view.sql` again.

#### When the train data changes

`StationConnection` is a stored copy, so it is not updated automatically. If the station data
changes (stations added, edited or deleted, or the train import is re-run with different
data), re-run `train_view.sql` to refresh it. The file can be run any number of times.

Changes that do not affect station names, codes or lines (for example, renaming a line) do
not require a refresh.

The train route queries in the API read from `StationConnection`. If it is empty, route
requests return no results.

### Step 8: Verify the import
After running both import scripts, execute the following SQL queries in MySQL Workbench/DBeaver:

    USE Transitiq;

    -- Bus tables
    SELECT COUNT(*) AS total_bus_stops FROM BusStop;
    SELECT COUNT(*) AS total_bus_services FROM BusService;
    SELECT COUNT(*) AS total_bus_routes FROM BusRoute;

    -- Train tables
    SELECT COUNT(*) AS total_train_lines FROM TrainLine;
    SELECT COUNT(*) AS total_train_stations FROM TrainStation;
    SELECT COUNT(*) AS total_station_lines FROM StationLine;
    
    -- Train route tables
    SELECT COUNT(*) AS total_station_connections FROM StationConnection;

The bus table counts should reflect the successfully imported LTA records after the fresh import.

Counts may differ from the API source totals if records are skipped due to missing values, foreign-key constraints or duplicate primary keys.

`StationConnection` should have the same number of rows as `v_name_graph`.

The bus import can be rerun to refresh the relational bus data from LTA DataMall. The API key and internet connection must be available whenever the script retrieves new data.

### Troubleshooting
| Problem | Fix |
|---|---|
| `ModuleNotFoundError: mysql` | Run Step 1 again, using the same Python that runs the script |
| `ModuleNotFoundError: No module named 'requests'` | Run Step 1 |
| `LTA_API_KEY is not set` | Configure the API key environment variable
| `LTA API returns 401 or 403` | Check the API key and access permissions
| `LTA API returns 429` | Reduce request frequency and retry later
| `Table ... doesn't exist` | Execute the database creation and schema scripts first |
| `Can't connect to MySQL server` | Start the MySQL service and check the `host` and `port` value |
| `Access denied` | Check the MySQL username, password and permissions |
| `FileNotFoundError` | Check the train CSV filenames and folder structure |
| Garbled Chinese text | Re-export the train CSVs as UTF-8 |
| Bus records skipped | Check the reported missing fields, invalid values or foreign-key references |
| Different database row counts | Review skipped records, duplicate keys and the API source record counts |
| Bus table clearing fails | Check whether other database tables reference the bus tables through foreign keys |
| `Table ... StationConnection doesn't exist` | Run `train_schema.sql` (Step 2) before `train_view.sql` |
| `View ... doesn't exist` | Run `train_view.sql` (Step 7) |
| Route API returns no route, or `StationConnection` has 0 rows | Run the train import (Step 6), then re-run `train_view.sql` |
| Route results look out of date after changing stations | Re-run `train_view.sql` to refresh `StationConnection` |
| `Error Code: 1175` when running a refresh | Use `TRUNCATE TABLE StationConnection;` instead of `DELETE` (Workbench Safe Updates blocks `DELETE` without `WHERE`) |