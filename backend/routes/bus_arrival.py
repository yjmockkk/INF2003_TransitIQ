import os
from datetime import datetime, timedelta, timezone
from pathlib import Path

from bson import ObjectId
from dotenv import load_dotenv
from flask import Blueprint, jsonify, request
from pymongo import MongoClient
from pymongo.errors import PyMongoError

load_dotenv(Path(__file__).resolve().parents[1] / ".env")

# MongoClient connects lazily, so the app still starts if MongoDB is off
client = MongoClient(
    os.getenv("MONGO_URI", "mongodb://localhost:27017/"),
    serverSelectionTimeoutMS=5000,
    tz_aware=True,
)
arrivals = client[os.getenv("MONGO_DB", "TransitIQ")]["BusArrival"]

bp = Blueprint("bus_arrival", __name__, url_prefix="/api/bus-arrivals")

SGT = timezone(timedelta(hours=8))


@bp.errorhandler(PyMongoError)
def handle_mongo_error(error):
    from flask import current_app
    current_app.logger.exception("MongoDB query failed")
    return jsonify({"error": "MongoDB query failed"}), 500


# ---------- helpers ----------
# Convert MongoDB values (ObjectId, UTC datetimes) into JSON-friendly values.
def to_json(value):
    if isinstance(value, dict):
        return {key: to_json(item) for key, item in value.items()}
    if isinstance(value, list):
        return [to_json(item) for item in value]
    if isinstance(value, ObjectId):
        return str(value)
    if isinstance(value, datetime):
        return value.astimezone(SGT).isoformat(timespec="seconds")
    return value


# Read ?hours= (default 24, between 1 and 168) and return the cut-off time.
def since_hours():
    hours = request.args.get("hours", 24, type=int)
    hours = max(1, min(hours, 168))
    return hours, datetime.now(timezone.utc) - timedelta(hours=hours)


# ---------- READ ----------
# Example: /api/bus-arrivals/stops
# List the monitored stops with how many snapshots each has.
@bp.get("/stops")
def list_stops():
    rows = arrivals.aggregate([
        {"$group": {
            "_id": "$bus_stop_code",
            "bus_stop_name": {"$first": "$bus_stop_name"},
            "snapshots": {"$sum": 1},
            "first_fetched_at": {"$min": "$fetched_at"},
            "last_fetched_at": {"$max": "$fetched_at"},
        }},
        {"$sort": {"_id": 1}},
        {"$project": {
            "_id": 0,
            "bus_stop_code": "$_id",
            "bus_stop_name": 1,
            "snapshots": 1,
            "first_fetched_at": 1,
            "last_fetched_at": 1,
        }},
    ])
    rows = to_json(list(rows))
    return jsonify({"data": rows, "count": len(rows)})


# Example: /api/bus-arrivals/75009/latest
# The most recent snapshot for one stop.
@bp.get("/<stop_code>/latest")
def latest(stop_code):
    document = arrivals.find_one(
        {"bus_stop_code": stop_code},
        {"_id": 0},
        sort=[("fetched_at", -1)],
    )

    if document is None:
        return jsonify({"error": "No arrival data for this stop"}), 404

    return jsonify({"data": to_json(document)})


# Example: /api/bus-arrivals/75009/history?service=15&hours=24
# Past snapshots for one service at one stop.
@bp.get("/<stop_code>/history")
def history(stop_code):
    service = request.args.get("service", "").strip()

    if not service:
        return jsonify({"error": "'service' is required"}), 400

    hours, since = since_hours()

    # "services.$" returns only the array element that matched the query
    documents = arrivals.find(
        {
            "bus_stop_code": stop_code,
            "fetched_at": {"$gte": since},
            "services.service_no": service,
        },
        {"_id": 0, "fetched_at": 1, "services.$": 1},
    ).sort("fetched_at", -1).limit(500)

    rows = []
    for document in documents:
        next_buses = document["services"][0]["next_buses"]
        first = next_buses[0] if next_buses else {}
        rows.append({
            "fetched_at": document["fetched_at"],
            "next_bus_minutes": first.get("minutes_away"),
            "load": first.get("load"),
            "bus_type": first.get("bus_type"),
            "buses_coming": len(next_buses),
        })

    rows = to_json(rows)
    return jsonify({
        "data": rows,
        "count": len(rows),
        "service": service,
        "hours": hours,
    })


# ---------- ADVANCED (aggregation pipelines) ----------
# Example: /api/bus-arrivals/75009/average-wait?hours=24
# Average waiting time for the next bus, per service, over a time window.
@bp.get("/<stop_code>/average-wait")
def average_wait(stop_code):
    hours, since = since_hours()

    rows = arrivals.aggregate([
        {"$match": {
            "bus_stop_code": stop_code,
            "fetched_at": {"$gte": since},
        }},
        {"$unwind": "$services"},
        {"$project": {
            "service_no": "$services.service_no",
            "wait": {"$arrayElemAt": ["$services.next_buses.minutes_away", 0]},
        }},
        {"$match": {"wait": {"$ne": None}}},
        # A bus already at the stop can have an ETA slightly in the past.
        # LTA treats that as "arriving", so count it as 0 minutes.
        {"$set": {"wait": {"$max": [0, "$wait"]}}},
        {"$group": {
            "_id": "$service_no",
            "average_wait": {"$avg": "$wait"},
            "shortest_wait": {"$min": "$wait"},
            "longest_wait": {"$max": "$wait"},
            "snapshots": {"$sum": 1},
        }},
        {"$sort": {"average_wait": 1}},
        {"$project": {
            "_id": 0,
            "service_no": "$_id",
            "average_wait": {"$round": ["$average_wait", 1]},
            "shortest_wait": 1,
            "longest_wait": 1,
            "snapshots": 1,
        }},
    ])
    rows = list(rows)
    return jsonify({"data": rows, "count": len(rows), "hours": hours})


# Example: /api/bus-arrivals/75009/crowding?hours=24
# How often incoming buses had seats, standing room or limited standing.
@bp.get("/<stop_code>/crowding")
def crowding(stop_code):
    hours, since = since_hours()

    rows = arrivals.aggregate([
        {"$match": {
            "bus_stop_code": stop_code,
            "fetched_at": {"$gte": since},
        }},
        {"$unwind": "$services"},
        {"$unwind": "$services.next_buses"},
        {"$group": {
            "_id": "$services.next_buses.load",
            "buses": {"$sum": 1},
        }},
        {"$group": {
            "_id": None,
            "total": {"$sum": "$buses"},
            "levels": {"$push": {"load": "$_id", "buses": "$buses"}},
        }},
        {"$unwind": "$levels"},
        {"$project": {
            "_id": 0,
            "load": "$levels.load",
            "buses": "$levels.buses",
            "percent": {"$round": [
                {"$multiply": [{"$divide": ["$levels.buses", "$total"]}, 100]},
                1,
            ]},
        }},
        {"$sort": {"buses": -1}},
    ])
    rows = list(rows)
    return jsonify({"data": rows, "count": len(rows), "hours": hours})


# ---------- UPDATE ----------
# Example: PUT /api/bus-arrivals/75009/name
# Body: {"bus_stop_name": "Tampines Bus Interchange"}
# Rename a stop in every snapshot saved for it.
@bp.put("/<stop_code>/name")
def rename_stop(stop_code):
    payload = request.get_json(silent=True)

    if not isinstance(payload, dict):
        return jsonify({"error": "Request body must be a JSON object"}), 400

    new_name = str(payload.get("bus_stop_name", "")).strip()

    if not new_name:
        return jsonify({"error": "'bus_stop_name' is required"}), 400

    if len(new_name) > 100:
        return jsonify({"error": "'bus_stop_name' must be at most 100 characters"}), 400

    result = arrivals.update_many(
        {"bus_stop_code": stop_code},
        {"$set": {"bus_stop_name": new_name}},
    )

    if result.matched_count == 0:
        return jsonify({"error": "No arrival data for this stop"}), 404

    return jsonify({
        "data": {
            "bus_stop_code": stop_code,
            "bus_stop_name": new_name,
            "snapshots_matched": result.matched_count,
            "snapshots_updated": result.modified_count,
        }
    })


# ---------- DELETE ----------
# Example: DELETE /api/bus-arrivals/old?days=7
# Remove snapshots older than the given number of days.
@bp.delete("/old")
def delete_old():
    days = request.args.get("days", 7, type=int)

    if days < 1:
        return jsonify({"error": "'days' must be at least 1"}), 400

    cutoff = datetime.now(timezone.utc) - timedelta(days=days)
    result = arrivals.delete_many({"fetched_at": {"$lt": cutoff}})

    return jsonify({
        "data": {
            "deleted": result.deleted_count,
            "older_than": to_json(cutoff),
        }
    })
