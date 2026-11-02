# Cross-asset scanner V6.2: operating decisions

- Scan all Binance USDT ticker rows returned by the source, not only top-volume assets.
- Apply a minimum 24h quote-volume floor of 100,000 USDT to the discovery candidate pool.
- Rank the discovery candidates by absolute 24h price change, then quote volume.
- Outside 07:00/19:00 Vienna full scans, fetch expensive 5m candles for the top 20 absolute-move names plus up to 60 rotating names (≤80). This is a **request budget**, not a market-overview cap.
- Set `CRYPTO_DISCOVER_UNIVERSE=true` to override the default static BTC/ETH symbol list.
- This is Binance-only coverage, not a global CEX/DEX market scan. 24h change is a lagging ranking signal, not an early-entry guarantee.
- Momentum candidates are research-only; do not call them executable Bitpanda buy signals without listing, spread, liquidity, and risk checks.
- Before merge: require successful GitHub Actions lint, format and tests for the exact PR head.
- Before Hetzner deployment: build the research image separately; run a one-shot scan; inspect integrity-checked journal with `read_run_journal`; preserve the production stack and Docker volumes.
- Do not modify the independent HEBELTRADER detective as part of this work.
