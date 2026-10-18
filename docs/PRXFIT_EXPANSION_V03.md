# PRXFIT BXT V0.3 — Free BTC spot and network expansion

**Experiment only; original console unchanged.** This branch builds on V0.2.

From the extracted repository's root folder run:

```powershell
python -m prxfit_data.expansion
```

This invokes read-only, no-key public APIs for Coinbase Exchange BTC-USD **spot** best bid/ask/last trade and mempool.space Bitcoin mainnet block height, fees and difficulty estimate. All results show source, market, unit, and retrieval timestamp; a true exchange observation timestamp is included when supplied. One failed provider does not hide another.

Run offline tests:

```powershell
python -m unittest discover -s tests -p "test_prxfit_*.py"
```

Nothing persists to disk in this V0.3 module. No paid inference, no trade execution, no modification to subscription LLM configuration. Domains not implemented are marked missing, not synthesized. Public APIs can rate-limit or geo-block, and live Windows testing remains to be done before merging.

Up next: point-in-time macro/intermarket data, source quality audits, bounded historical storage across tables, and seven-domain synthesis.
