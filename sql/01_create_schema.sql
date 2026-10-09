-- Portfolio project. Synthetic manufacturing-logistics records only.
-- MySQL 8.0.16+ required for enforced CHECK constraints.
CREATE DATABASE IF NOT EXISTS portfolio_logistics
  CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
USE portfolio_logistics;

CREATE TABLE IF NOT EXISTS dim_customer (
 customer_id INT PRIMARY KEY,
 customer_name VARCHAR(80) NOT NULL,
 segment VARCHAR(40) NOT NULL,
 data_type VARCHAR(30) NOT NULL CHECK (data_type='SYNTHETIC')
);
CREATE TABLE IF NOT EXISTS dim_carrier (
 carrier_id INT PRIMARY KEY,
 carrier_name VARCHAR(80) NOT NULL,
 data_type VARCHAR(30) NOT NULL CHECK (data_type='SYNTHETIC')
);
CREATE TABLE IF NOT EXISTS dim_route (
 route_id INT PRIMARY KEY,
 origin_city VARCHAR(60) NOT NULL,
 destination_city VARCHAR(60) NOT NULL,
 destination_country VARCHAR(60) NOT NULL,
 route_type VARCHAR(20) NOT NULL,
 rate_factor DECIMAL(5,2) NOT NULL CHECK (rate_factor>0),
 data_type VARCHAR(30) NOT NULL CHECK (data_type='SYNTHETIC')
);
CREATE TABLE IF NOT EXISTS dim_date (
 date_key INT PRIMARY KEY,
 calendar_date DATE NOT NULL UNIQUE,
 calendar_year SMALLINT NOT NULL,
 month_number TINYINT NOT NULL CHECK (month_number BETWEEN 1 AND 12),
 month_name VARCHAR(12) NOT NULL,
 `year_month` CHAR(7) NOT NULL,
 quarter_number TINYINT NOT NULL CHECK (quarter_number BETWEEN 1 AND 4)
);
CREATE TABLE IF NOT EXISTS fact_shipment (
 shipment_id VARCHAR(16) PRIMARY KEY,
 ship_date_key INT NOT NULL,
 customer_id INT NOT NULL,
 carrier_id INT NOT NULL,
 route_id INT NOT NULL,
 planned_mode VARCHAR(10) NOT NULL CHECK (planned_mode IN ('Road','Sea','Air')),
 actual_mode VARCHAR(10) NOT NULL CHECK (actual_mode IN ('Road','Sea','Air')),
 weight_kg DECIMAL(12,2) NOT NULL CHECK (weight_kg>0),
 promised_delivery_date DATE NOT NULL,
 actual_delivery_date DATE NOT NULL,
 base_freight_inr DECIMAL(16,2) NOT NULL CHECK (base_freight_inr>=0),
 fuel_surcharge_inr DECIMAL(16,2) NOT NULL CHECK (fuel_surcharge_inr>=0),
 handling_charge_inr DECIMAL(16,2) NOT NULL CHECK (handling_charge_inr>=0),
 expedite_fee_inr DECIMAL(16,2) NOT NULL CHECK (expedite_fee_inr>=0),
 recorded_freight_inr DECIMAL(16,2) NOT NULL,
 baseline_rate_inr_kg DECIMAL(12,2) NOT NULL CHECK (baseline_rate_inr_kg>0),
 baseline_fuel_inr DECIMAL(16,2) NOT NULL CHECK (baseline_fuel_inr>=0),
 baseline_handling_inr DECIMAL(16,2) NOT NULL CHECK (baseline_handling_inr>=0),
 modeled_baseline_inr DECIMAL(16,2) NOT NULL CHECK (modeled_baseline_inr>0),
 expedited_flag TINYINT NOT NULL CHECK (expedited_flag IN (0,1)),
 delay_reason VARCHAR(40) NOT NULL,
 data_type VARCHAR(30) NOT NULL CHECK (data_type='SYNTHETIC'),
 FOREIGN KEY (ship_date_key) REFERENCES dim_date(date_key),
 FOREIGN KEY (customer_id) REFERENCES dim_customer(customer_id),
 FOREIGN KEY (carrier_id) REFERENCES dim_carrier(carrier_id),
 FOREIGN KEY (route_id) REFERENCES dim_route(route_id),
 CONSTRAINT chk_invoice_total CHECK (
 recorded_freight_inr=base_freight_inr+fuel_surcharge_inr+handling_charge_inr+expedite_fee_inr),
 CONSTRAINT chk_baseline_total CHECK (
 modeled_baseline_inr=ROUND(weight_kg*baseline_rate_inr_kg,2)+baseline_fuel_inr+baseline_handling_inr)
);

CREATE TABLE IF NOT EXISTS pipeline_run_log (
 run_id CHAR(36) PRIMARY KEY,
 started_at DATETIME NOT NULL,
 finished_at DATETIME NULL,
 status VARCHAR(20) NOT NULL,
 rows_processed INT NOT NULL DEFAULT 0,
 message VARCHAR(500) NULL
);
SHOW TABLES;
