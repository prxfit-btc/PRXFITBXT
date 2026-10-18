"""Run with: python -m prxfit_data BTC-USD"""
import argparse
import json
from .engine import collect_snapshot, persist_snapshot

def main():
    parser = argparse.ArgumentParser(description="PRXFIT BXT BTC public-data snapshot")
    parser.add_argument("symbol", nargs="?", default="BTC-USD")
    parser.add_argument("--no-save", action="store_true", help="do not save SQLite snapshot")
    args = parser.parse_args()
    if args.symbol.upper() != "BTC-USD":
        parser.error("V0.1 currently supports BTC-USD only")
    snapshot = collect_snapshot()
    if not args.no_save:
        persist_snapshot(snapshot)
    print(json.dumps(snapshot, indent=2, allow_nan=False))

if __name__ == "__main__":
    main()
