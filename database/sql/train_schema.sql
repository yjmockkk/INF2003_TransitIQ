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