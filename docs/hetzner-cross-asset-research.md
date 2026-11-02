# Hetzner: cross-asset research worker (pilot)

This is a **research-only** one-shot worker using the existing Docker image. It does
not send purchase alerts, validate Bitpanda listings, or place orders. It does not
claim broad stock or crypto market coverage.

## Prerequisites

Docker Engine with Compose plugin; the repository checked out on Hetzner.
The existing `compose.yaml` requires `POSTGRES_PASSWORD` even for this
isolated profile because its common environment is evaluated by Compose.

Configure a local `.env` (do not commit it):

```dotenv
POSTGRES_PASSWORD=<existing database password>
CRYPTO_SYMBOLS=["BTCUSDT","ETHUSDT"]
SEC_TARGETS=[{"cik":320193,"symbol":"AAPL"}]
SEC_ALLOW_NETWORK=true
SEC_MAX_REQUESTS=1
SEC_USER_AGENT=Scanner Research contact@example.org
```

Replace the SEC User-Agent contact with your real address. Without explicit
SEC network permission the stock side only uses existing immutable cache
snapshots and may report unavailable. Cached SEC submissions are not refreshed:
a cache hit must **not** be interpreted as a new live check. This is a limited
technical pilot, not a production early-warning engine.

## One-shot execution

```bash
docker compose --profile research build cross-asset-research
docker compose --profile research run --rm --no-deps cross-asset-research
```

The command prints a short JSON summary. Detailed run envelopes and SEC
research evidence are stored in the named volume
`cross_asset_research` (under `/data` inside the container).
A `partial` status means at least one market scan was unavailable or
incomplete. An envelope `unavailable` means **both** asset classes failed or
had no configured coverage. Never interpret unavailable data as a no-signal
outcome. Live SEC journaling is limited to the last 72 hours of filings so a
stale submissions cache cannot re-append the full historical form set each run.

For a scheduled pilot, run the one-shot command via a host systemd timer or
cron under a **single-writer lock**. Do not start multiple simultaneous runs:
the append-only JSONL journal has no cross-process locking.

## Production readiness gaps

- The stock side checks only configured SEC CIKs, and the immutable SEC cache
  requires an explicit refresh policy for recurring monitoring.
- The crypto side checks only configured Binance spot pairs, not all Bitpanda
  assets or DEX smallcaps. Candle collection alone is not a trading signal.
- No exchange-order-book, fees, Bitpanda execution quotes, community scanning,
  tradeable setup qualification, alert delivery, or market-wide recall.
- A healthy container only proves the research pass ran, not that market
  coverage or actionable signals are complete.
