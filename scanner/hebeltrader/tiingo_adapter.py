"""Offline Tiingo normalization; raw and adjusted prices remain distinct."""

from decimal import Decimal, InvalidOperation

from .market_provider import RAW_BAR_FIELDS
from .tiingo import read_tiingo_record


def _number(value):
    try:
        result = Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError):
        raise ValueError("invalid Tiingo numeric value") from None
    if not result.is_finite():
        raise ValueError("invalid Tiingo numeric value")
    return str(result)


def normalize_tiingo_record(root, manifest_sha256):
    record = read_tiingo_record(root, manifest_sha256)
    bars, seen = [], set()
    for index, row in enumerate(record["payload"]):
        if not isinstance(row, dict) or any(field not in row for field in RAW_BAR_FIELDS):
            raise ValueError("invalid Tiingo row")
        day = str(row["date"])[:10]
        if day in seen:
            raise ValueError("duplicate Tiingo session")
        seen.add(day)
        values = {field: _number(row[field]) for field in RAW_BAR_FIELDS[1:]}
        if Decimal(values["volume"]) < 0:
            raise ValueError("invalid Tiingo volume")
        bars.append(
            dict(
                date=day,
                **values,
                adjusted_open=_number(row["adjOpen"]),
                adjusted_high=_number(row["adjHigh"]),
                adjusted_low=_number(row["adjLow"]),
                adjusted_close=_number(row["adjClose"]),
                adjusted_volume=_number(row["adjVolume"]),
                dividend_cash=_number(row["divCash"]),
                split_factor=_number(row["splitFactor"]),
                payload_pointer=f"/{index}",
            )
        )
    return dict(
        provider="Tiingo",
        instrument_type="stock",
        derivative_quote_capable=False,
        manifest_sha256=manifest_sha256,
        raw_sha256=record["raw_sha256"],
        retrieved_at=record["retrieved_at"],
        source_reference=record["source_reference"],
        license=record["license"],
        bars=bars,
        quality_status="offline_integrity_verified; venue/calendar completeness not inferred",
    )
