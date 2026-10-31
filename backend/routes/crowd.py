import os
from datetime import datetime, timezone
from pathlib import Path

from dotenv import load_dotenv
from flask import Blueprint, jsonify, request
from pymongo import MongoClient
from pymongo.errors import PyMongoError

BACKEND_FOLDER = Path(__file__).resolve().parents[1]
load_dotenv(BACKEND_FOLDER / ".env")

bp = Blueprint(
    "crowd",
    __name__,
    url_prefix="/api/crowd",
)

client = MongoClient(
    os.getenv("MONGO_URI", "mongodb://localhost:27017/"),
    serverSelectionTimeoutMS=3000,
    tz_aware=True,
    connect=False,
)

database = client[os.getenv("MONGO_DB", "TransitIQ")]

TRAIN_LINES = {
    "CCL", "CEL", "CGL", "DTL", "EWL", "NEL",
    "NSL", "BPL", "SLRT", "PLRT", "TEL",
}

CROWD_LABELS = {
    "l": "Low",
    "m": "Moderate",
    "h": "High",
    "NA": "Not available",
}


@bp.get("/latest")
def latest_crowd():
    now = datetime.now(timezone.utc)

    query = {
        "station_code": {"$type": "string"},
        "start_time": {"$lte": now},
    }

    line = request.args.get("line_code", "").strip().upper()
    station = request.args.get("station_code", "").strip().upper()

    if line:
        if line not in TRAIN_LINES:
            return jsonify({"error": "Invalid line_code"}), 400

        query["line_code"] = line

    if station:
        if not station.isalnum() or len(station) > 12:
            return jsonify({"error": "Invalid station_code"}), 400

        query["station_code"] = station

    try:
        rows = list(database.StationCrowdDensity.aggregate([
            {"$match": query},

            {"$sort": {
                "start_time": -1,
                "end_time": -1,
                "fetched_at": -1,
            }},

            # Keep one latest observation per station and line.
            {"$group": {
                "_id": {
                    "station": "$station_code",
                    "line": "$line_code",
                },
                "observation": {"$first": "$$ROOT"},
            }},

            {"$replaceRoot": {"newRoot": "$observation"}},

            {"$sort": {
                "line_code": 1,
                "station_code": 1,
            }},

            {"$project": {
                "_id": 0,
                "line_code": 1,
                "station_code": 1,
                "crowd_level": 1,
                "start_time": 1,
                "end_time": 1,
                "fetched_at": 1,
            }},
        ]))

        for row in rows:
            row["crowd_label"] = CROWD_LABELS.get(
                row["crowd_level"],
                "Unknown",
            )

            for field in ("start_time", "end_time", "fetched_at"):
                row[field] = row[field].isoformat()

        response = jsonify({
            "data": rows,
            "count": len(rows),
        })

        response.headers["Cache-Control"] = "no-store"
        return response

    except PyMongoError:
        return jsonify({
            "error": "Crowd data is temporarily unavailable."
        }), 503