# Multi-Asset Chancen-Scanner V6

Docker-based Python scanner for crypto, stocks and future leveraged-instrument analysis.

## MVP
- Python 3.12, FastAPI, PostgreSQL, SQLAlchemy/Alembic, pytest.
- Isolated Docker Compose stack alongside existing Immich; no changes to Immich resources.
- Modular CEX spot, DEX pool, stock and authorized community-data adapters.
- Early 5m/15m volume/liquidity acceleration and news catalysts.
- Point-in-time audit trail for candidates, rejection reasons and 1h/4h/24h outcomes.
- Paper trading only; no live order execution.
- Bitpanda availability, spreads and fees must be verified before actionable recommendations.
- Secrets outside source control; database private; dashboard local-only until authentication.

## First Codex task
Scaffold API, worker, DB migrations, a real public spot provider and fixture provider, candidate engine, read-only dashboard endpoints, Docker Compose, automated tests and deployment instructions. Validate historical DOOD/ZEREBRO cases only with timestamped historical evidence and without look-ahead bias.
