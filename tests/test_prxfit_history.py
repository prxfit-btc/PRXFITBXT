import unittest
from unittest.mock import patch
from prxfit_data.history import freshness, collect_history, _candles

class TestHistory(unittest.TestCase):
    def test_freshness(self):
        self.assertEqual(freshness(100000, 100000)["status"], "fresh")
        self.assertEqual(freshness(100000, 500000)["status"], "stale")
        self.assertEqual(freshness(None)["status"], "unknown")
        self.assertEqual(freshness(300000, 100000)["status"], "future_timestamp")

    def test_candles_sorted_deduplicated(self):
        rows = [[2000,"2","3","1","2","5","7","9"],[1000,"1","3","1","2","4","6","8"],[2000,"2","3","1","2","5","7","9"]]
        result = _candles(rows, "binance", "BINANCE:BTCUSDT:PERP", "1d", 7)
        self.assertEqual([x["open_time_ms"] for x in result], [1000,2000])
        self.assertEqual(result[0]["quote_volume"], 8.0)

    def test_partial_failure(self):
        def fail(days): raise ValueError("unavailable")
        doc = collect_history(7, {"bad":fail, "good":lambda days:{"count":days}})
        self.assertEqual(doc["sources"]["good"]["count"], 7)
        self.assertEqual(doc["source_errors"][0]["source"], "bad")

if __name__ == "__main__":
    unittest.main()
