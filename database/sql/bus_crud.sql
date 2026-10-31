-- TransitIQ Bus Database Queries - CRUD Operations
USE Transitiq;

START TRANSACTION;

-- ----------------------------------
-- CREATE: Insert test records
-- ----------------------------------

-- BusStop
INSERT INTO BusStop (
	bus_stop_code, road_name, description, 
	latitude, longitude
)
VALUES 
	('TEST01' , '83 Punggol Central', 'Waterway Point', 1.406603, 103.902071),
	('TEST02', '1 HarbourFront Walk', 'VivoCity', 1.263889, 103.822222);

-- BusService
INSERT INTO BusService (
	service_no, direction, operator, category, 
	origin_code, destination_code, 
	am_peak_freq, am_offpeak_freq, 
	pm_peak_freq, pm_offpeak_freq
)
VALUES (
	'SER39B', 1, 'SBST', 'TRUNK', 
	'TEST01', 'TEST02', 
	'08-09', '06-13', '08-09', '8-14'
);

-- BusRoute
INSERT INTO BusRoute (
	service_no, direction, stop_seq, bus_stop_code, distance, 
	wd_first_bus, wd_last_bus, sat_first_bus, sat_last_bus, 
	sun_first_bus, sun_last_bus
)
VALUES 
	('SER39B', 1, 1, 'TEST01', 0.000, '0530', '2330', '0600', '2300', '0630', '2230'), 
	('SER39B', 1, 2, 'TEST02', 1.500, '0535', '2335', '0605', '2305', '0635', '2235');


-- ----------------------------------
-- READ: Retrieve test records
-- ----------------------------------

-- BusStop
SELECT * FROM BusStop
WHERE bus_stop_code IN ('TEST01', 'TEST02');

-- BusService
SELECT * FROM BusService
WHERE service_no = 'SER39B' AND direction = 1;

-- BusRoute
SELECT * FROM BusRoute
WHERE service_no = 'SER39B' AND direction = 1
ORDER BY stop_seq;


-- ----------------------------------
-- UPDATE: Modify test records
-- ----------------------------------

-- BusStop
UPDATE BusStop
SET road_name = '3 Temasek Blvd', description = 'Suntec City'
WHERE bus_stop_code = 'TEST01';

-- Update BusService records
UPDATE BusService
SET category = 'FEEDER'
WHERE service_no = 'SER39B' AND direction = 1;

-- Update BusRoute records
UPDATE BusRoute
SET distance = 1.800
WHERE service_no = 'SER39B' AND direction = 1 AND stop_seq = 2;


-- Verify updated records
SELECT * FROM BusStop
WHERE bus_stop_code IN ('TEST01', 'TEST02');

SELECT * FROM BusService
WHERE service_no = 'SER39B' AND direction = 1;

SELECT * FROM BusRoute
WHERE service_no = 'SER39B' AND direction = 1
ORDER BY stop_seq;


-- ----------------------------------
-- DELETE: Remove test records
-- ----------------------------------

-- Delete child records before parent records

-- BusRoute
DELETE FROM BusRoute
WHERE service_no = 'SER39B' AND direction = 1;

-- BusService
DELETE FROM BusService
WHERE service_no = 'SER39B' AND direction = 1;

-- BusStop
DELETE FROM BusStop
WHERE bus_stop_code IN ('TEST01', 'TEST02');


-- ----------------------------------
-- ROLLBACK: Undo test changes
-- ----------------------------------
ROLLBACK;
