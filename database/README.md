## Importing the Data into MySQL

Two Python scripts load the datasets into the `Transitiq` MySQL database:

| Script | Tables filled | Source files |
|---|---|---|
| `bus_import.py` | `BusStop`, `BusService`, `BusRoute` | `datasets/bus/csv/bus_stops.csv`, `bus_services.csv`, `bus_routes.csv` |
| `import_train_data.py` | `TrainLine`, `TrainStation`, `StationLine` | `datasets/train/csv/train_stations.csv`, `train_lines.csv` |

The bus data comes as JSON samples from the LTA DataMall static datasets and supplemented with more comprehensive CSV datasets sourced from Kaggle to support the relational database implementation. The train CSV datasets were converted from the original `Train-Station-Codes-and-Chinese-Names.xls` and `Train-Line-Codes.xlsx`.

### Prerequisites

- Python 3 installed
- MySQL Server 8.0 running locally
- MySQL Workbench (or another MySQL client)

### Step 1: Install the MySQL connector

In a terminal, run:

    pip install mysql-connector-python

### Step 2: Create the database and tables

The scripts do not create tables. They must exist before either script runs.

1. Open MySQL Workbench and connect to your local MySQL server.
2. Create the database:

       CREATE DATABASE IF NOT EXISTS Transitiq;
       USE Transitiq;

3. Run the table definitions from the schema files in `database/sql/`, for both the bus tables (`BusStop`, `BusService`, `BusRoute`) and the train tables (`TrainStation`, `TrainLine`, `StationLine`).
4. Check the tables exist. In the Schemas panel, refresh and expand `Transitiq` > Tables, or run:

       SHOW TABLES;

   The output must include all six tables.

### Step 3: Check the dataset files

Make sure these files are present. All CSVs must be saved as **CSV UTF-8 (Comma delimited)** so that special and Chinese characters load correctly:

- `datasets/bus/csv/bus_stops.csv`
- `datasets/bus/csv/bus_services.csv`
- `datasets/bus/csv/bus_routes.csv`
- `datasets/train/csv/train_stations.csv`
- `datasets/train/csv/train_lines.csv`

### Step 4: Check the connection settings

In each script, the connection block uses these defaults:

    host="localhost"
    port=3306
    user="root"
    database="Transitiq"

Change `port` or `user` if your MySQL setup differs. The password is requested when a script runs, so it is never stored in the file.

### Step 5: Run the scripts

From the folder containing the scripts, run them one after the other:

    python bus_import.py
    python import_train_data.py

Enter your MySQL password when prompted each time. The two scripts use separate tables, so they can be run in either order.

Within the bus script, records are imported in the order `BusStop`, `BusService`, `BusRoute`, because later tables refer to earlier ones through foreign keys. Rows that refer to a missing stop or service are skipped and listed in the output.

### Step 6: Verify the import

Each script prints the number of records processed and skipped, then the total rows in each table. The train script should show:

    TrainLine records processed: 11
    TrainStation records processed: 213
    StationLine records processed: 213
    Import completed successfully!

Both scripts can be run again safely. Existing rows are updated rather than duplicated.

### Troubleshooting

| Problem | Fix |
|---|---|
| `ModuleNotFoundError: mysql` | Run Step 1 again, using the same Python that runs the script |
| `Table ... doesn't exist` | Complete Step 2 first |
| `Can't connect to MySQL server` | Start the MySQL service and check the `port` value |
| `Access denied` | Check the user and password |
| `FileNotFoundError` | Check the CSV names and folders in Step 3 |
| Garbled Chinese text | Re-export the train CSVs as UTF-8 |
| Many bus rows skipped | Check that `bus_stops.csv` loaded first and is complete, because services and routes depend on it |