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

@bp.get("/busy-hours")
def busy_hours():
    station = request.args.get("station_code", "").strip().upper()
    line = request.args.get("line_code", "").strip().upper()

    if not station:
        return jsonify({"error": "station_code is required"}), 400

    if not station.isalnum() or len(station) > 12:
        return jsonify({"error": "Invalid station_code"}), 400

    if line and line not in TRAIN_LINES:
        return jsonify({"error": "Invalid line_code"}), 400

    query = {
        "station_code": station,
        "start_time": {"$type": "date"},
        "crowd_level": {"$in": ["l", "m", "h"]},
    }

    if line:
        query["line_code"] = line

    try:
        rows = list(database.StationCrowdDensity.aggregate([
            {"$match": query},

            # Convert each observation's timestamp to its Singapore hour.
            {"$set": {
                "singapore_hour": {
                    "$hour": {
                        "date": "$start_time",
                        "timezone": "Asia/Singapore",
                    }
                }
            }},

            # Analyse only 06:00–23:59 Singapore time.
            {"$match": {
                "singapore_hour": {"$gte": 6}
            }},

            # Count valid and high readings for each line and hour.
            {"$group": {
                "_id": {
                    "line_code": "$line_code",
                    "hour": "$singapore_hour",
                },
                "valid_readings": {"$sum": 1},
                "high_readings": {
                    "$sum": {
                        "$cond": [
                            {"$eq": ["$crowd_level", "h"]},
                            1,
                            0,
                        ]
                    }
                },
                "first_observation": {"$min": "$start_time"},
                "last_observation": {"$max": "$start_time"},
            }},

            # Calculate the percentage of valid readings labelled High.
            {"$project": {
                "_id": 0,
                "line_code": "$_id.line_code",
                "hour": "$_id.hour",
                "valid_readings": 1,
                "high_readings": 1,
                "high_percentage": {
                    "$round": [
                        {
                            "$multiply": [
                                {
                                    "$divide": [
                                        "$high_readings",
                                        "$valid_readings",
                                    ]
                                },
                                100,
                            ]
                        },
                        1,
                    ]
                },
                "first_observation": 1,
                "last_observation": 1,
            }},

            {"$sort": {
                "line_code": 1,
                "hour": 1,
            }},
        ]))

        for row in rows:
            for field in ("first_observation", "last_observation"):
                row[field] = row[field].isoformat()

        response = jsonify({
            "station_code": station,
            "timezone": "Asia/Singapore",
            "data": rows,
            "count": len(rows),
        })

        response.headers["Cache-Control"] = "no-store"
        return response

    except PyMongoError:
        return jsonify({
            "error": "Busy-hour data is temporarily unavailable."
        }), 503

@bp.get("/alerts/latest")
def latest_train_alert():
    def as_list(value):
        if value is None or value == "":
            return []
        return value if isinstance(value, list) else [value]

    try:
        document = database.TrainServiceAlert.find_one(
            {},
            sort=[("fetched_at", -1), ("_id", -1)],
        )

        if document is None:
            response = jsonify({"data": None})
        else:
            payload = document.get("payload")

            if not isinstance(payload, dict):
                payload = {}

            status = str(
                payload.get("Status", document.get("status", ""))
            )

            labels = {
                "1": "Normal train service or minor delays",
                "2": "Disrupted train service or major delays",
            }

            last_checked = (
                document.get("last_seen_at")
                or document.get("fetched_at")
            )

            response = jsonify({
                "data": {
                    "status": status,
                    "status_label": labels.get(
                        status, "Service status unavailable"
                    ),
                    "affected_segments": as_list(
                        payload.get("AffectedSegments")
                    ),
                    "messages": as_list(payload.get("Message")),
                    "additional_details": {
                        key: value
                        for key, value in payload.items()
                        if key not in (
                            "Status", "AffectedSegments", "Message"
                        )
                    },
                    "last_checked": (
                        last_checked.isoformat()
                        if isinstance(last_checked, datetime)
                        else None
                    ),
                }
            })

        response.headers["Cache-Control"] = "no-store"
        return response

    except PyMongoError:
        return jsonify({
            "error": "Train-service information is temporarily unavailable."
        }), 503