# PRXFIT BXT — Historical Context V0.2

This is a separate experimental module built on the working V0.1 branch.
The original TradingAgents CLI remains unchanged.

From inside the cloned/downloaded repository folder:

```powershell
python -m prxfit_data.history --days 7 --no-save
```

Run offline unit tests:

```powershell
python -m unittest discover -s tests -p "test_prxfit_*.py"
```

## What it adds

- Binance BTCUSDT perpetual daily candles and recent public funding history.
- Bybit BTCUSDT linear perpetual daily candles and recent hourly OI.
- Explicit source/market identifiers, UTC candle timestamps, base/quote units.
- Freshness classification helper with unknown, fresh, stale and future_timestamp.
- Deduplication and ordering of daily candles; independently reported source failures.

## Known constraints, deliberately not hidden

- No historical global OI is inferred from two exchanges.
- Bybit hourly OI fetch is limited to the most recent 200 buckets, **not** a full 30-day history.
- Binance funding history currently uses a single bounded request.
- Daily candle is marked incomplete until the UTC day ends.
- The history CLI currently does not persist to disk: cross-table enforcement of the full
  5 GiB database budget is required first. The V0.1 snapshot tool still supports bounded storage.
- Live endpoint behavior has not been independently validated on the user's machine.
- This is research data, not an AI forecast, and remains separate from TradingAgents orchestration.
