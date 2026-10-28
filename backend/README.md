## Running the API (Flask)

The Flask backend in `backend/` exposes the train data from the `Transitiq` MySQL database as JSON endpoints. The frontend (PHP) calls these endpoints. A built-in test page is included to check that every query works.

Complete **Importing the Data into MySQL** first. The API only reads and writes tables that already exist and contain data.

### Project files

| File | Purpose |
|---|---|
| `backend/app.py` | Starts the Flask app, registers the routes, serves the test page |
| `backend/config.py` | Reads the database settings from `.env` |
| `backend/db.py` | MySQL connection pool, `query()` for reads, `transaction()` for writes |
| `backend/routes/train.py` | All train endpoints (read and CRUD) |
| `backend/requirements.txt` | Python packages needed |
| `backend/.env.example` | Template for your own `.env` |
| `frontend/templates/api_tester.html` | Test page with a button for each endpoint |

### Prerequisites

- Python 3 installed
- MySQL Server 8.0 running locally, with the `Transitiq` database imported (see above)

### Step 1: Install the Python packages

Open a terminal in the `backend/` folder and run:

    pip install -r requirements.txt

This installs Flask, `mysql-connector-python` and `python-dotenv`. You do not need to install them separately. If you use a virtual environment, activate it first.

To confirm the install worked:

    python -c "import flask, mysql.connector, dotenv; print('ok')"

### Step 2: Create your `.env` file

1. In `backend/`, copy `.env.example` and name the copy `.env`.
2. Fill in your own MySQL details:

       DB_HOST=localhost
       DB_PORT=3306
       DB_USER=root
       DB_PASSWORD=your_mysql_password
       DB_NAME=Transitiq

3. Set `DB_PORT` to the port your MySQL 8.0 server uses. To check it, run this in MySQL Workbench:

       SELECT @@port, VERSION();

### Step 3: Start the API

From the `backend/` folder:

    python app.py

The server starts at `http://localhost:5000`. Leave the terminal open while you use the API. Press `Ctrl+C` to stop it.

### Step 4: Test the endpoints

Open `http://localhost:5000/` for the API tester page. It has a button for each endpoint, and shows the HTTP status, response time, the raw JSON and a results table. Try these in order:

1. **GET lines** - should list 11 lines with station counts.
2. **GET stations** - search for `bishan`, or for `碧山` to test Chinese search.
3. **GET station** with code `NS17` - shows the station, its line and interchange codes.
4. **GET line stations** with code `NSL` - stations in numeric order (NS1, NS2, ... NS10).
5. **POST create**, **PUT update**, then **DELETE** using the default `TEST1` values.

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

    {
      "station_code": "TEST1",
      "station_name_english": "Test Station",
      "station_name_chinese": "测试站",
      "line_code": "NSL"
    }

### Response format

Successful responses use this shape:

    {"data": [...], "count": 11}

Errors use this shape:

    {"error": "Station not found"}

| Status | Meaning |
|---|---|
| 200 | OK |
| 201 | Created |
| 400 | Missing or invalid input, or the referenced line does not exist |
| 404 | Station or line not found |
| 409 | Duplicate code, or delete blocked because other records depend on it |
| 500 | Unexpected database error |