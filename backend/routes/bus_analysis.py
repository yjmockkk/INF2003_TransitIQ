from flask import Blueprint, jsonify, request
import db

bus_analysis_bp = Blueprint("bus_analysis", __name__)

# Query 1: Direct Bus Connections
# Find bus services connecting two stops in the correct order.
@bus_analysis_bp.get("/api/bus/analysis/direct-connections")
def direct_connections():
    origin_code = request.args.get("origin_code", "").strip()
    destination_code = request.args.get("destination_code", "").strip()

    if not origin_code or not destination_code:
        return jsonify({
            "error": "Origin and destination stop codes are required"
        }), 400

    if origin_code == destination_code:
        return jsonify({
            "error": "Origin and destination must be different"
        }), 400

    sql = """
        SELECT DISTINCT
            origin.bus_stop_code AS origin_stop,
            destination.bus_stop_code AS destination_stop,
            origin.service_no,
            origin.direction
        FROM BusRoute AS origin
        INNER JOIN BusRoute AS destination
            ON origin.service_no = destination.service_no
            AND origin.direction = destination.direction
        WHERE origin.bus_stop_code = %s
          AND destination.bus_stop_code = %s
          AND origin.stop_seq < destination.stop_seq
        ORDER BY origin.service_no, origin.direction
    """

    results = db.query(sql, (origin_code, destination_code))
    return jsonify({"data": results})


# Query 2: Bus Stop Connectivity
# Find stops served by at least five distinct bus services.
@bus_analysis_bp.get("/api/bus/analysis/stop-connectivity")
def stop_connectivity():
    sql = """
        SELECT
            stop.bus_stop_code,
            stop.description AS stop_name,
            COUNT(DISTINCT route.service_no) AS total_services
        FROM BusStop AS stop
        INNER JOIN BusRoute AS route
            ON stop.bus_stop_code = route.bus_stop_code
        GROUP BY stop.bus_stop_code, stop.description
        HAVING COUNT(DISTINCT route.service_no) >= 5
        ORDER BY total_services DESC
    """

    results = db.query(sql)
    return jsonify({"data": results})

# Query 3: Bus Operator Comparison
# Compare operators based on services, routes and distances.
@bus_analysis_bp.get("/api/bus/analysis/operator-comparison")
def operator_comparison():
    sql = """
        SELECT
            operator,
            COUNT(DISTINCT service_no) AS total_services,
            COUNT(*) AS total_routes,
            ROUND(AVG(route_distance), 2) AS avg_route_distance,
            MAX(route_distance) AS longest_route_distance
        FROM (
            SELECT
                service.operator,
                route.service_no,
                route.direction,
                MAX(route.distance) AS route_distance
            FROM BusService AS service
            INNER JOIN BusRoute AS route
                ON service.service_no = route.service_no
                AND service.direction = route.direction
            GROUP BY
                service.operator,
                route.service_no,
                route.direction
        ) AS operator_routes
        GROUP BY operator
        ORDER BY total_services DESC
    """

    results = db.query(sql)
    return jsonify({"data": results})
