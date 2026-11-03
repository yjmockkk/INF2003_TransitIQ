## Importing the Data into MySQL

Two Python scripts are used to populate the `Transitiq` MySQL database with bus and train information:

| Script | Tables populated | Dataset files |
|---|---|---|
| `bus_import.py` | `BusStop`, `BusService`, `BusRoute` | LTA DataMall API (Bus Stops, Bus Services and Bus Routes) |
| `train_import.py` | `TrainLine`, `TrainStation`, `StationLine` | `datasets/train/csv/` (converted from original Excel datasets) |

## Data Sources
### Bus datasets
The bus datasets are retrieved directly from Singapore's Land Transport Authority (LTA) DataMall API using an API key.

The three datasets used are:
- <b>Bus Stops:</b> Contains bus stop codes, road names, descriptions and geographical coordinates.
- <b>Bus Services:</b> Contains bus service numbers, directions, operators, categories, origins, destinations and frequency information.
- <b>Bus Routes:</b> Contains the sequence of bus stops along each service, route distances and first/last bus timings.

Initially, limited JSON samples from LTA DataMall were used to examine the dataset structures. However, these samples were insufficient for populating the relational database. Therefore, the implementation was updated to retrieve the complete datasets directly through the LTA DataMall API.

The Python import script retrieves the complete datasets using API pagination and populates the corresponding MySQL tables.

### Train datasets
The original train datasets were provided in Excel format (`Train-Station-Codes-and-Chinese-Names.xls` and `Train-Line-Codes.xlsx`). 

These files were converted into CSV format to facilitate importing the train station and line information into MySQL.

### Prerequisites
Before running the import scripts, ensure that:
- Python 3 installed
- MySQL Server 8.0 is installed and running locally
- MySQL Workbench/DBeaver (or another MySQL client is available)
- An LTA DataMall API key is available for retrieving the datasets.
- The train CSV datasets are present in the required directory.

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

The bus import script does not require local CSV or JSON files, as it retrieves the bus datasets directly from LTA DataMall.

### Step 4: Configure the LTA DataMall API Key
The `bus_import.py` script retrieves bus datasets directly from LTA DataMall and requires a valid API key.

To request API access, visit https://datamall.lta.gov.sg/content/datamall/en/request-for-api.html 

#### Set the API Key

Open a terminal in the TransitIQ project root directory.

For macOS/Linux:

    export LTA_API_KEY='YOUR_LTA_API_KEY'

For Windows PowerShell:

    $env:LTA_API_KEY = "YOUR_LTA_API_KEY"

Replace `YOUR_LTA_API_KEY` with your actual API key.

#### Important notes:
- The API key must be configured in the terminal session used to run the script.
- When opening a new terminal session, the API key may need to be exported again.
- The API key must not be hardcoded into Python files.
- The importer requires an internet connection to retrieve LTA data.
- Running `bus_import.py` clears and repopulates the existing bus tables. Back up important bus data before running it.

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
The bus import script performs the following operations:

1. Authenticates with LTA DataMall using the API key.
2. Retrieves the complete Bus Stops, Bus Services and Bus Routes datasets using $skip pagination, with up to 500 records per request.
3. Connects to the Transitiq MySQL database.
4. Clears the existing records from the three bus tables in the order BusRoute → BusService → BusStop.
5. Imports the retrieved records in the order BusStop → BusService → BusRoute
6. Validates mandatory fields, numeric values and foreign-key references before insertion.
7. Skips records that fail validation and displays the reasons.
8. Commits the imported data and displays the final database row counts.

The import order is important because `BusService` references `BusStop`, while `BusRoute` references both `BusService` and `BusStop`.

The script uses `ON DUPLICATE KEY UPDATE` to handle records with existing primary keys.

<b>Important:</b> Each execution performs a fresh import by clearing and repopulating the bus tables. Any existing bus records, including manually added test data, will be removed. Back up important data before running the script. The train tables are not intentionally cleared by the bus importer.

### Bus Import Results
The following results were obtained from a successful LTA DataMall API import:

| Table | Source records | Records processed | Records skipped |
|---|---|---|---|
| BusStop | 5209 | 5209 | 0 |
| BusService | 804 | 801 | 3 |
| BusRoute | 26946 | 26946 | 0 |
| Total | 32959| 32956| 3 |

Three bus services (291, 293 and 307) were skipped because the API returned missing `OriginCode` and `DestinationCode` values.

These records could not satisfy the NOT NULL and foreign-key constraints defined in the `BusService` table.

The final MySQL database counts after the fresh import were:

    BusStop: 5209 total rows
    BusService: 801 total rows
    BusRoute: 26946 total rows

Note: The source record counts may change when the LTA datasets are updated.

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