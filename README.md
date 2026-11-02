# INF2003_TransitIQ
Repository for INF2003 project

## Setting up

### Prerequisites

- Python 3 installed
- MySQL Server 8.0 running locally
- MySQL Workbench (or another MySQL client)

### Step 1: Install all necessary packages

In a terminal, run:

    pip install -r requirements.txt

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

**Change `port` or `user` if your MySQL setup differs.** 

The password is requested when a script runs, so it is never stored in the file.

### Step 5: Run the data import scripts

From `database/scripts`, run them one after the other:

    python bus_import.py
    python import_train_data.py

Enter your MySQL password when prompted each time. The two scripts use separate tables, so they can be run in either order.

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

## How to run
### Step 1: Create your own `.env` file
The `.env` file stores **your own** MySQL login details. It is not included in the repository, so each member must create it on their own computer. Do not copy the example `.env.example`, because the password, port and username may not match your MySQL setup.

1. In `backend/`, make a copy of `.env.example` and name the copy `.env`. You should now have both files side by side.
2. Open `.env` and fill each value with the details of **your** MySQL server:

       DB_HOST=your_host
       DB_PORT=your_port
       DB_USER=your_user
       DB_PASSWORD=your_mysql_password
       DB_NAME=your_name

### Step 2: Start the server

In the `backend/` folder:

    python app.py

Open `http://localhost:5000/` for the webpage. Leave the terminal open while you use the API. Press `Ctrl+C` to stop stop the server.