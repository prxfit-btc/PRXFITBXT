"""On-demand BTC market snapshot. Standard library only; no API keys or trading permissions.

Each observation retains its actual venue, market and quote currency. BTCUSDT
perpetuals are NOT represented as BTC-USD spot. Missing data remains missing.
"""
from __future__ import annotations

import json
import os
import sqlite3
import time
from datetime import datetime, timezone
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

LIMIT_BYTES = 5 * 1024 ** 3
DEFAULT_DB = Path.home() / ".prxfit_bxt" / "market_data.sqlite3"
UA = "PRXFIT-BXT/0.1 (public-data-research)"
SOURCES = {
    "binance": "https://fapi.binance.com",
    "bybit": "https://api.bybit.com",
    "deribit": "https://www.deribit.com",
    "mempool": "https://mempool.space",
}


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def request_json(base: str, path: str, params: dict | None = None, timeout: int = 12):
    url = base + path
    if params:
        url += "?" + urlencode(params)
    req = Request(url, headers={"User-Agent": UA, "Accept": "application/json"})
    with urlopen(req, timeout=timeout) as response:
        if response.status != 200:
            raise ValueError(f"HTTP {response.status}")
        raw = response.read(2_000_001)
        if len(raw) > 2_000_000:
            raise ValueError("Response exceeds 2 MB safety limit")
        return json.loads(raw)


def bybit(path: str, params: dict):
    obj = request_json(SOURCES["bybit"], path, params)
    if obj.get("retCode") != 0:
        raise ValueError(f"Bybit retCode {obj.get('retCode')}: {str(obj.get('retMsg'))[:120]}")
    return obj["result"]


def observation(source: str, market: str, metric: str, value, unit: str,
                market_timestamp_ms=None, **meta):
    return {
        "source": source, "market": market, "metric": metric, "value": value,
        "unit": unit, "market_timestamp_ms": market_timestamp_ms,
        "retrieved_at_utc": utc_now(), "metadata": meta,
    }


def _float(value):
    if value is None:
        return None
    result = float(value)
    if not (-float("inf") < result < float("inf")):
        raise ValueError("Nonfinite number")
    return result


def fetch_binance():
    """USDⓈ-M BTCUSDT perpetual, not BTC-USD spot."""
    market = "BINANCE:BTCUSDT:PERP"
    k = request_json(SOURCES["binance"], "/fapi/v1/klines",
                     {"symbol": "BTCUSDT", "interval": "1d", "limit": 2})
    if not k:
        raise ValueError("No Binance daily candles")
    candle = k[-1]
    oi = request_json(SOURCES["binance"], "/fapi/v1/openInterest", {"symbol": "BTCUSDT"})
    premium = request_json(SOURCES["binance"], "/fapi/v1/premiumIndex", {"symbol": "BTCUSDT"})
    t = int(candle[0])
    return [
        observation("binance", market, "utc_daily_ohlcv",
                    {"open": _float(candle[1]), "high": _float(candle[2]),
                     "low": _float(candle[3]), "close": _float(candle[4]),
                     "base_volume": _float(candle[5]), "quote_volume": _float(candle[7]),
                     "open_time_ms": t, "close_time_ms": int(candle[6]),
                     "in_progress": int(candle[6]) > int(time.time()*1000)},
                    "USDT price; BTC base volume", t),
        observation("binance", market, "open_interest", _float(oi["openInterest"]),
                    "BTC contracts/base units", int(oi.get("time", time.time()*1000))),
        observation("binance", market, "mark_price", _float(premium["markPrice"]),
                    "USDT/BTC", int(premium.get("time", time.time()*1000))),
        observation("binance", market, "last_funding_rate",
                    _float(premium["lastFundingRate"]), "decimal fraction",
                    int(premium.get("time", time.time()*1000))),
    ]


def fetch_bybit():
    market = "BYBIT:BTCUSDT:LINEAR_PERP"
    k = bybit("/v5/market/kline",
              {"category": "linear", "symbol": "BTCUSDT", "interval": "D", "limit": 2})["list"]
    if not k:
        raise ValueError("No Bybit daily candles")
    candle = max(k, key=lambda x: int(x[0]))
    ticker = bybit("/v5/market/tickers",
                   {"category": "linear", "symbol": "BTCUSDT"})["list"][0]
    oi = bybit("/v5/market/open-interest",
               {"category": "linear", "symbol": "BTCUSDT", "intervalTime": "5min", "limit": 2})["list"]
    out = [
        observation("bybit", market, "utc_daily_ohlcv",
                    {"open": _float(candle[1]), "high": _float(candle[2]),
                     "low": _float(candle[3]), "close": _float(candle[4]),
                     "base_volume": _float(candle[5]), "turnover": _float(candle[6]),
                     "open_time_ms": int(candle[0]),
                     "in_progress": int(candle[0]) + 86400000 > int(time.time()*1000)},
                    "USDT price; BTC base volume", int(candle[0])),
        observation("bybit", market, "last_price", _float(ticker["lastPrice"]),
                    "USDT/BTC"),
        observation("bybit", market, "funding_rate", _float(ticker["fundingRate"]),
                    "decimal fraction"),
    ]
    if oi:
        record = max(oi, key=lambda x: int(x["timestamp"]))
        out.append(observation("bybit", market, "open_interest",
                   _float(record["openInterest"]), "BTC", int(record["timestamp"]),
                   note="5-minute bucket value, not necessarily live"))
    return out


def fetch_deribit():
    market = "DERIBIT:BTC:OPTIONS"
    r = request_json(SOURCES["deribit"], "/api/v2/public/get_book_summary_by_currency",
                     {"currency": "BTC", "kind": "option"})
    if r.get("error"):
        raise ValueError(str(r["error"])[:160])
    records = r.get("result") or []
    active = [x for x in records if x.get("open_interest") is not None]
    # Do not combine this with exchange perpetual OI: contract specs differ.
    total = sum(_float(x["open_interest"]) for x in active)
    return [observation("deribit", market, "option_open_interest_aggregate",
                        total, "Deribit reported option OI units",
                        instruments_count=len(active),
                        warning="Aggregate is exchange-specific; do not treat as global BTC options OI")]


def fetch_mempool():
    """Public on-chain context; tip height is not exchange-market activity."""
    r = request_json(SOURCES["mempool"], "/api/blocks/tip/height")
    return [observation("mempool.space", "BITCOIN:MAINNET",
                        "block_height", int(r), "blocks")]


FETCHERS = {
    "binance": fetch_binance,
    "bybit": fetch_bybit,
    "deribit": fetch_deribit,
    "mempool": fetch_mempool,
}
DOMAIN_STATUS = {
    "economics": "not_connected",
    "asset_fundamentals": "partial: mempool block height",
    "sentiment": "not_connected",
    "positioning_derivatives": "partial: exchange OI, funding, options OI",
    "intermarket_comparative_strength": "not_connected",
    "time_price": "partial: UTC daily perp candles",
    "orderflow_liquidity": "not_connected",
}


def collect_snapshot(fetchers=None):
    """Collect available data without allowing one provider failure to erase others."""
    observations, errors = [], []
    for name, fetch in (fetchers or FETCHERS).items():
        try:
            records = fetch()
            if not isinstance(records, list):
                raise ValueError("Fetcher must return a list")
            observations.extend(records)
        except (ValueError, KeyError, TypeError, IndexError, HTTPError, URLError,
                TimeoutError, OSError, json.JSONDecodeError) as exc:
            errors.append({"source": name, "error": str(exc)[:240]})
    return {"schema": "prxfit.snapshot.v1", "instrument": "BTC-USD",
            "as_of_utc": utc_now(), "observations": observations,
            "source_errors": errors, "domain_coverage": DOMAIN_STATUS.copy(),
            "note": "BTC-USD is a research query; individual feeds retain their true market and quote units."}


def _connect(path: Path):
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path)
    conn.execute("CREATE TABLE IF NOT EXISTS snapshots (id INTEGER PRIMARY KEY, created_at_ms INTEGER NOT NULL, data BLOB NOT NULL)")
    conn.execute("CREATE INDEX IF NOT EXISTS snapshots_time ON snapshots(created_at_ms)")
    return conn


def persist_snapshot(snapshot: dict, db_path: Path = DEFAULT_DB, max_bytes: int = LIMIT_BYTES):
    """Bound SQLite DB on disk; reject oversize and prune oldest snapshots.
    max_bytes covers this database only, not temporary files or Python packages.
    """
    import zlib
    if max_bytes < 100_000:
        raise ValueError("max_bytes too small")
    payload = zlib.compress(json.dumps(snapshot, allow_nan=False).encode("utf-8"), level=6)
    if len(payload) > max_bytes // 2:
        raise ValueError("Snapshot too large for storage budget")
    conn = _connect(Path(db_path))
    try:
        conn.execute("INSERT INTO snapshots(created_at_ms, data) VALUES (?, ?)",
                     (int(time.time()*1000), payload))
        conn.commit()
        # Conservative cap allows headroom for SQLite page accounting.
        target = int(max_bytes * 0.8)
        for _ in range(100000):
            conn.execute("PRAGMA wal_checkpoint(TRUNCATE)")
            if Path(db_path).stat().st_size <= target:
                break
            deleted = conn.execute("DELETE FROM snapshots WHERE id IN (SELECT id FROM snapshots ORDER BY id LIMIT 100)").rowcount
            conn.commit()
            if not deleted:
                break
        conn.execute("VACUUM")
        conn.commit()
        if Path(db_path).stat().st_size > max_bytes:
            raise RuntimeError("Storage budget exceeded; inspect database")
    finally:
        conn.close()


def latest_snapshot(db_path: Path = DEFAULT_DB):
    import zlib
    with _connect(Path(db_path)) as conn:
        row = conn.execute("SELECT data FROM snapshots ORDER BY id DESC LIMIT 1").fetchone()
    return json.loads(zlib.decompress(row[0])) if row else None
