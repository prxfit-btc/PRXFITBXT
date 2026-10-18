"""V0.3 free spot and Bitcoin fundamentals. Isolated from existing TradingAgents graph."""
from __future__ import annotations
import json
from datetime import datetime, timezone
from .engine import request_json, observation, _float, collect_snapshot

COINBASE = "https://api.exchange.coinbase.com"
MEMPOOL = "https://mempool.space"

def fetch_coinbase_spot():
    market = "COINBASE:BTC-USD:SPOT"
    ticker = request_json(COINBASE, "/products/BTC-USD/ticker")
    bid, ask, last = (_float(ticker[k]) for k in ("bid", "ask", "price"))
    if min(bid, ask, last) <= 0 or ask < bid:
        raise ValueError("Invalid Coinbase spot quote")
    market_time = ticker.get("time")
    timestamp_ms = None
    if market_time:
        parsed = datetime.fromisoformat(market_time.replace("Z", "+00:00"))
        if parsed.tzinfo is None:
            raise ValueError("Missing timezone in Coinbase quote")
        timestamp_ms = int(parsed.timestamp() * 1000)
    return [
        observation("coinbase", market, "last_trade_price", last, "USD/BTC", timestamp_ms),
        observation("coinbase", market, "best_bid", bid, "USD/BTC", timestamp_ms),
        observation("coinbase", market, "best_ask", ask, "USD/BTC", timestamp_ms),
        observation("coinbase", market, "quoted_spread", round(ask-bid, 2), "USD", timestamp_ms),
    ]

def fetch_bitcoin_network():
    fees = request_json(MEMPOOL, "/api/v1/fees/recommended")
    adjustment = request_json(MEMPOOL, "/api/v1/difficulty-adjustment")
    block_height = request_json(MEMPOOL, "/api/blocks/tip/height")
    market = "BITCOIN:MAINNET"
    results = [observation("mempool.space", market, "block_height", int(block_height), "blocks")]
    for name in ("fastestFee", "halfHourFee", "hourFee", "economyFee", "minimumFee"):
        if name in fees:
            results.append(observation("mempool.space", market, name, _float(fees[name]), "sat/vB"))
    for key, unit in (("difficultyChange","percent"), ("remainingBlocks","blocks"),
                      ("remainingTime","seconds"), ("previousRetarget","percent")):
        if key in adjustment and adjustment[key] is not None:
            results.append(observation("mempool.space", market, key, _float(adjustment[key]), unit))
    return results

def collect_expansion(fetchers=None):
    """Independent failures are visible; never confuse spot with derivatives."""
    jobs = {"coinbase_spot":fetch_coinbase_spot, "bitcoin_network":fetch_bitcoin_network}
    if fetchers is not None:
        jobs = fetchers
    data, failures = [], []
    for name, func in jobs.items():
        try:
            data.extend(func())
        except Exception as exc:
            failures.append({"source":name,"error":f"{type(exc).__name__}: {str(exc)[:180]}"})
    return {
        "schema":"prxfit.expansion.v1", "query":"BTC-USD",
        "retrieved_at_utc":datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "observations":data, "source_errors":failures,
        "coverage":{
            "economics":"not_connected",
            "asset_fundamentals":"partial: public Bitcoin network/fees",
            "sentiment":"not_connected",
            "positioning_derivatives":"provided by V0.1/V0.2, not included here",
            "intermarket_comparative_strength":"not_connected",
            "time_price":"spot quote only; OHLCV supplied separately",
            "orderflow_liquidity":"top-of-book spread only; not full orderflow"},
        "integrity_note":"Coinbase spot USD and Binance/Bybit perpetual USDT are distinct markets; never average as one price."
    }

def main():
    print(json.dumps(collect_expansion(), indent=2, allow_nan=False))

if __name__=="__main__":
    main()
