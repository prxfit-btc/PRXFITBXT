"""PRXFIT BXT V0.2: bounded historical context with explicit source provenance.

Read-only public APIs, no paid credentials. No claims about inaccessible
historical order book or vendor-specific global market totals.
"""
from __future__ import annotations
import json
import time
from datetime import datetime, timezone
from pathlib import Path

from .engine import DEFAULT_DB, SOURCES, _connect, _float, bybit, request_json

DAY_MS = 86_400_000

def _timestamp(value):
    return datetime.fromtimestamp(int(value) / 1000, timezone.utc).isoformat()

def _candles(rows, source, market, interval, mapping):
    result = []
    seen = set()
    for row in rows:
        t = int(row[0])
        if t in seen:
            continue
        seen.add(t)
        result.append({
            "open_time_ms": t,
            "open_time_utc": _timestamp(t),
            "open": _float(row[1]),
            "high": _float(row[2]),
            "low": _float(row[3]),
            "close": _float(row[4]),
            "base_volume": _float(row[5]),
            "quote_volume": _float(row[mapping]) if mapping is not None else None,
            "source": source, "market": market, "interval": interval,
            "price_unit": "USDT/BTC",
            "completed": t + DAY_MS <= int(time.time() * 1000) if interval == "1d" else None,
        })
    return sorted(result, key=lambda x: x["open_time_ms"])

def fetch_binance_history(days=30):
    if not (1 <= days <= 365):
        raise ValueError("days must be 1..365")
    candles = request_json(SOURCES["binance"], "/fapi/v1/klines",
                           {"symbol": "BTCUSDT", "interval": "1d", "limit": days + 1})
    funding = request_json(SOURCES["binance"], "/fapi/v1/fundingRate",
                           {"symbol": "BTCUSDT", "limit": min(1000, days * 4 + 4)})
    return {
        "market": "BINANCE:BTCUSDT:PERP",
        "daily_candles": _candles(candles, "binance", "BINANCE:BTCUSDT:PERP", "1d", 7)[-days-1:],
        "funding_history": sorted([{
            "timestamp_ms": int(x["fundingTime"]),
            "funding_rate": _float(x["fundingRate"]),
            "unit": "decimal fraction",
            "market": "BINANCE:BTCUSDT:PERP",
            "source": "binance"
        } for x in funding], key=lambda x: x["timestamp_ms"]),
    }

def fetch_bybit_history(days=30):
    if not (1 <= days <= 180):
        raise ValueError("Bybit history days must be 1..180")
    candles = bybit("/v5/market/kline", {"category": "linear", "symbol": "BTCUSDT",
                  "interval": "D", "limit": days + 1})["list"]
    # Five-minute OI history is much larger. Use hourly buckets for bounded retrieval.
    oi = bybit("/v5/market/open-interest", {"category": "linear", "symbol": "BTCUSDT",
               "intervalTime": "1h", "limit": min(200, days * 24)})["list"]
    return {
        "market": "BYBIT:BTCUSDT:LINEAR_PERP",
        "daily_candles": _candles(candles, "bybit", "BYBIT:BTCUSDT:LINEAR_PERP", "1d", 6)[-days-1:],
        "open_interest_history": sorted([{
            "timestamp_ms": int(x["timestamp"]), "open_interest": _float(x["openInterest"]),
            "unit": "BTC", "source": "bybit",
            "market": "BYBIT:BTCUSDT:LINEAR_PERP"
        } for x in oi], key=lambda x: x["timestamp_ms"]),
        "note": "Bybit OI request returns at most 200 hourly buckets; do not imply full window coverage.",
    }

def freshness(observed_ms, now_ms=None, max_age_seconds=300):
    """Return unknown, fresh, stale or future_timestamp with measured age."""
    if observed_ms is None:
        return {"status": "unknown", "age_seconds": None}
    now = int(time.time()*1000) if now_ms is None else int(now_ms)
    age = (now - int(observed_ms)) / 1000
    if age < -60:
        status = "future_timestamp"
    elif age > max_age_seconds:
        status = "stale"
    else:
        status = "fresh"
    return {"status": status, "age_seconds": round(age, 1)}

FETCHERS = {"binance": fetch_binance_history, "bybit": fetch_bybit_history}

def collect_history(days=30, fetchers=None):
    """Partial source outages are explicit, never replaced with invented zeros."""
    results, errors = {}, []
    for name, fn in (FETCHERS if fetchers is None else fetchers).items():
        try:
            results[name] = fn(days)
        except Exception as exc:
            errors.append({"source": name, "error": f"{type(exc).__name__}: {str(exc)[:180]}"})
    return {
        "schema": "prxfit.history.v1",
        "query": "BTC-USD",
        "retrieved_at_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "requested_days": days, "sources": results, "source_errors": errors,
        "warning": "Latest daily candle may be incomplete; markets and timestamps are source-specific."
    }

def save_history(document, path=DEFAULT_DB):
    """Store compressed history in existing SQLite DB without growing beyond 5 GiB.

    History is a replaceable latest record, not an unlimited append-only log.
    """
    import zlib
    payload = zlib.compress(json.dumps(document, allow_nan=False).encode(), 6)
    with _connect(Path(path)) as db:
        db.execute("CREATE TABLE IF NOT EXISTS history_cache (key TEXT PRIMARY KEY, data BLOB NOT NULL)")
        db.execute("INSERT OR REPLACE INTO history_cache(key,data) VALUES('latest',?)", (payload,))
        db.commit()

def main():
    import argparse
    parser = argparse.ArgumentParser(description="PRXFIT BTC historical context")
    parser.add_argument("--days", type=int, default=30)
    parser.add_argument("--no-save", action="store_true")
    args = parser.parse_args()
    if not 1 <= args.days <= 30:
        parser.error("V0.2 CLI supports 1..30 days; longer windows require pagination")
    doc = collect_history(args.days)
    # History is currently printed without persistent storage by default:
    # keep disk cap controlled by the existing snapshot engine.
    if not args.no_save:
        print("History storage disabled pending joint 5 GiB budget enforcement.", flush=True)
    print(json.dumps(doc, indent=2, allow_nan=False))

if __name__ == "__main__":
    main()
