import hashlib
import json
import sys
import unittest
from copy import deepcopy
from datetime import date
from decimal import Decimal
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

import pipeline
from pipeline import extract_data, transform_data, validate_data


class TestValidation(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.original = transform_data(extract_data())

    def test_valid_dataset_passes(self):
        validate_data(deepcopy(self.original))

    def test_invalid_shipments_are_rejected(self):
        cases = [
            ("weight_kg", Decimal("-10"), "weight_kg"),
            ("actual_mode", "Teleport", "invalid actual_mode"),
            ("expedited_flag", 9, "expedited_flag"),
            ("modeled_baseline_inr", Decimal("1"), "baseline mismatch"),
            ("base_freight_inr", Decimal("-1"), "base_freight_inr"),
            ("fuel_surcharge_inr", Decimal("NaN"), "fuel_surcharge_inr"),
            (
                "actual_delivery_date",
                date(2024, 12, 31),
                "actual_delivery_date cannot be before dispatch",
            ),
            (
                "promised_delivery_date",
                date(2024, 12, 31),
                "promised_delivery_date cannot be before dispatch",
            ),
        ]

        for column, value, expected_message in cases:
            with self.subTest(column=column):
                data = deepcopy(self.original)
                data["fact_shipment"][0][column] = value

                with self.assertRaisesRegex(ValueError, expected_message):
                    validate_data(data)

    def test_non_synthetic_dimensions_are_rejected(self):
        for table in ("dim_customer", "dim_carrier", "dim_route"):
            with self.subTest(table=table):
                data = deepcopy(self.original)
                data[table][0]["data_type"] = "REAL"
                with self.assertRaisesRegex(ValueError, f"Non-synthetic row detected in {table}"):
                    validate_data(data)

    def test_malformed_csv_is_rejected(self):
        cases = [
            ("customer_id,customer_name,segment,data_type,data_type\n",
             "duplicate column names"),
            ("customer_id,customer_name,segment,data_type\n"
             "1,Demo Customer 01,Industrial,SYNTHETIC,extra\n",
             "wrong number of values"),
            ("customer_id,customer_name,segment,data_type\n"
             "1,Demo Customer 01,Industrial\n",
             "wrong number of values"),
        ]
        for content, expected_message in cases:
            with self.subTest(content=content), TemporaryDirectory() as folder:
                (Path(folder) / "dim_customer.csv").write_text(content, encoding="utf-8")
                with patch.object(pipeline, "DATA_DIR", Path(folder)):
                    with self.assertRaisesRegex(ValueError, expected_message):
                        extract_data()

    def test_dataset_fingerprints_match_report(self):
        report = json.loads(
            (pipeline.PROJECT_DIR / "validation_report.json").read_text(encoding="utf-8")
        )
        self.assertEqual(report["csv_hash_normalization"], "LF line endings before SHA-256")
        self.assertEqual(
            set(report["csv_sha256"]),
            {path.name for path in pipeline.DATA_DIR.glob("*.csv")},
        )
        for filename, expected in report["csv_sha256"].items():
            with self.subTest(filename=filename):
                content = (pipeline.DATA_DIR / filename).read_bytes().replace(b"\r\n", b"\n")
                self.assertEqual(hashlib.sha256(content).hexdigest(), expected)

    def test_missing_column_is_rejected(self):
        with TemporaryDirectory() as folder:
            csv_path = Path(folder) / "dim_customer.csv"
            csv_path.write_text(
                "customer_id,customer_name,data_type\n"
                "1,Demo Customer 01,SYNTHETIC\n",
                encoding="utf-8",
            )

            with patch.object(pipeline, "DATA_DIR", Path(folder)):
                with self.assertRaisesRegex(
                    ValueError, r"missing=\['segment'\]"
                ):
                    extract_data()


if __name__ == "__main__":
    unittest.main()
