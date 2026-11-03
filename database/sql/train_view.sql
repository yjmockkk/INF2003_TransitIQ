USE Transitiq;

-- View for detailed station information including line details
CREATE OR REPLACE VIEW v_station_details AS
SELECT s.station_code, s.station_name_english, s.station_name_chinese,
    l.line_code, l.line_name_english, l.line_name_chinese
FROM TrainStation AS s
INNER JOIN StationLine AS sl
ON s.station_code = sl.station_code
INNER JOIN TrainLine AS l
ON sl.line_code = l.line_code;

-- View for interchange stations with the number of lines and their codes
CREATE OR REPLACE VIEW v_interchange_stations AS
SELECT s.station_name_english, s.station_name_chinese,
    COUNT(DISTINCT sl.line_code) AS total_lines,
    GROUP_CONCAT(s.station_code ORDER BY s.station_code SEPARATOR ', ') AS station_codes,
    GROUP_CONCAT(sl.line_code ORDER BY sl.line_code SEPARATOR ', ') AS line_codes
FROM TrainStation AS s
INNER JOIN StationLine AS sl
ON s.station_code = sl.station_code
GROUP BY s.station_name_english, s.station_name_chinese
HAVING COUNT(DISTINCT sl.line_code) >= 2;

-- View for links between different lines at interchange stations
CREATE OR REPLACE VIEW v_line_links AS
SELECT DISTINCT a.line_code AS from_line, b.line_code AS to_line
FROM TrainStation AS s1
INNER JOIN StationLine AS a
ON a.station_code = s1.station_code
INNER JOIN TrainStation AS s2
ON s2.station_name_english = s1.station_name_english
AND s2.station_code <> s1.station_code
INNER JOIN StationLine AS b
ON b.station_code = s2.station_code
WHERE a.line_code <> b.line_code;

-- Each station with its code prefix and number (e.g. NS17 -> NS, 17)
CREATE OR REPLACE VIEW v_station_ordered AS
SELECT sl.line_code, s.station_code, s.station_name_english,
    REGEXP_SUBSTR(s.station_code, '^[A-Za-z]+') AS code_prefix,
    CAST(REGEXP_SUBSTR(s.station_code, '[0-9]+') AS UNSIGNED) AS code_number
FROM TrainStation AS s
INNER JOIN StationLine AS sl
ON s.station_code = sl.station_code;

-- Neighbouring stations on the same line (code to code, with the line)
CREATE OR REPLACE VIEW v_ride_links AS
SELECT a.line_code, a.station_code AS station_a, b.station_code AS station_b
FROM v_station_ordered AS a
INNER JOIN v_station_ordered AS b
ON a.line_code = b.line_code
AND a.code_prefix = b.code_prefix
AND b.code_number = (
    SELECT MIN(c.code_number)
    FROM v_station_ordered AS c
    WHERE c.line_code = a.line_code
    AND c.code_prefix = a.code_prefix
    AND c.code_number > a.code_number
)
UNION ALL
-- LRT hub stations (no number, e.g. PTC) link to both ends of each loop
SELECT hub.line_code, hub.station_code, st.station_code
FROM v_station_ordered AS hub
INNER JOIN v_station_ordered AS st
ON st.line_code = hub.line_code
AND st.code_number IS NOT NULL
WHERE hub.code_number IS NULL
AND (st.code_number = (
        SELECT MIN(c.code_number) FROM v_station_ordered AS c
        WHERE c.line_code = st.line_code AND c.code_prefix = st.code_prefix)
    OR st.code_number = (
        SELECT MAX(c.code_number) FROM v_station_ordered AS c
        WHERE c.line_code = st.line_code AND c.code_prefix = st.code_prefix));


-- The same links between station NAMES, in both directions, with the line used.
-- Buona Vista (EW21) and Buona Vista (CC22) are now one node.
CREATE OR REPLACE VIEW v_name_graph AS
SELECT from_name, to_name, MIN(line_code) AS line_code
FROM (
    SELECT sa.station_name_english AS from_name, sb.station_name_english AS to_name, l.line_code
    FROM v_ride_links AS l
    INNER JOIN TrainStation AS sa ON sa.station_code = l.station_a
    INNER JOIN TrainStation AS sb ON sb.station_code = l.station_b
    UNION ALL
    SELECT sb.station_name_english, sa.station_name_english, l.line_code
    FROM v_ride_links AS l
    INNER JOIN TrainStation AS sa ON sa.station_code = l.station_a
    INNER JOIN TrainStation AS sb ON sb.station_code = l.station_b
) AS both_ways
GROUP BY from_name, to_name;

-- Refresh the stored copy: empty the table, then refill it from the view
TRUNCATE TABLE StationConnection;

INSERT INTO StationConnection (from_name, to_name, line_code)
SELECT from_name, to_name, line_code FROM v_name_graph;