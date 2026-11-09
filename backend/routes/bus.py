from flask import Blueprint, jsonify, request
from mysql.connector import Error
import math
import re

import db

bp = Blueprint("bus", __name__, url_prefix="/api/bus")

# ----------------------------------------------
# Database Error Handler
# ----------------------------------------------
@bp.errorhandler(Error)
def handle_database_error(error):
    # Keep database details in the server logs.
    from flask import current_app
    current_app.logger.exception("Bus database query failed")
    if error.errno == 1062:
        return jsonify({"error": "A record with this primary key already exists"}), 409
    if error.errno == 1451:
        return jsonify({"error": "This record is referenced by another table. Remove or update the dependent records first."}), 409
    if error.errno == 1452:
        return jsonify({"error": "A referenced bus stop or service does not exist. Create it first."}), 409
    if error.errno in (1048, 1264, 1292, 1366, 1406, 3819, 4025):
        return jsonify({"error": "A value does not match the database column type, length, or constraint"}), 400
    return jsonify({"error": "Database query failed"}), 500

# ----------------------------------------------
# Bus Information APIs (READ)
# ----------------------------------------------

# Search bus stops by code, road name or description.
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

# Retrieve all bus services.
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

# Retrieve the ordered bus stops along a service and direction.
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


# ----------------------------------------------
# CRUD Input Validation and Helper Functions
# ----------------------------------------------
class InvalidInput(ValueError):
    pass


@bp.errorhandler(InvalidInput)
def handle_invalid_input(error):
    return jsonify({"error": str(error)}), 400


STOP_FIELDS = (
    "bus_stop_code", "road_name", "description",
    "latitude", "longitude",
)

SERVICE_FIELDS = (
    "service_no", "direction", "operator", "category",
    "origin_code", "destination_code",
    "am_peak_freq", "am_offpeak_freq",
    "pm_peak_freq", "pm_offpeak_freq",
)

ROUTE_FIELDS = (
    "service_no", "direction", "stop_seq",
    "bus_stop_code", "distance",
    "wd_first_bus", "wd_last_bus",
    "sat_first_bus", "sat_last_bus",
    "sun_first_bus", "sun_last_bus",
)

SERVICE_OPTIONAL = SERVICE_FIELDS[6:]
ROUTE_OPTIONAL = ROUTE_FIELDS[5:]


def validate_value(field, value):
    if value is None or isinstance(value, (bool, list, dict)):
        raise InvalidInput(f"{field} must contain a valid value")

    value = str(value).strip()

    if not value:
        raise InvalidInput(f"{field} is required")

    if field in ("direction", "stop_seq"):
        if not re.fullmatch(r"[0-9]+", value):
            raise InvalidInput(f"{field} must be a whole number")

        value = int(value)

        if field == "direction" and value not in (1, 2):
            raise InvalidInput("direction must be 1 or 2")

        if field == "stop_seq" and value < 1:
            raise InvalidInput("stop_seq must be at least 1")

    elif field in ("latitude", "longitude", "distance"):
        try:
            value = float(value)
        except (ValueError, OverflowError):
            raise InvalidInput(f"{field} must be a number")

        if not math.isfinite(value):
            raise InvalidInput(f"{field} must be finite")

        if field == "latitude" and not -90 <= value <= 90:
            raise InvalidInput("latitude must be between -90 and 90")

        if field == "longitude" and not -180 <= value <= 180:
            raise InvalidInput("longitude must be between -180 and 180")

        if field == "distance" and value < 0:
            raise InvalidInput("distance cannot be negative")

    elif field.endswith("_bus"):
        if (
            not re.fullmatch(r"[0-9]{4}", value)
            or int(value[2:]) > 59
        ):
            raise InvalidInput(
                f"{field} must be HHMM, e.g. 0530 or 2530"
            )

    return value


def read_data(allowed, required=(), optional=()):
    data = request.get_json(silent=True)

    if not isinstance(data, dict) or not data:
        raise InvalidInput("Send a non-empty JSON object")

    unknown = set(data) - set(allowed)

    if unknown:
        raise InvalidInput(
            "Unknown or non-editable fields: " +
            ", ".join(sorted(unknown))
        )

    missing = [field for field in required if field not in data]

    if missing:
        raise InvalidInput("Missing fields: " + ", ".join(missing))

    cleaned = {}

    for field, value in data.items():
        if field in optional:
            # Blank optional inputs are left unchanged on updates.
            if isinstance(value, str) and not value.strip():
                continue

            # API clients may explicitly clear nullable columns.
            if value is None:
                cleaned[field] = None
                continue

        cleaned[field] = validate_value(field, value)

    if not cleaned:
        raise InvalidInput("Provide at least one field")

    return cleaned

# ----------------------------------------------
# Bus Stop CRUD Operations
# ----------------------------------------------
# Primary key: bus_stop_code

# Example: POST /api/bus/stops
@bp.post("/stops")
def create_stop():
    data = read_data(
        allowed=STOP_FIELDS,
        required=STOP_FIELDS,
    )

    with db.transaction() as cursor:
        cursor.execute("""
            INSERT INTO BusStop (
                bus_stop_code, road_name, description,
                latitude, longitude
            )
            VALUES (%s, %s, %s, %s, %s)
        """, (
            data["bus_stop_code"],
            data["road_name"],
            data["description"],
            data["latitude"],
            data["longitude"],
        ))

    return jsonify({
        "message": "Bus stop created",
        "bus_stop_code": data["bus_stop_code"],
    }), 201

# Example: GET /api/bus/stops/TEST01
@bp.get("/stops/<bus_stop_code>")
def get_stop(bus_stop_code):
    row = db.query("""
        SELECT bus_stop_code, road_name, description,
               latitude, longitude
        FROM BusStop
        WHERE bus_stop_code = %s
    """, (bus_stop_code,), one=True)

    if row is None:
        return jsonify({"error": "Bus stop not found"}), 404

    return jsonify({"data": [row], "count": 1})

# Example: PUT /api/bus/stops/TEST01
@bp.put("/stops/<bus_stop_code>")
def update_stop(bus_stop_code):
    # Only non-key fields may be updated.
    data = read_data(
        allowed=STOP_FIELDS[1:],
    )

    # Field names are validated against STOP_FIELDS above.
    assignments = ", ".join(f"`{field}` = %s" for field in data)

    with db.transaction() as cursor:
        cursor.execute("""
            SELECT bus_stop_code
            FROM BusStop
            WHERE bus_stop_code = %s
            FOR UPDATE
        """, (bus_stop_code,))

        if cursor.fetchone() is None:
            return jsonify({"error": "Bus stop not found"}), 404

        cursor.execute(f"""
            UPDATE BusStop
            SET {assignments}
            WHERE bus_stop_code = %s
        """, tuple(data.values()) + (bus_stop_code,))

    return jsonify({"message": "Bus stop updated"})

# Example: DELETE /api/bus/stops/TEST01
@bp.delete("/stops/<bus_stop_code>")
def delete_stop(bus_stop_code):
    with db.transaction() as cursor:
        cursor.execute("""
            DELETE FROM BusStop
            WHERE bus_stop_code = %s
        """, (bus_stop_code,))

        deleted = cursor.rowcount

    if deleted == 0:
        return jsonify({"error": "Bus stop not found"}), 404

    return jsonify({"message": "Bus stop deleted"})

# ----------------------------------------------
# Bus Service CRUD Operations
# ----------------------------------------------
# Primary key: service_no + direction

# Example: POST /api/bus/services
@bp.post("/services")
def create_service():
    data = read_data(
        allowed=SERVICE_FIELDS,
        required=SERVICE_FIELDS[:6],
        optional=SERVICE_OPTIONAL,
    )

    with db.transaction() as cursor:
        cursor.execute("""
            INSERT INTO BusService (
                service_no, direction, operator, category,
                origin_code, destination_code,
                am_peak_freq, am_offpeak_freq,
                pm_peak_freq, pm_offpeak_freq
            )
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        """, (
            data["service_no"],
            data["direction"],
            data["operator"],
            data["category"],
            data["origin_code"],
            data["destination_code"],
            data.get("am_peak_freq"),
            data.get("am_offpeak_freq"),
            data.get("pm_peak_freq"),
            data.get("pm_offpeak_freq"),
        ))

    return jsonify({
        "message": "Bus service created",
        "service_no": data["service_no"],
        "direction": data["direction"],
    }), 201

# Example: GET /api/bus/services/SER39B/1
@bp.get("/services/<service_no>/<direction>")
def get_service(service_no, direction):
    direction = validate_value("direction", direction)

    row = db.query("""
        SELECT service_no, direction, operator, category,
               origin_code, destination_code,
               am_peak_freq, am_offpeak_freq,
               pm_peak_freq, pm_offpeak_freq
        FROM BusService
        WHERE service_no = %s AND direction = %s
    """, (service_no, direction), one=True)

    if row is None:
        return jsonify({"error": "Bus service not found"}), 404

    return jsonify({"data": [row], "count": 1})

# Example: PUT /api/bus/services/SER39B/1
@bp.put("/services/<service_no>/<direction>")
def update_service(service_no, direction):
    direction = validate_value("direction", direction)

    data = read_data(
        allowed=SERVICE_FIELDS[2:],
        optional=SERVICE_OPTIONAL,
    )

    assignments = ", ".join(f"`{field}` = %s" for field in data)

    with db.transaction() as cursor:
        cursor.execute("""
            SELECT service_no
            FROM BusService
            WHERE service_no = %s AND direction = %s
            FOR UPDATE
        """, (service_no, direction))

        if cursor.fetchone() is None:
            return jsonify({"error": "Bus service not found"}), 404

        cursor.execute(f"""
            UPDATE BusService
            SET {assignments}
            WHERE service_no = %s AND direction = %s
        """, tuple(data.values()) + (service_no, direction))

    return jsonify({"message": "Bus service updated"})

# Example: DELETE /api/bus/services/SER39B/1
@bp.delete("/services/<service_no>/<direction>")
def delete_service(service_no, direction):
    direction = validate_value("direction", direction)

    with db.transaction() as cursor:
        cursor.execute("""
            DELETE FROM BusService
            WHERE service_no = %s AND direction = %s
        """, (service_no, direction))

        deleted = cursor.rowcount

    if deleted == 0:
        return jsonify({"error": "Bus service not found"}), 404

    return jsonify({"message": "Bus service deleted"})


# ----------------------------------------------
# Bus Route CRUD Operations
# ----------------------------------------------
# Primary key: service_no + direction + stop_seq

# Example: GET /api/bus/routes?limit=50
@bp.get("/routes")
def list_routes():
    limit = request.args.get("limit", 50, type=int)
    limit = max(1, min(limit, 500))

    rows = db.query("""
        SELECT service_no, direction, stop_seq,
               bus_stop_code, distance,
               wd_first_bus, wd_last_bus,
               sat_first_bus, sat_last_bus,
               sun_first_bus, sun_last_bus
        FROM BusRoute
        ORDER BY service_no, direction, stop_seq
        LIMIT %s
    """, (limit,))

    return jsonify({"data": rows, "count": len(rows)})

# Example: POST /api/bus/routes
@bp.post("/routes")
def create_route():
    data = read_data(
        allowed=ROUTE_FIELDS,
        required=ROUTE_FIELDS[:5],
        optional=ROUTE_OPTIONAL,
    )

    with db.transaction() as cursor:
        cursor.execute("""
            INSERT INTO BusRoute (
                service_no, direction, stop_seq,
                bus_stop_code, distance,
                wd_first_bus, wd_last_bus,
                sat_first_bus, sat_last_bus,
                sun_first_bus, sun_last_bus
            )
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        """, (
            data["service_no"],
            data["direction"],
            data["stop_seq"],
            data["bus_stop_code"],
            data["distance"],
            data.get("wd_first_bus"),
            data.get("wd_last_bus"),
            data.get("sat_first_bus"),
            data.get("sat_last_bus"),
            data.get("sun_first_bus"),
            data.get("sun_last_bus"),
        ))

    return jsonify({
        "message": "Bus route entry created",
        "service_no": data["service_no"],
        "direction": data["direction"],
        "stop_seq": data["stop_seq"],
    }), 201

# Example: GET /api/bus/routes/SER39B/1/1
@bp.get("/routes/<service_no>/<direction>/<stop_seq>")
def get_route_entry(service_no, direction, stop_seq):
    direction = validate_value("direction", direction)
    stop_seq = validate_value("stop_seq", stop_seq)

    row = db.query("""
        SELECT service_no, direction, stop_seq,
               bus_stop_code, distance,
               wd_first_bus, wd_last_bus,
               sat_first_bus, sat_last_bus,
               sun_first_bus, sun_last_bus
        FROM BusRoute
        WHERE service_no = %s
          AND direction = %s
          AND stop_seq = %s
    """, (service_no, direction, stop_seq), one=True)

    if row is None:
        return jsonify({"error": "Bus route entry not found"}), 404

    return jsonify({"data": [row], "count": 1})

# Example: PUT /api/bus/routes/SER39B/1/1
@bp.put("/routes/<service_no>/<direction>/<stop_seq>")
def update_route(service_no, direction, stop_seq):
    direction = validate_value("direction", direction)
    stop_seq = validate_value("stop_seq", stop_seq)

    data = read_data(
        allowed=ROUTE_FIELDS[3:],
        optional=ROUTE_OPTIONAL,
    )

    assignments = ", ".join(f"`{field}` = %s" for field in data)

    with db.transaction() as cursor:
        cursor.execute("""
            SELECT service_no
            FROM BusRoute
            WHERE service_no = %s
              AND direction = %s
              AND stop_seq = %s
            FOR UPDATE
        """, (service_no, direction, stop_seq))

        if cursor.fetchone() is None:
            return jsonify({"error": "Bus route entry not found"}), 404

        cursor.execute(f"""
            UPDATE BusRoute
            SET {assignments}
            WHERE service_no = %s
              AND direction = %s
              AND stop_seq = %s
        """, tuple(data.values()) + (
            service_no, direction, stop_seq,
        ))

    return jsonify({"message": "Bus route entry updated"})

# Example: DELETE /api/bus/routes/SER39B/1/1
@bp.delete("/routes/<service_no>/<direction>/<stop_seq>")
def delete_route(service_no, direction, stop_seq):
    direction = validate_value("direction", direction)
    stop_seq = validate_value("stop_seq", stop_seq)

    with db.transaction() as cursor:
        cursor.execute("""
            DELETE FROM BusRoute
            WHERE service_no = %s
              AND direction = %s
              AND stop_seq = %s
        """, (service_no, direction, stop_seq))

        deleted = cursor.rowcount

    if deleted == 0:
        return jsonify({"error": "Bus route entry not found"}), 404

    return jsonify({"message": "Bus route entry deleted"})