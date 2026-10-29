-- TransitIQ Bus Database Schema
USE Transitiq;

-- Create 'BusStop' table
CREATE TABLE IF NOT EXISTS BusStop(
  bus_stop_code VARCHAR(10) NOT NULL,
  road_name VARCHAR(100) NOT NULL,
  description VARCHAR(200) NOT NULL,
  latitude DECIMAL(9,6) NOT NULL,
  longitude DECIMAL(9,6) NOT NULL,
  
  PRIMARY KEY(bus_stop_code)
);

-- Create 'BusService' table
CREATE TABLE IF NOT EXISTS BusService (
  service_no VARCHAR(10) NOT NULL,
  direction TINYINT NOT NULL,
  operator VARCHAR(100) NOT NULL,
  category VARCHAR(30) NOT NULL,
  origin_code VARCHAR(10) NOT NULL,
  destination_code VARCHAR(10) NOT NULL,
  am_peak_freq VARCHAR(20),
  am_offpeak_freq VARCHAR(20),
  pm_peak_freq VARCHAR(20),
  pm_offpeak_freq VARCHAR(20),

  PRIMARY KEY(service_no, direction),

  FOREIGN KEY(origin_code) REFERENCES BusStop(bus_stop_code),
  FOREIGN KEY(destination_code) REFERENCES BusStop(bus_stop_code)
);

-- Create 'BusRoute' table
CREATE TABLE IF NOT EXISTS BusRoute(
  service_no VARCHAR(10) NOT NULL,
  direction TINYINT NOT NULL,
  stop_seq INT NOT NULL,
  bus_stop_code VARCHAR(10) NOT NULL,
  distance DECIMAL(9,3) NOT NULL,
  wd_first_bus VARCHAR(10),
  wd_last_bus VARCHAR(10),
  sat_first_bus VARCHAR(10),
  sat_last_bus VARCHAR(10),
  sun_first_bus VARCHAR(10),
  sun_last_bus VARCHAR(10),

  PRIMARY KEY (service_no, direction, stop_seq),
  
  FOREIGN KEY (service_no, direction) REFERENCES BusService(service_no, direction),
  FOREIGN KEY (bus_stop_code) REFERENCES BusStop(bus_stop_code)
);


