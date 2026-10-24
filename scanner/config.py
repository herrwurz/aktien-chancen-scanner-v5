import re
from decimal import Decimal
from pathlib import Path
from typing import Literal

from pydantic import Field, SecretStr, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict
from sqlalchemy import URL


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: SecretStr | None = None
    postgres_host: str = "db"
    postgres_port: int = Field(default=5432, ge=1, le=65535)
    postgres_db: str = "scanner"
    postgres_user: str = "scanner"
    postgres_password: SecretStr = SecretStr("")
    provider: Literal["binance_spot", "fixture"] = "binance_spot"
    symbols: list[str] = ["BTCUSDT", "ETHUSDT"]
    intervals: list[Literal["5m", "15m"]] = ["5m", "15m"]
    scan_seconds: int = Field(default=60, ge=10)
    volume_lookback: int = Field(default=20, ge=1, le=998)
    volume_threshold: Decimal = Field(default=Decimal("3"), gt=1, allow_inf_nan=False)
    min_quote_volume: Decimal = Field(default=Decimal("100000"), ge=0, allow_inf_nan=False)
    detective_research_mode: Literal["fixture", "cached_research", "live_research"] = "fixture"
    detective_research_snapshot: Path = Path("reports/research-v23/snapshot.json")
    detective_research_cache_dir: Path = Path("reports/research-v23/sec-cache")
    detective_live_allow_network: bool = False
    detective_live_max_requests: int = Field(default=0, ge=0, le=101)
    detective_live_max_candidates: int = Field(default=10, ge=1, le=50)
    detective_live_request_timeout_seconds: float = Field(default=10, ge=1, le=30)
    detective_live_max_duration_seconds: float = Field(default=120, ge=1, le=300)
    detective_live_api_token: SecretStr | None = None
    sec_user_agent: str | None = None

    @field_validator("symbols")
    @classmethod
    def valid_symbols(cls, value):
        if (
            not value
            or len(value) > 100
            or any(not re.fullmatch(r"[A-Z0-9]{3,30}", s) for s in value)
        ):
            raise ValueError("Use 1–100 uppercase exchange symbols, e.g. BTCUSDT")
        return list(dict.fromkeys(value))

    @field_validator("intervals")
    @classmethod
    def nonempty_intervals(cls, value):
        if not value:
            raise ValueError("At least one interval required")
        return list(dict.fromkeys(value))

    def db_url(self):
        if self.database_url is not None:
            return self.database_url.get_secret_value()
        return URL.create(
            "postgresql+psycopg",
            username=self.postgres_user,
            password=self.postgres_password.get_secret_value(),
            host=self.postgres_host,
            port=self.postgres_port,
            database=self.postgres_db,
        )
