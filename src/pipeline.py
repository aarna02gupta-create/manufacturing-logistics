"""Extract, transform, validate, load and reconcile synthetic logistics data."""

from __future__ import annotations

import csv
import logging
from datetime import date, datetime
from decimal import Decimal
from pathlib import Path
from uuid import uuid4

from db_connection import get_db_connection


PROJECT_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = PROJECT_DIR / "data"
LOG_DIR = PROJECT_DIR / "logs"

TABLE_FILES = {
    "dim_customer": "dim_customer.csv",
    "dim_carrier": "dim_carrier.csv",
    "dim_route": "dim_route.csv",
    "dim_date": "dim_date.csv",
    "fact_shipment": "fact_shipment.csv",
}

PRIMARY_KEYS = {
    "dim_customer": "customer_id",
    "dim_carrier": "carrier_id",
    "dim_route": "route_id",
    "dim_date": "date_key",
    "fact_shipment": "shipment_id",
}

INTEGER_COLUMNS = {
    "dim_customer": {"customer_id"},
    "dim_carrier": {"carrier_id"},
    "dim_route": {"route_id"},
    "dim_date": {"date_key", "calendar_year", "month_number", "quarter_number"},
    "fact_shipment": {
        "ship_date_key", "customer_id", "carrier_id", "route_id", "expedited_flag"
    },
}

DECIMAL_COLUMNS = {
    "dim_route": {"rate_factor"},
    "fact_shipment": {
        "weight_kg", "base_freight_inr", "fuel_surcharge_inr",
        "handling_charge_inr", "expedite_fee_inr", "recorded_freight_inr",
        "baseline_rate_inr_kg", "baseline_fuel_inr",
        "baseline_handling_inr", "modeled_baseline_inr",
    },
}

DATE_COLUMNS = {
    "dim_date": {"calendar_date"},
    "fact_shipment": {"promised_delivery_date", "actual_delivery_date"},
}

EXPECTED_ROWS = {
    "dim_customer": 12,
    "dim_carrier": 5,
    "dim_route": 8,
    "dim_date": 730,
    "fact_shipment": 2400,
}


def configure_logging() -> logging.Logger:
    LOG_DIR.mkdir(exist_ok=True)
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s | %(levelname)s | %(message)s",
        handlers=[
            logging.StreamHandler(),
            logging.FileHandler(LOG_DIR / "pipeline.log", encoding="utf-8"),
        ],
    )
    return logging.getLogger("logistics_pipeline")


def extract_data() -> dict[str, list[dict[str, str]]]:
    """Read CSV files after checking their columns and row structure."""
    expected_columns = {
        "dim_customer": {
            "customer_id", "customer_name", "segment", "data_type",
        },
        "dim_carrier": {
            "carrier_id", "carrier_name", "data_type",
        },
        "dim_route": {
            "route_id", "origin_city", "destination_city",
            "destination_country", "route_type", "rate_factor", "data_type",
        },
        "dim_date": {
            "date_key", "calendar_date", "calendar_year", "month_number",
            "month_name", "year_month", "quarter_number",
        },
        "fact_shipment": {
            "shipment_id", "ship_date_key", "customer_id", "carrier_id",
            "route_id", "planned_mode", "actual_mode", "weight_kg",
            "promised_delivery_date", "actual_delivery_date",
            "base_freight_inr", "fuel_surcharge_inr", "handling_charge_inr",
            "expedite_fee_inr", "recorded_freight_inr",
            "baseline_rate_inr_kg", "baseline_fuel_inr",
            "baseline_handling_inr", "modeled_baseline_inr",
            "expedited_flag", "delay_reason", "data_type",
        },
    }

    datasets = {}

    for table, filename in TABLE_FILES.items():
        file_path = DATA_DIR / filename

        if not file_path.exists():
            raise FileNotFoundError(f"Missing source file: {file_path}")

        with file_path.open(newline="", encoding="utf-8-sig") as source:
            reader = csv.DictReader(source)
            headers = reader.fieldnames

            if not headers:
                raise ValueError(f"{filename}: missing header row")

            if len(headers) != len(set(headers)):
                raise ValueError(f"{filename}: duplicate column names")

            missing = expected_columns[table] - set(headers)
            unexpected = set(headers) - expected_columns[table]

            if missing or unexpected:
                raise ValueError(
                    f"{filename}: column mismatch; "
                    f"missing={sorted(missing)}, "
                    f"unexpected={sorted(unexpected)}"
                )

            rows = []
            for row in reader:
                if None in row or any(value is None for value in row.values()):
                    raise ValueError(
                        f"{filename}: wrong number of values "
                        f"near line {reader.line_num}"
                    )
                rows.append(row)

            datasets[table] = rows

    return datasets

def convert_value(table: str, column: str, raw_value: str):
    """Strip text and convert typed columns to Python values."""
    value = raw_value.strip()
    if value == "":
        raise ValueError(f"{table}.{column} contains a blank value")
    if column in INTEGER_COLUMNS.get(table, set()):
        return int(value)
    if column in DECIMAL_COLUMNS.get(table, set()):
        return Decimal(value)
    if column in DATE_COLUMNS.get(table, set()):
        return date.fromisoformat(value)
    return value


def transform_data(datasets: dict[str, list[dict]]) -> dict[str, list[dict]]:
    """Clean strings and enforce integer, decimal and date types."""
    transformed = {}
    for table, rows in datasets.items():
        transformed[table] = [
            {
                column: convert_value(table, column, value)
                for column, value in row.items()
            }
            for row in rows
        ]
    return transformed


def validate_data(datasets: dict[str, list[dict]]) -> None:
    """Validate row counts, keys, relationships and business rules."""
    if set(datasets) != set(TABLE_FILES):
        raise ValueError("The pipeline did not receive all five required datasets")

    for table, expected in EXPECTED_ROWS.items():
        rows = datasets[table]
        if len(rows) != expected:
            raise ValueError(f"{table}: expected {expected} rows, found {len(rows)}")
        key = PRIMARY_KEYS[table]
        values = [row[key] for row in rows]
        if len(values) != len(set(values)):
            raise ValueError(f"{table}.{key} contains duplicates")

    valid_ids = {
        table: {row[PRIMARY_KEYS[table]] for row in datasets[table]}
        for table in ("dim_customer", "dim_carrier", "dim_route", "dim_date")
    }

    for table in ("dim_customer", "dim_carrier", "dim_route"):
        for row in datasets[table]:
            if row["data_type"] != "SYNTHETIC":
                raise ValueError(
                    f"Non-synthetic row detected in {table}: "
                    f"{row[PRIMARY_KEYS[table]]}"
                )

    shipment_dates = {
        row["date_key"]: row["calendar_date"]
        for row in datasets["dim_date"]
    }

    for row in datasets["fact_shipment"]:
        shipment_id = row["shipment_id"]
        cost_columns = (
            "base_freight_inr",
            "fuel_surcharge_inr",
            "handling_charge_inr",
            "expedite_fee_inr",
            "recorded_freight_inr",
        )

        for column in cost_columns:
            value = row[column]
            if not value.is_finite() or value < 0:
                raise ValueError(
                    f"{shipment_id}: {column} must be finite and non-negative"
                )

        ship_date = shipment_dates.get(row["ship_date_key"])

        if ship_date is None:
            raise ValueError(
                f"{shipment_id}: unknown ship_date_key"
            )

        for column in (
            "promised_delivery_date",
            "actual_delivery_date",
        ):
            if row[column] < ship_date:
                raise ValueError(
                    f"{shipment_id}: {column} cannot be before dispatch"
                )

        if not row["weight_kg"].is_finite() or row["weight_kg"] <= 0:
            raise ValueError(
                f"{shipment_id}: weight_kg must be a finite positive number"
            )

        for column in ("planned_mode", "actual_mode"):
            if row[column] not in {"Road", "Sea", "Air"}:
                raise ValueError(
                    f"{shipment_id}: invalid {column}: {row[column]}"
                )

        if row["expedited_flag"] not in {0, 1}:
            raise ValueError(
                f"{shipment_id}: expedited_flag must be 0 or 1"
            )

        baseline_columns = (
            "baseline_rate_inr_kg",
            "baseline_fuel_inr",
            "baseline_handling_inr",
            "modeled_baseline_inr",
        )

        for column in baseline_columns:
            value = row[column]
            if not value.is_finite() or value < 0:
                raise ValueError(
                    f"{shipment_id}: {column} must be finite and non-negative"
                )

        if (
            row["baseline_rate_inr_kg"] == 0
            or row["modeled_baseline_inr"] == 0
        ):
            raise ValueError(
                f"{shipment_id}: baseline rate and total must be positive"
            )

        expected_baseline = (
            (row["weight_kg"] * row["baseline_rate_inr_kg"]).quantize(
                Decimal("0.01"), rounding="ROUND_HALF_UP"
            )
            + row["baseline_fuel_inr"]
            + row["baseline_handling_inr"]
        )

        if row["modeled_baseline_inr"] != expected_baseline:
            raise ValueError(
                f"{shipment_id}: baseline mismatch; "
                f"expected {expected_baseline}, "
                f"found {row['modeled_baseline_inr']}"
            )
        for column, table in (
            ("customer_id", "dim_customer"),
            ("carrier_id", "dim_carrier"),
            ("route_id", "dim_route"),
            ("ship_date_key", "dim_date"),
        ):
            if row[column] not in valid_ids[table]:
                raise ValueError(f"Unknown {column}: {row[column]}")

        recorded = sum(
            row[column]
            for column in (
                "base_freight_inr", "fuel_surcharge_inr",
                "handling_charge_inr", "expedite_fee_inr",
            )
        )
        if recorded != row["recorded_freight_inr"]:
            raise ValueError(f"Invoice mismatch for {row['shipment_id']}")
        if row["actual_delivery_date"] < row["promised_delivery_date"]:
            expected_reason = "None"
        elif row["actual_delivery_date"] == row["promised_delivery_date"]:
            expected_reason = "None"
        else:
            expected_reason = row["delay_reason"]
            if expected_reason == "None":
                raise ValueError(f"Missing delay reason for {row['shipment_id']}")
        if expected_reason == "None" and row["delay_reason"] != "None":
            raise ValueError(f"Unexpected delay reason for {row['shipment_id']}")
        if row["data_type"] != "SYNTHETIC":
            raise ValueError(f"Non-synthetic row detected: {row['shipment_id']}")


def ensure_log_table(connection) -> None:
    cursor = connection.cursor()
    try:
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS pipeline_run_log (
                run_id CHAR(36) PRIMARY KEY,
                started_at DATETIME NOT NULL,
                finished_at DATETIME NULL,
                status VARCHAR(20) NOT NULL,
                rows_processed INT NOT NULL DEFAULT 0,
                message VARCHAR(500) NULL
            )
            """
        )
        connection.commit()
    finally:
        cursor.close()


def record_run(connection, run_id: str, status: str, rows: int, message: str) -> None:
    cursor = connection.cursor()
    try:
        if status == "RUNNING":
            cursor.execute(
                """
                INSERT INTO pipeline_run_log
                    (run_id, started_at, status, rows_processed, message)
                VALUES (%s, %s, %s, %s, %s)
                """,
                (run_id, datetime.now(), status, rows, message[:500]),
            )
        else:
            cursor.execute(
                """
                UPDATE pipeline_run_log
                SET finished_at=%s, status=%s, rows_processed=%s, message=%s
                WHERE run_id=%s
                """,
                (datetime.now(), status, rows, message[:500], run_id),
            )
        connection.commit()
    finally:
        cursor.close()


def upsert_table(cursor, table: str, rows: list[dict], batch_size: int = 500) -> int:
    """Insert new rows and update changed rows in batches."""
    columns = list(rows[0])
    quoted = ", ".join(f"`{column}`" for column in columns)
    placeholders = ", ".join(["%s"] * len(columns))
    primary_key = PRIMARY_KEYS[table]
    updates = ", ".join(
        f"`{column}`=VALUES(`{column}`)"
        for column in columns
        if column != primary_key
    )
    statement = (
        f"INSERT INTO `{table}` ({quoted}) VALUES ({placeholders}) "
        f"ON DUPLICATE KEY UPDATE {updates}"
    )
    processed = 0
    for offset in range(0, len(rows), batch_size):
        batch = rows[offset:offset + batch_size]
        cursor.executemany(
            statement,
            [tuple(row[column] for column in columns) for row in batch],
        )
        processed += len(batch)
    return processed


def reconcile_database(cursor, datasets: dict[str, list[dict]]) -> None:
    """Confirm database counts and key uniqueness after loading."""
    for table, rows in datasets.items():
        key = PRIMARY_KEYS[table]
        cursor.execute(
            f"SELECT COUNT(*), COUNT(DISTINCT `{key}`) FROM `{table}`"
        )
        total, unique_keys = cursor.fetchone()
        expected = len(rows)
        if total != expected or unique_keys != expected:
            raise ValueError(
                f"{table} reconciliation failed: expected {expected}, "
                f"found {total} rows and {unique_keys} unique keys"
            )

    cursor.execute(
        """
        SELECT COUNT(*)
        FROM fact_shipment
        WHERE data_type <> 'SYNTHETIC'
           OR recorded_freight_inr < 0
           OR modeled_baseline_inr <= 0
        """
    )
    if cursor.fetchone()[0] != 0:
        raise ValueError("Post-load business-rule reconciliation failed")


def run_pipeline() -> None:
    logger = configure_logging()
    run_id = str(uuid4())
    connection = None
    rows_processed = 0

    try:
        logger.info("Pipeline %s started", run_id)
        datasets = transform_data(extract_data())
        validate_data(datasets)
        logger.info("Extract, transform and validation completed")

        connection = get_db_connection()
        ensure_log_table(connection)
        record_run(connection, run_id, "RUNNING", 0, "Validation passed")

        cursor = connection.cursor()
        try:
            connection.start_transaction()
            for table in TABLE_FILES:
                loaded = upsert_table(cursor, table, datasets[table])
                rows_processed += loaded
                logger.info("Loaded %s: %s rows", table, loaded)
            reconcile_database(cursor, datasets)
            connection.commit()
        except Exception:
            connection.rollback()
            raise
        finally:
            cursor.close()

        record_run(
            connection, run_id, "SUCCESS", rows_processed,
            "All tables loaded and reconciled",
        )
        logger.info("Pipeline completed successfully: %s rows", rows_processed)
    except Exception as error:
        if connection is not None and connection.is_connected():
            try:
                record_run(connection, run_id, "FAILED", rows_processed, str(error))
            except Exception:
                logger.exception("Could not update the pipeline run log")
        logger.exception("Pipeline failed: %s", error)
        raise
    finally:
        if connection is not None and connection.is_connected():
            connection.close()


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(
        description="Validate and load manufacturing logistics data."
    )
    parser.add_argument(
        "--validate-only",
        action="store_true",
        help="Validate CSV files without connecting to MySQL.",
    )
    args = parser.parse_args()

    if args.validate_only:
        datasets = transform_data(extract_data())
        validate_data(datasets)

        for table, rows in datasets.items():
            print(f"PASS: {table} ({len(rows)} rows)")

        print("Validation successful. No database changes made.")
    else:
        run_pipeline()