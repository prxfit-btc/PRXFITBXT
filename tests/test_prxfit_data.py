import tempfile
import unittest
from pathlib import Path
from prxfit_data.engine import collect_snapshot, persist_snapshot, latest_snapshot, observation

class TestDataEngine(unittest.TestCase):
    def test_partial_failure_and_provenance(self):
        def okay():
            return [observation("test", "TEST:BTCUSD:SPOT", "price", 100, "USD/BTC", 123)]
        def fail():
            raise ValueError("feed offline")
        snapshot = collect_snapshot({"test": okay, "offline": fail})
        self.assertEqual(len(snapshot["observations"]), 1)
        self.assertEqual(snapshot["observations"][0]["market_timestamp_ms"], 123)
        self.assertEqual(snapshot["source_errors"][0]["source"], "offline")
        self.assertEqual(snapshot["domain_coverage"]["sentiment"], "not_connected")

    def test_local_round_trip(self):
        snapshot = collect_snapshot({"empty": lambda: []})
        with tempfile.TemporaryDirectory() as temp:
            db = Path(temp) / "data.db"
            persist_snapshot(snapshot, db, max_bytes=500_000)
            self.assertEqual(latest_snapshot(db)["schema"], "prxfit.snapshot.v1")
            self.assertLess(db.stat().st_size, 500_000)

    def test_reject_tiny_budget(self):
        with tempfile.TemporaryDirectory() as temp:
            with self.assertRaises(ValueError):
                persist_snapshot({}, Path(temp)/"data.db", max_bytes=10)

if __name__ == "__main__":
    unittest.main()
