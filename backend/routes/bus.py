from flask import Blueprint, jsonify, request
from mysql.connector import Error

import db

bp = Blueprint("bus", __name__, url_prefix="/api/bus")


@bp.errorhandler(Error)
def handle_database_error(error):
    # Keep database details in the server logs.
    from flask import current_app
    current_app.logger.exception("Bus database query failed")
    return jsonify({"error": "Database query failed"}), 500


# Example: /api/bus/stops?q=orchard
@bp.get("/stops")
def search_stops():
    q = request.args.get("q", "").strip()
    limit = request.args.get("limit", 50, type=int)
    limit = max(1, min(limit, 500))

    search = f"%{q}%"

    rows = db.query("""
        SELECT bus_stop_code, road_name, description,
               latitude, longitude
        FROM BusStop
        WHERE bus_stop_code LIKE %s
           OR road_name LIKE %s
           OR description LIKE %s
        ORDER BY bus_stop_code
        LIMIT %s
    """, (search, search, search, limit))

    return jsonify({"data": rows, "count": len(rows)})


# Example: /api/bus/services
@bp.get("/services")
def list_services():
    rows = db.query("""
        SELECT service_no, direction, operator, category,
               origin_code, destination_code
        FROM BusService
        ORDER BY service_no, direction
    """)

    return jsonify({"data": rows, "count": len(rows)})


# Example: /api/bus/services/27/route?direction=1
@bp.get("/services/<service_no>/route")
def get_route(service_no):
    direction = request.args.get("direction", "1")

    if direction not in ("1", "2"):
        return jsonify({"error": "direction must be 1 or 2"}), 400

    service = db.query("""
        SELECT service_no
        FROM BusService
        WHERE service_no = %s AND direction = %s
    """, (service_no, int(direction)), one=True)

    if service is None:
        return jsonify({"error": "Bus service direction not found"}), 404

    rows = db.query("""
        SELECT r.stop_seq, r.bus_stop_code,
               s.description, s.road_name,
               s.latitude, s.longitude, r.distance,
               r.wd_first_bus, r.wd_last_bus
        FROM BusRoute r
        JOIN BusStop s ON s.bus_stop_code = r.bus_stop_code
        WHERE r.service_no = %s AND r.direction = %s
        ORDER BY r.stop_seq
    """, (service_no, int(direction)))

    return jsonify({"data": rows, "count": len(rows)})