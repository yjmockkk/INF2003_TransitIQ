from flask import Blueprint, request
from mysql.connector import Error

import db
from routes.train import ok, fail, db_error

# All analytics endpoints live under /api/train/analytics
# They rely on the views v_station_details, v_interchange_stations and
# v_line_links, so run the "Views" section of train_advanced_queries.sql first.
bp = Blueprint("train_analytics", __name__, url_prefix="/api/train/analytics")


# Query 4: stations per line, share of the network, size rank
# (aggregate + window functions)
LINE_SIZES_SQL = """
    SELECT l.line_code, l.line_name_english,
        COUNT(sl.station_code) AS total_stations,
        ROUND(100 * COUNT(sl.station_code) / SUM(COUNT(sl.station_code)) OVER (), 1) AS pct_of_network,
        RANK() OVER (ORDER BY COUNT(sl.station_code) DESC) AS size_rank
    FROM TrainLine AS l
    LEFT JOIN StationLine AS sl
    ON l.line_code = sl.line_code
    GROUP BY l.line_code, l.line_name_english
    ORDER BY size_rank, l.line_code
"""

# Query 5: stations that sit on 2+ lines (from the interchange view)
INTERCHANGES_SQL = """
    SELECT station_name_english, station_name_chinese, total_lines,
        station_codes, line_codes
    FROM v_interchange_stations
    WHERE total_lines >= %(min_lines)s
    ORDER BY total_lines DESC, station_name_english
"""

# Query 6: pairs of lines and the interchanges they share (self-join)
LINE_CONNECTIONS_SQL = """
    SELECT a.line_code AS line_a, b.line_code AS line_b,
        COUNT(DISTINCT s1.station_name_english) AS shared_interchanges,
        GROUP_CONCAT(DISTINCT s1.station_name_english
            ORDER BY s1.station_name_english SEPARATOR ', ') AS interchange_stations
    FROM StationLine AS a
    INNER JOIN TrainStation AS s1
    ON s1.station_code = a.station_code
    INNER JOIN TrainStation AS s2
    ON s2.station_name_english = s1.station_name_english
    AND s2.station_code <> s1.station_code
    INNER JOIN StationLine AS b
    ON b.station_code = s2.station_code
    AND b.line_code > a.line_code
    GROUP BY a.line_code, b.line_code
    ORDER BY shared_interchanges DESC, line_a, line_b
"""

# Query 7: previous / next station on the same line (LAG / LEAD windows).
# The window is computed over the whole line first, then we pick one station.
NEIGHBOURS_SQL = """
    SELECT line_code, station_code, station_name_english,
        previous_station, next_station
    FROM (
        SELECT sl.line_code, s.station_code, s.station_name_english,
            LAG(s.station_name_english) OVER line_order AS previous_station,
            LEAD(s.station_name_english) OVER line_order AS next_station
        FROM TrainStation AS s
        INNER JOIN StationLine AS sl
        ON s.station_code = sl.station_code
        WINDOW line_order AS (
            PARTITION BY sl.line_code
            ORDER BY REGEXP_SUBSTR(s.station_code, '^[A-Za-z]+'),
                     CAST(REGEXP_SUBSTR(s.station_code, '[0-9]+') AS UNSIGNED)
        )
    ) AS ordered_stations
    WHERE station_code = %(station_code)s
"""

# Query 8: fewest-transfer route (recursive CTE over the line graph).
# NOTE: the literal % signs in the LIKE pattern are written as %% because the
# driver treats a single % as the start of a parameter placeholder.
ROUTE_SQL = """
    WITH RECURSIVE paths AS (
        SELECT line_code, 0 AS transfers, CAST(line_code AS CHAR(255)) AS path
        FROM StationLine
        WHERE station_code = %(from_station)s

        UNION ALL

        SELECT links.to_line, paths.transfers + 1,
            CONCAT(paths.path, ' > ', links.to_line)
        FROM paths
        INNER JOIN v_line_links AS links
        ON links.from_line = paths.line_code
        WHERE CONCAT(' > ', paths.path, ' > ') NOT LIKE CONCAT('%% > ', links.to_line, ' > %%')
        AND paths.transfers < %(max_transfers)s
    )
    SELECT transfers, path
    FROM paths
    WHERE line_code = (
        SELECT line_code FROM StationLine WHERE station_code = %(to_station)s
    )
    ORDER BY transfers, path
    LIMIT 5
"""

# Query 9: fewest-stops route over station NAMES (a line change is not a stop)
SHORTEST_PATH_SQL = """
    WITH RECURSIVE
    reach AS (
        SELECT CAST(%(from_name)s AS CHAR(100)) AS station_name, 0 AS hops
        UNION
        SELECT g.to_name, r.hops + 1
        FROM reach AS r
        INNER JOIN StationConnection AS g ON g.from_name = r.station_name
        WHERE r.hops < %(max_hops)s
    ),
    dist AS (
        SELECT station_name, MIN(hops) AS hops FROM reach GROUP BY station_name
    ),
    back AS (
        SELECT station_name, hops, CAST(station_name AS CHAR(2000)) AS path
        FROM dist
        WHERE station_name = %(to_name)s
        UNION ALL
        SELECT g.to_name, b.hops - 1, CONCAT(g.to_name, ',', b.path)
        FROM back AS b
        INNER JOIN StationConnection AS g ON g.from_name = b.station_name
        INNER JOIN dist AS d ON d.station_name = g.to_name AND d.hops = b.hops - 1
    )
    SELECT path
    FROM back
    WHERE hops = 0
    ORDER BY path
    LIMIT 1
"""

# One row per station on the path, with the line arriving and leaving
PATH_STEPS_SQL = """
    WITH stops AS (
        SELECT FIND_IN_SET(station_name_english, %(path)s) AS step,
            station_name_english,
            MIN(station_name_chinese) AS station_name_chinese,
            GROUP_CONCAT(station_code ORDER BY station_code) AS station_codes
        FROM TrainStation
        WHERE FIND_IN_SET(station_name_english, %(path)s) > 0
        GROUP BY station_name_english
    )
    SELECT s.step, s.station_name_english, s.station_name_chinese, s.station_codes,
        leg_in.line_code AS arrive_line,
        leg_out.line_code AS depart_line,
        CASE
            WHEN leg_in.line_code IS NULL THEN 'start'
            WHEN leg_out.line_code IS NULL THEN 'arrive'
            WHEN leg_in.line_code <> leg_out.line_code THEN 'change'
            ELSE 'pass'
        END AS action
    FROM stops AS s
    LEFT JOIN stops AS prev ON prev.step = s.step - 1
    LEFT JOIN StationConnection AS leg_in
        ON leg_in.from_name = prev.station_name_english AND leg_in.to_name = s.station_name_english
    LEFT JOIN stops AS nxt ON nxt.step = s.step + 1
    LEFT JOIN StationConnection AS leg_out
        ON leg_out.from_name = s.station_name_english AND leg_out.to_name = nxt.station_name_english
    ORDER BY s.step
"""

@bp.get("/line-sizes")
def line_sizes():
    """GET /api/train/analytics/line-sizes
    Stations per line, % of the network and size rank."""
    try:
        return ok(db.query(LINE_SIZES_SQL))
    except Error as error:
        return db_error(error)


@bp.get("/interchanges")
def interchanges():
    """GET /api/train/analytics/interchanges?min_lines=2
    Stations that appear on at least min_lines lines (default 2)."""
    min_lines = max(request.args.get("min_lines", 2, type=int), 2)
    try:
        return ok(db.query(INTERCHANGES_SQL, {"min_lines": min_lines}),
                  min_lines=min_lines)
    except Error as error:
        return db_error(error)


@bp.get("/line-connections")
def line_connections():
    """GET /api/train/analytics/line-connections
    For each pair of lines, the interchanges they share."""
    try:
        return ok(db.query(LINE_CONNECTIONS_SQL))
    except Error as error:
        return db_error(error)


@bp.get("/stations/<code>/neighbours")
def station_neighbours(code):
    """GET /api/train/analytics/stations/<code>/neighbours
    The stations before and after this one on its line."""
    try:
        row = db.query(NEIGHBOURS_SQL, {"station_code": code}, one=True)
        if row is None:
            return fail("Station not found", 404)
        return ok(row)
    except Error as error:
        return db_error(error)

@bp.get("/route")
def route():
    """GET /api/train/analytics/route?from=NS1&to=NE17&max_transfers=5
    Fewest-transfer line routes between two station codes."""
    from_station = request.args.get("from", "").strip()
    to_station = request.args.get("to", "").strip()
    # Cap the search depth so the recursion always stops quickly
    max_transfers = min(max(request.args.get("max_transfers", 5, type=int), 0), 8)

    if not from_station or not to_station:
        return fail("Both 'from' and 'to' station codes are required", 400)

    try:
        # Make sure both stations exist (also gives us their details for the response)
        details = {}
        for key, code in (("from", from_station), ("to", to_station)):
            row = db.query(
                "SELECT station_code, station_name_english, line_code "
                "FROM v_station_details WHERE station_code = %s", (code,), one=True)
            if row is None:
                return fail(f"Station '{code}' not found", 404)
            details[key] = row

        rows = db.query(ROUTE_SQL, {
            "from_station": from_station,
            "to_station": to_station,
            "max_transfers": max_transfers,
        })
        if not rows:
            return fail("No route found within the transfer limit", 404)

        # Turn "NSL > NEL" into a list of lines for the frontend
        routes = [{"transfers": r["transfers"],
                   "path": r["path"],
                   "lines": r["path"].split(" > ")} for r in rows]
        return ok({"from": details["from"], "to": details["to"],
                   "fewest_transfers": routes[0]["transfers"],
                   "routes": routes})
    except Error as error:
        return db_error(error)
    
@bp.get("/shortest-route")
def shortest_route():
    """GET /api/train/analytics/shortest-route?from=NS1&to=NE17&max_hops=40
    Route with the fewest stops. Changing line at an interchange is not a stop."""
    from_code = request.args.get("from", "").strip()
    to_code = request.args.get("to", "").strip()
    max_hops = min(max(request.args.get("max_hops", 40, type=int), 1), 100)

    if not from_code or not to_code:
        return fail("Both 'from' and 'to' station codes are required", 400)

    try:
        # Look up the station name for each code (the route runs on names)
        names = {}
        for code in (from_code, to_code):
            row = db.query(
                "SELECT station_name_english FROM TrainStation WHERE station_code = %s",
                (code,), one=True)
            if row is None:
                return fail(f"Station '{code}' not found", 404)
            names[code] = row["station_name_english"]

        found = db.query(SHORTEST_PATH_SQL, {
            "from_name": names[from_code],
            "to_name": names[to_code],
            "max_hops": max_hops,
        }, one=True)
        if found is None:
            return fail("No route found within max_hops", 404)

        steps = db.query(PATH_STEPS_SQL, {"path": found["path"]})
        return ok({
            "from": {"station_code": from_code, "station_name_english": names[from_code]},
            "to": {"station_code": to_code, "station_name_english": names[to_code]},
            "total_stops": len(steps) - 1,
            "line_changes": sum(1 for s in steps if s["action"] == "change"),
            "steps": steps,
        })
    except Error as error:
        return db_error(error)