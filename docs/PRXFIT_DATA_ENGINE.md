# PRXFIT BXT — Data Engine v0.1

First backend increment. **Not integrated into the TradingAgents decision graph.**
The original CLI is untouched. No paid APIs or API keys are required.

## Run

From repository root with your existing Python environment:

```powershell
& "..\.venv\Scripts\python.exe" -m prxfit_data BTC-USD
```

Or use `python -m prxfit_data BTC-USD --no-save` in an activated environment.
Tests: `python -m unittest discover -s tests -p "test_prxfit_data.py"`

## Live sources
- Binance USDⓈ-M BTCUSDT perpetual: current UTC daily kline, mark, open interest, last funding rate.
- Bybit BTCUSDT linear perpetual: UTC daily kline, ticker price/funding, latest five-minute OI bucket.
- Deribit: summary-level BTC option open-interest aggregate (Deribit units; **not** global option OI).
- mempool.space: Bitcoin mainnet chain tip height.

All HTTP fetches are public, time-limited, read-only and recorded with provenance. One failed source never silently becomes a zero. The command prints a JSON snapshot and, unless `--no-save` is set, saves a compressed copy in `~/.prxfit_bxt/market_data.sqlite3`. Oldest snapshots are pruned near 80% of a **5 GiB database cap**. This limit covers that SQLite database only, not the Python installation, any OS cache, or logs.

## Important integrity rules
- `BTC-USD` is the **query label**, not a claim that all feeds are BTC/USD spot. Market identifiers and units stay separate.
- Timestamp of retrieval is not timestamp of the market observation. Missing exchange timestamps remain null.
- Open UTC daily candles are not completed forecasts or confirmed closing values.
- Domain coverage is partial; missing domains are explicitly marked `not_connected`.
- No model is used yet. No advice, signals, trade execution or spurious daily direction claims.
- Free public endpoints may rate-limit, geo-block, change response formats or go offline.

## Next planned increments
1. Real BTC/USD spot reference and cross-venue quote normalization.
2. Historical paginated OHLCV + funding/OI, freshness thresholds, point-in-time data QA.
3. Macro releases, intermarket, verified news, official ETF sources and on-chain datasets.
4. Orderflow/orderbook sampling with retention policy before enabling continuous collection.
5. Integrate verified standardized observations as analyst tools into TradingAgents.

This deliberately prioritizes accurate source-labelled data over pretending seven domains are complete.
