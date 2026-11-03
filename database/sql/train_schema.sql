USE Transitiq;

-- 1. Train Stations
CREATE TABLE IF NOT EXISTS TrainStation (
    station_code VARCHAR(10) NOT NULL,
    station_name_english VARCHAR(100) NOT NULL,
    station_name_chinese VARCHAR(100) NOT NULL,

    PRIMARY KEY (station_code)
);


-- 2. TrainLine
CREATE TABLE IF NOT EXISTS TrainLine (
    line_code VARCHAR(10) NOT NULL,
    line_name_english VARCHAR(100) NOT NULL,
    line_name_chinese VARCHAR(100) NOT NULL,

    PRIMARY KEY (line_code)
);


-- 3. StationLine
CREATE TABLE IF NOT EXISTS StationLine (
    line_code VARCHAR(10) NOT NULL,
    station_code VARCHAR(10) NOT NULL,

    PRIMARY KEY (line_code, station_code),

    FOREIGN KEY (line_code)
        REFERENCES TrainLine(line_code),

    FOREIGN KEY (station_code)
        REFERENCES TrainStation(station_code)
);

-- Direct connection from one station name to a neighbouring one, with the line that serves it.
-- This is a stored copy of the view v_name_graph, kept for fast route lookups.
CREATE TABLE IF NOT EXISTS StationConnection (
    from_name VARCHAR(100) NOT NULL,
    to_name VARCHAR(100) NOT NULL,
    line_code VARCHAR(10) NOT NULL,

    PRIMARY KEY (from_name, to_name)
);

-- StationConnection is filled by database/sql/train_view.sql, after the train data is imported.
-- To refresh it when station data changes, re-run train_view.sql.