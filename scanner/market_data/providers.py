"""Pure normalization of integrity-checked provider archive records."""

from datetime import date, datetime, time
from decimal import Decimal, InvalidOperation
from zoneinfo import ZoneInfo

from .models import (
    CorporateAction,
    DailyBar,
    ExchangeCalendar,
    InstrumentListing,
    MarketDataBatch,
    PriceVector,
)


def _decimal(value, *, optional=False):
    if value is None and optional:
        return None
    try:
        result = Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError):
        raise ValueError("invalid numeric value") from None
    if not result.is_finite():
        raise ValueError("invalid numeric value")
    return result


def _close(day: date, listing: InstrumentListing, calendar: ExchangeCalendar | None):
    if calendar is not None:
        if listing.mic not in calendar.supported_mics or listing.timezone != calendar.timezone:
            raise ValueError("verified calendar listing mismatch")
        close = calendar.sessions.get(day)
        if close is None:
            raise ValueError("provider session absent from verified calendar")
        return close, "verified_exchange_calendar", calendar.raw_sha256
    # US pilot listings currently use regular-session EOD. Early-close evidence belongs
    # in an independently sourced calendar and is never inferred here.
    return (
        datetime.combine(day, time(16), ZoneInfo(listing.timezone)),
        "modeled_regular_close_unverified",
        None,
    )


def _common(record, listing, *, provider, bars, actions):
    retrieved_at = datetime.fromisoformat(str(record["retrieved_at"]))
    return MarketDataBatch(
        provider=provider,
        instrument=listing,
        bars=bars,
        actions=actions,
        retrieved_at=retrieved_at,
        source_reference=record["source_reference"],
        license_reference=record["license"],
        raw_sha256=record["raw_sha256"],
        manifest_sha256=record["manifest_sha256"],
        source_status="raw_archive_integrity_verified",
        availability_basis="modeled_session_close",
        training_eligible=False,
    )


def normalize_tiingo(
    record: dict,
    listing: InstrumentListing,
    *,
    calendar: ExchangeCalendar | None = None,
) -> MarketDataBatch:
    if (
        record.get("vendor") != "Tiingo"
        or record.get("request", {}).get("symbol") != listing.provider_symbol
    ):
        raise ValueError("provider symbol mismatch")
    retrieved_at = datetime.fromisoformat(str(record["retrieved_at"]))
    request = record["request"]
    bars, actions = [], []
    for index, row in enumerate(record.get("payload", [])):
        day = date.fromisoformat(str(row["date"])[:10])
        if not date.fromisoformat(request["start"]) <= day <= date.fromisoformat(request["end"]):
            raise ValueError("price outside provider request window")
        close, close_status, calendar_sha = _close(day, listing, calendar)
        bars.append(
            DailyBar(
                session_date=day,
                session_end_at=close,
                modeled_available_at=close,
                session_end_status=close_status,
                calendar_sha256=calendar_sha,
                raw=PriceVector(
                    **{
                        key: _decimal(row[key])
                        for key in ("open", "high", "low", "close", "volume")
                    }
                ),
                adjusted=PriceVector(
                    open=_decimal(row["adjOpen"]),
                    high=_decimal(row["adjHigh"]),
                    low=_decimal(row["adjLow"]),
                    close=_decimal(row["adjClose"]),
                    volume=_decimal(row["adjVolume"]),
                ),
                retrieved_at=retrieved_at,
                source_pointer=f"/{index}",
            )
        )
        dividend = _decimal(row.get("divCash", 0))
        split = _decimal(row.get("splitFactor", 1))
        if dividend:
            actions.append(
                CorporateAction(
                    kind="dividend",
                    effective_date=day,
                    value=dividend,
                    currency=listing.currency,
                    source_pointer=f"/{index}/divCash",
                )
            )
        if split != 1:
            actions.append(
                CorporateAction(
                    kind="split",
                    effective_date=day,
                    value=split,
                    source_pointer=f"/{index}/splitFactor",
                )
            )
    if not bars:
        raise ValueError("empty price series")
    return _common(record, listing, provider="Tiingo", bars=bars, actions=actions)


def normalize_eodhd(
    record: dict,
    listing: InstrumentListing,
    *,
    calendar: ExchangeCalendar | None = None,
) -> MarketDataBatch:
    request = record.get("request", {})
    if (
        record.get("vendor") != "EODHD"
        or request.get("endpoint") != "eod"
        or request.get("symbol") != listing.provider_symbol
    ):
        raise ValueError("provider symbol mismatch")
    retrieved_at = datetime.fromisoformat(str(record["retrieved_at"]))
    bars = []
    for index, row in enumerate(record.get("payload", [])):
        day = date.fromisoformat(str(row["date"]))
        start, end = request.get("start"), request.get("end")
        if start and day < date.fromisoformat(start) or end and day > date.fromisoformat(end):
            raise ValueError("price outside provider request window")
        close, close_status, calendar_sha = _close(day, listing, calendar)
        bars.append(
            DailyBar(
                session_date=day,
                session_end_at=close,
                modeled_available_at=close,
                session_end_status=close_status,
                calendar_sha256=calendar_sha,
                raw=PriceVector(
                    **{
                        key: _decimal(row[key])
                        for key in ("open", "high", "low", "close", "volume")
                    }
                ),
                adjusted=PriceVector(
                    open=None,
                    high=None,
                    low=None,
                    close=_decimal(row.get("adjusted_close", row["close"])),
                    volume=None,
                ),
                retrieved_at=retrieved_at,
                source_pointer=f"/{index}",
            )
        )
    if not bars:
        raise ValueError("empty price series")
    return _common(record, listing, provider="EODHD", bars=bars, actions=[])
