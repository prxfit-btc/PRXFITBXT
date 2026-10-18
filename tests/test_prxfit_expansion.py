import unittest
from unittest.mock import patch
from prxfit_data.expansion import fetch_coinbase_spot, fetch_bitcoin_network, collect_expansion

class Tests(unittest.TestCase):
    @patch("prxfit_data.expansion.request_json")
    def test_spot(self, request):
        request.return_value={"bid":"80000","ask":"80002","price":"80001","time":"2026-10-18T03:00:00Z"}
        out=fetch_coinbase_spot()
        self.assertEqual(len(out),4)
        self.assertEqual(out[0]["market"],"COINBASE:BTC-USD:SPOT")
        self.assertEqual(out[3]["value"],2.0)
    @patch("prxfit_data.expansion.request_json")
    def test_bad_quote(self, request):
        request.return_value={"bid":"80002","ask":"80000","price":"80001"}
        with self.assertRaises(ValueError):
            fetch_coinbase_spot()
    @patch("prxfit_data.expansion.request_json")
    def test_network(self, request):
        request.side_effect=[{"fastestFee":7,"hourFee":2},{"difficultyChange":1.5,"remainingBlocks":20},971938]
        out=fetch_bitcoin_network()
        self.assertEqual(len(out),5)
    def test_partial_failure(self):
        result=collect_expansion({"good": lambda:[], "bad":lambda: 1/0})
        self.assertEqual(result["source_errors"][0]["source"],"bad")
if __name__=="__main__":
    unittest.main()
