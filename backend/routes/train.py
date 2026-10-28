from flask import Blueprint, jsonify, request
from mysql.connector import Error

import db

# Make sure each route is prefixed with /api/train, so that the frontend can be served from / without conflicting with the API.
bp = Blueprint("train", __name__, url_prefix="/api/train")

# MySQL error numbers
ERR_DUPLICATE = 1062       # duplicate primary key
ERR_FK_NO_PARENT = 1452    # child row refers to a missing parent
ERR_FK_HAS_CHILD = 1451    # parent row is still referenced


# ---------- helpers ----------
# Build a successful JSON response: {"data": ..., "count": n, ...extra}.
def ok(data, status=200, **extra):
    body = {"data": data}
    if isinstance(data, list):
        body["count"] = len(data)
    body.update(extra)
    return jsonify(body), status

# Build an error JSON response: {"error": "..."} with an HTTP status code.
def fail(message, status):
    return jsonify({"error": message}), status

# Read required and optional fields from a JSON request body, stripping whitespace and validating length.
def read_fields(required, optional=()):
    payload = request.get_json(silent=True)
    if not isinstance(payload, dict):
        return None, "Request body must be a JSON object"

    values = {}
    for name in required:
        value = str(payload.get(name, "")).strip()
        if not value:
            return None, f"'{name}' is required"
        values[name] = value
    for name in optional:
        if name in payload and payload[name] is not None:
            values[name] = str(payload[name]).strip()

    for name, value in values.items():
        limit = 10 if name.endswith("_code") else 100
        if len(value) > limit:
            return None, f"'{name}' must be at most {limit} characters"
    return values, None

# Handle MySQL errors and return a JSON response with an appropriate HTTP status code.
def db_error(error):
    if error.errno == ERR_DUPLICATE:
        return fail("A record with that code already exists", 409)
    if error.errno == ERR_FK_NO_PARENT:
        return fail("Referenced line or station does not exist", 400)
    if error.errno == ERR_FK_HAS_CHILD:
        return fail("Cannot delete: other records still depend on it", 409)
    return fail(f"Database error: {error.msg}", 500)


# Reusable ORDER BY clause for station code sorted by letter prefix, then by the number inside it (Eg. NS2 comes before NS10)
STATION_ORDER = """
    ORDER BY REGEXP_SUBSTR(s.station_code, '^[A-Za-z]+'),
             CAST(REGEXP_SUBSTR(s.station_code, '[0-9]+') AS UNSIGNED),
             s.station_code
"""


# ---------- READ ----------
# Search stations by English name, Chinese name or code; filter by line.
@bp.get("/stations")
def search_stations():
    q = request.args.get("q", "").strip()
    line = request.args.get("line", "").strip()
    limit = min(request.args.get("limit", 50, type=int), 500)
    offset = max(request.args.get("offset", 0, type=int), 0)

    sql = """
        SELECT s.station_code, s.station_name_english, s.station_name_chinese,
               l.line_code, l.line_name_english, l.line_name_chinese
        FROM TrainStation s
        JOIN StationLine sl ON sl.station_code = s.station_code
        JOIN TrainLine l    ON l.line_code = sl.line_code
        WHERE 1 = 1
    """
    params = []

    if q:
        sql += """ AND (s.station_name_english LIKE %s
                     OR s.station_name_chinese LIKE %s
                     OR s.station_code LIKE %s)"""
        like = f"%{q}%"
        params += [like, like, like]
    if line:
        sql += " AND l.line_code = %s"
        params.append(line)

    sql += STATION_ORDER + " LIMIT %s OFFSET %s"
    params += [limit, offset]

    try:
        return ok(db.query(sql, params), limit=limit, offset=offset)
    except Error as error:
        return db_error(error)

# Get a station by its code, including the lines it belongs to and any other stations with the same English name (interchange stations).
@bp.get("/stations/<code>")
def get_station(code):
    sql = """
        SELECT s.station_code, s.station_name_english, s.station_name_chinese,
               l.line_code, l.line_name_english, l.line_name_chinese
        FROM TrainStation s
        JOIN StationLine sl ON sl.station_code = s.station_code
        JOIN TrainLine l    ON l.line_code = sl.line_code
        WHERE s.station_code = %s
    """
    other_sql = """
        SELECT s2.station_code, l2.line_code, l2.line_name_english
        FROM TrainStation s2
        JOIN StationLine sl2 ON sl2.station_code = s2.station_code
        JOIN TrainLine l2    ON l2.line_code = sl2.line_code
        WHERE s2.station_name_english = %s AND s2.station_code <> %s
        ORDER BY s2.station_code
    """
    try:
        rows = db.query(sql, (code,))
        if not rows:
            return fail("Station not found", 404)
        station = rows[0]
        station["lines"] = [
            {"line_code": r["line_code"],
             "line_name_english": r["line_name_english"],
             "line_name_chinese": r["line_name_chinese"]}
            for r in rows
        ]
        station["interchange_with"] = db.query(
            other_sql, (station["station_name_english"], code))
        return ok(station)
    except Error as error:
        return db_error(error)

# List all train lines with their station counts.
@bp.get("/lines")
def list_lines():
    sql = """
        SELECT l.line_code, l.line_name_english, l.line_name_chinese,
               COUNT(sl.station_code) AS station_count
        FROM TrainLine l
        LEFT JOIN StationLine sl ON sl.line_code = l.line_code
        GROUP BY l.line_code, l.line_name_english, l.line_name_chinese
        ORDER BY station_count DESC, l.line_code
    """
    try:
        return ok(db.query(sql))
    except Error as error:
        return db_error(error)

# Get a train line by its code, including the number of stations it has.
@bp.get("/lines/<code>")
def get_line(code):
    sql = """
        SELECT l.line_code, l.line_name_english, l.line_name_chinese,
               COUNT(sl.station_code) AS station_count
        FROM TrainLine l
        LEFT JOIN StationLine sl ON sl.line_code = l.line_code
        WHERE l.line_code = %s
        GROUP BY l.line_code, l.line_name_english, l.line_name_chinese
    """
    try:
        line = db.query(sql, (code,), one=True)
        if line is None:
            return fail("Line not found", 404)
        return ok(line)
    except Error as error:
        return db_error(error)

# Get all stations on a train line, in numeric order of their station codes.
@bp.get("/lines/<code>/stations")
def line_stations(code):
    sql = f"""
        SELECT s.station_code, s.station_name_english, s.station_name_chinese
        FROM TrainStation s
        JOIN StationLine sl ON sl.station_code = s.station_code
        WHERE sl.line_code = %s
        {STATION_ORDER}
    """
    try:
        if db.query("SELECT 1 FROM TrainLine WHERE line_code = %s", (code,), one=True) is None:
            return fail("Line not found", 404)
        return ok(db.query(sql, (code,)), line_code=code)
    except Error as error:
        return db_error(error)


# ---------- CREATE ----------
# Create a new station and assign it to a line. The station code must be unique, and the line must already exist.
@bp.post("/stations")
def create_station():
    values, error = read_fields(
        ["station_code", "station_name_english", "station_name_chinese", "line_code"])
    if error:
        return fail(error, 400)
    try:
        with db.transaction() as cur:
            cur.execute(
                "INSERT INTO TrainStation (station_code, station_name_english, station_name_chinese) "
                "VALUES (%s, %s, %s)",
                (values["station_code"], values["station_name_english"], values["station_name_chinese"]))
            cur.execute(
                "INSERT INTO StationLine (line_code, station_code) VALUES (%s, %s)",
                (values["line_code"], values["station_code"]))
        return ok(values, 201)
    except Error as error:
        return db_error(error)

# Create a new train line. The line code must be unique.
@bp.post("/lines")
def create_line():
    values, error = read_fields(["line_code", "line_name_english", "line_name_chinese"])
    if error:
        return fail(error, 400)
    try:
        with db.transaction() as cur:
            cur.execute(
                "INSERT INTO TrainLine (line_code, line_name_english, line_name_chinese) "
                "VALUES (%s, %s, %s)",
                (values["line_code"], values["line_name_english"], values["line_name_chinese"]))
        return ok(values, 201)
    except Error as error:
        return db_error(error)


# ---------- UPDATE ----------
# Update a station's name and optionally its line. The station must exist, and the new line (if provided) must also exist.
@bp.put("/stations/<code>")
def update_station(code):
    values, error = read_fields(
        ["station_name_english", "station_name_chinese"], optional=["line_code"])
    if error:
        return fail(error, 400)
    try:
        with db.transaction() as cur:
            cur.execute("SELECT 1 FROM TrainStation WHERE station_code = %s", (code,))
            if cur.fetchone() is None:
                return fail("Station not found", 404)

            cur.execute(
                "UPDATE TrainStation SET station_name_english = %s, station_name_chinese = %s "
                "WHERE station_code = %s",
                (values["station_name_english"], values["station_name_chinese"], code))

            if values.get("line_code"):
                cur.execute("DELETE FROM StationLine WHERE station_code = %s", (code,))
                cur.execute(
                    "INSERT INTO StationLine (line_code, station_code) VALUES (%s, %s)",
                    (values["line_code"], code))
        values["station_code"] = code
        return ok(values)
    except Error as error:
        return db_error(error)

# Update a train line's name. The line must exist.
@bp.put("/lines/<code>")
def update_line(code):
    values, error = read_fields(["line_name_english", "line_name_chinese"])
    if error:
        return fail(error, 400)
    try:
        with db.transaction() as cur:
            cur.execute(
                "UPDATE TrainLine SET line_name_english = %s, line_name_chinese = %s "
                "WHERE line_code = %s",
                (values["line_name_english"], values["line_name_chinese"], code))
            if cur.rowcount == 0:
                cur.execute("SELECT 1 FROM TrainLine WHERE line_code = %s", (code,))
                if cur.fetchone() is None:
                    return fail("Line not found", 404)
        values["line_code"] = code
        return ok(values)
    except Error as error:
        return db_error(error)


# ---------- DELETE ----------
# Delete a station and its line assignments. The station must exist.
@bp.delete("/stations/<code>")
def delete_station(code):
    try:
        with db.transaction() as cur:
            cur.execute("DELETE FROM StationLine WHERE station_code = %s", (code,))
            cur.execute("DELETE FROM TrainStation WHERE station_code = %s", (code,))
            if cur.rowcount == 0:
                return fail("Station not found", 404)
        return ok({"deleted": code})
    except Error as error:
        return db_error(error)

# Delete a train line. The line must exist and cannot have any stations assigned to it.
@bp.delete("/lines/<code>")
def delete_line(code):
    """Blocked (409) while stations still belong to the line."""
    try:
        with db.transaction() as cur:
            cur.execute("DELETE FROM TrainLine WHERE line_code = %s", (code,))
            if cur.rowcount == 0:
                return fail("Line not found", 404)
        return ok({"deleted": code})
    except Error as error:
        return db_error(error)