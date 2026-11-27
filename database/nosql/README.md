# NoSQL Setup — TransitIQ

Use the bundled train crowd and service alert samples to run this part of TransitIQ without an LTA DataMall API key.

## 1. Install MongoDB

1. Download the Windows MSI from [MongoDB Community Server](https://www.mongodb.com/try/download/community).
2. Run the installer and choose **Complete**. Enable **Install MongoD as a Service**.
3. Install MongoDB Compass when offered, then connect to `mongodb://localhost:27017/`.

## 2. Configure the database

From the project root, install the project dependencies.

```powershell
python -m pip install -r requirements.txt
```

Add the MongoDB settings to `backend/.env` alongside your MySQL settings.

```dotenv
MONGO_URI=mongodb://localhost:27017/
MONGO_DB=TransitIQ
```

Use a fresh database name such as `TransitIQ_demo` if you already have live data in `TransitIQ` and want a sample-only demo.

## 3. Load the train samples

From the project root, run the importer once.

```powershell
python database/scripts/train_sample_import.py
```

The files in `database/nosql/sample_data/` populate the following collections.

| Sample file | MongoDB collection | Sample documents |
|---|---|---:|
| `StationCrowdDensity.json` | `StationCrowdDensity` | 86,466 |
| `TrainServiceAlert.json` | `TrainServiceAlert` | 5 |

The importer creates the collections and calls the shared index setup in `database/scripts/mongo_db.py`.

- `unique_station_window` prevents duplicate station readings for the same line and time window.
- `station_history` indexes station codes and start times for crowd history queries.
- `alert_history` indexes alert retrieval times for the latest service alert lookup.

Rerunning the importer replaces sample documents with matching `_id` values. Flask reads the saved records from MongoDB when the dashboard requests them.

## 4. Verify the import

In MongoDB Compass, open the database named by `MONGO_DB` and check the **Documents** and **Indexes** tabs for both collections. Start Flask and open `http://localhost:5000/crowd-dashboard` to check the crowd and alert views. [Run the app](../../README.md#6-run-the-app)
