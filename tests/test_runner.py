import json
import shutil
import tempfile
import unittest
from pathlib import Path

from lakehouse import runner

ROOT = Path(__file__).resolve().parent.parent
FIXTURE = ROOT / "tests" / "fixtures" / "trips_sample.csv"


class GraphTests(unittest.TestCase):
    def _write(self, directory: Path, files: dict[str, str]) -> dict[str, Path]:
        for name, sql in files.items():
            (directory / f"{name}.sql").write_text(sql)
        return runner.discover_models(directory)

    def test_orders_models_after_their_dependencies(self):
        with tempfile.TemporaryDirectory() as tmp:
            models = self._write(Path(tmp), {
                "c": "SELECT * FROM {{ ref('b') }}",
                "b": "SELECT * FROM {{ ref('a') }}",
                "a": "SELECT 1",
            })
            self.assertEqual(runner.order_models(models), ["a", "b", "c"])

    def test_cycle_is_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            models = self._write(Path(tmp), {
                "a": "SELECT * FROM {{ ref('b') }}",
                "b": "SELECT * FROM {{ ref('a') }}",
            })
            with self.assertRaises(runner.RunnerError):
                runner.order_models(models)

    def test_unknown_ref_is_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            models = self._write(Path(tmp), {"a": "SELECT * FROM {{ ref('ghost') }}"})
            with self.assertRaises(runner.RunnerError):
                runner.order_models(models)

    def test_render_replaces_ref_and_source(self):
        sql = "SELECT * FROM {{ ref('x') }} JOIN {{ source('raw', 'trips') }}"
        self.assertEqual(runner.render(sql), "SELECT * FROM x JOIN raw_trips")

    def test_unsafe_path_is_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            bad = Path(tmp) / "a'; DROP TABLE x; --.csv"
            with self.assertRaises(runner.RunnerError):
                runner.ingest(Path(tmp) / "db.duckdb", bad, Path(tmp) / "o.parquet")


@unittest.skipUnless(shutil.which("duckdb"), "duckdb CLI not installed")
class EndToEndTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        cls.db = Path(cls.tmp.name) / "t.duckdb"
        runner.ingest(cls.db, FIXTURE, Path(cls.tmp.name) / "raw.parquet")
        runner.build(cls.db, ROOT / "models")

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def _query(self, sql: str) -> str:
        return runner.run_duckdb(self.db, sql, as_json=True)

    def test_each_bad_row_gets_its_own_reason(self):
        out = self._query("SELECT reject_reason FROM trips_rejected ORDER BY reject_reason")
        reasons = {r["reject_reason"] for r in json.loads(out)}
        self.assertEqual(reasons, {
            "dropoff_before_pickup", "nonpositive_distance", "distance_over_100_miles",
            "nonpositive_fare", "negative_total", "invalid_passenger_count",
            "pickup_outside_nyc",
        })

    def test_row_counts_reconcile(self):
        out = self._query(
            "SELECT (SELECT count(*) FROM fct_trips) AS ok, "
            "(SELECT count(*) FROM trips_rejected) AS bad")
        row = json.loads(out)[0]
        self.assertEqual((row["ok"], row["bad"]), (3, 7))

    def test_shipped_data_tests_pass_on_fixture(self):
        results = runner.run_tests(self.db, ROOT / "tests" / "sql")
        self.assertEqual({k: v for k, v in results.items() if v}, {})

    def test_data_test_fails_when_data_is_bad(self):
        # Guards against vacuous tests: corrupt the fact table and expect a failure.
        runner.run_duckdb(self.db, "CREATE OR REPLACE TABLE fct_bad AS SELECT * FROM fct_trips;"
                                    "UPDATE fct_bad SET fare_amount = -5 WHERE trip_id = 0;")
        with tempfile.TemporaryDirectory() as tmp:
            (Path(tmp) / "bad.sql").write_text("SELECT trip_id FROM fct_bad WHERE fare_amount <= 0")
            self.assertEqual(runner.run_tests(self.db, Path(tmp)), {"bad": 1})


if __name__ == "__main__":
    unittest.main()
