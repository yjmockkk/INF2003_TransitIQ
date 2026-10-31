-- TransitIQ Bus Database - Advanced SQL Queries
USE Transitiq;

-- ----------------------------------------------
-- Query 1: Bus Route Details
-- ----------------------------------------------
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
-- Query 3: Number of Stops per Route
-- ----------------------------------------------
SELECT service_no, direction, COUNT(*) AS total_stops
FROM BusRoute
GROUP BY service_no, direction
ORDER BY total_stops DESC;

-- ----------------------------------------------
-- Query 4: Stops Served by Multiple Services
-- ----------------------------------------------
SELECT stop.bus_stop_code, stop.description, COUNT(DISTINCT route.service_no) AS total_services
FROM BusStop stop
JOIN BusRoute route
    ON stop.bus_stop_code = route.bus_stop_code
GROUP BY stop.bus_stop_code, stop.description
HAVING COUNT(DISTINCT route.service_no) >= 5
ORDER BY total_services DESC;

-- ----------------------------------------------
-- Query 5: Longest Bus Routes
-- ----------------------------------------------
SELECT service_no, direction, MAX(distance) AS route_distance
FROM BusRoute
GROUP BY service_no, direction
ORDER BY route_distance DESC
LIMIT 10;