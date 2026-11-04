USE Transitiq;

-- ----------------------------------------------
-- Query 1: Bus Route Details
-- ----------------------------------------------
-- Retrieves the bus stops along a selected bus service and direction.
-- Displays the stops in their correct sequence, including route distances.

SELECT route.service_no, route.direction, route.stop_seq, stop.bus_stop_code, 
	stop.description AS stop_name, stop.road_name, route.distance
FROM BusRoute AS route
INNER JOIN BusStop AS stop
ON route.bus_stop_code = stop.bus_stop_code
WHERE route.service_no = :service_no AND route.direction = :direction
ORDER BY route.stop_seq;

-- ----------------------------------------------
-- Query 2: Bus Service Origin and Destination
-- ----------------------------------------------
-- Retrieves the origin and destination bus stops for a selected bus service.
-- Uses joins to display the stop names for each direction.

SELECT service.service_no, service.direction, service.origin_code, 
	origin.description AS origin_stop, service.destination_code, 
    destination.description AS destination_stop
FROM BusService AS service
INNER JOIN BusStop AS origin 
ON service.origin_code = origin.bus_stop_code
INNER JOIN BusStop AS destination
ON service.destination_code = destination.bus_stop_code
WHERE service.service_no = :service_no
ORDER BY service.direction;

-- ----------------------------------------------
-- Query 3: Bus Route Statistics
-- ----------------------------------------------
-- Compares the number of stops and total distance for each bus service and direction.
-- Sorts the routes by the highest number of stops.

SELECT service_no, direction, COUNT(*) AS total_stops, MAX(distance) AS route_distance
FROM BusRoute
GROUP BY service_no, direction
ORDER BY total_stops DESC;

-- ----------------------------------------------
-- Query 4: Stops Served by Multiple Services
-- ----------------------------------------------
-- Identifies bus stops served by at least five distinct bus services.
-- Ranks the stops by the number of services available.

SELECT stop.bus_stop_code, stop.description, COUNT(DISTINCT route.service_no) AS total_services
FROM BusStop stop
JOIN BusRoute route
    ON stop.bus_stop_code = route.bus_stop_code
GROUP BY stop.bus_stop_code, stop.description
HAVING COUNT(DISTINCT route.service_no) >= 5
ORDER BY total_services DESC;

-- ----------------------------------------------
-- Query 5: Direct Bus Connection Finder
-- ----------------------------------------------
-- Finds bus services connecting two selected stops in the correct travel direction.

SELECT DISTINCT origin.service_no, origin.direction, origin.bus_stop_code AS origin_stop,
    destination.bus_stop_code AS destination_stop
FROM BusRoute AS origin
INNER JOIN BusRoute AS destination
    ON origin.service_no = destination.service_no
    AND origin.direction = destination.direction
WHERE origin.bus_stop_code = :origin_code
  AND destination.bus_stop_code = :destination_code
  AND origin.stop_seq < destination.stop_seq
ORDER BY origin.service_no, origin.direction;

-- ----------------------------------------------
-- Query 6: Bus Operator Comparison
-- ----------------------------------------------
-- Compares bus operators based on the number of services and routes.
-- Calculates the average and longest route distances for each operator.

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
ORDER BY total_services DESC;