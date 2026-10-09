import sys
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

import pipeline


class DeliberateTestError(Exception):
    pass


def read_customer_name():
    connection = pipeline.get_db_connection()
    cursor = connection.cursor()
    try:
        cursor.execute(
            "SELECT customer_name FROM dim_customer WHERE customer_id = 1"
        )
        row = cursor.fetchone()
        if row is None:
            raise RuntimeError("Customer 1 is missing. Run the pipeline first.")
        return row[0]
    finally:
        cursor.close()
        connection.close()


def restore_customer_name(name):
    connection = pipeline.get_db_connection()
    cursor = connection.cursor()
    try:
        cursor.execute(
            "UPDATE dim_customer SET customer_name = %s WHERE customer_id = 1",
            (name,),
        )
        connection.commit()
    finally:
        cursor.close()
        connection.close()


class TestRollback(unittest.TestCase):
    def test_failed_load_undoes_change(self):
        original_name = read_customer_name()
        temporary_name = "ROLLBACK TEST CUSTOMER"
        self.assertNotEqual(original_name, temporary_name)

        def fail_during_loading(cursor, table, rows):
            cursor.execute(
                "UPDATE dim_customer SET customer_name = %s "
                "WHERE customer_id = 1",
                (temporary_name,),
            )
            cursor.execute(
                "SELECT customer_name FROM dim_customer WHERE customer_id = 1"
            )
            self.assertEqual(cursor.fetchone()[0], temporary_name)
            raise DeliberateTestError("Intentional failure to test rollback")

        try:
            with patch.object(
                pipeline, "upsert_table", side_effect=fail_during_loading
            ):
                with self.assertRaises(DeliberateTestError):
                    pipeline.run_pipeline()

            self.assertEqual(
                read_customer_name(),
                original_name,
                "Rollback failed: the temporary name was saved.",
            )
        finally:
            # Restore the original value if the rollback test fails.
            if read_customer_name() != original_name:
                restore_customer_name(original_name)


if __name__ == "__main__":
    unittest.main(verbosity=2)