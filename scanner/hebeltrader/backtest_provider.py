"""Offline, explicit-calendar stock history. No inferred sessions or adjusted prices.

Manifest identity uses ``wkn``/``isin`` (``instrument_wkn``/``instrument_isin``
aliases accepted). Coverage is an explicit assertion by the named data source;
the provider checks its bounds and calendar, but cannot certify vendor completeness.
CSV timestamps must use the venue local UTC offset, including daylight saving;
coverage and retrieval timestamps may use any explicit UTC offset.
"""

from __future__ import annotations

import csv
import hashlib
import io
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from pathlib import Path
from typing import Protocol
from zoneinfo import ZoneInfo

from .backtest import Bar


@dataclass
class MarketHistory:
    bars: list[Bar]
    source: dict
    issues: list[str]


class HistoricalStockProvider(Protocol):
    def load(
        self, spec: dict, *, instrument: dict, available_at: datetime, as_of: datetime
    ) -> MarketHistory: ...


def _at(value):
    result = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    if result.utcoffset() is None:
        raise ValueError("timezone required")
    return result


class CsvStockProvider:
    def __init__(self, root: Path):
        self.root = Path(root).resolve()

    def load(
        self, spec: dict, *, instrument: dict, available_at: datetime, as_of: datetime
    ) -> MarketHistory:
        source = {}
        source["sha256"] = {}
        result = MarketHistory([], source, [])

        def issue(name):
            if name not in result.issues:
                result.issues.append(name)

        required = (
            "file",
            "symbol",
            "venue",
            "timezone",
            "currency",
            "adjustment",
            "source_reference",
            "license",
            "retrieved_at",
            "calendar_file",
            "calendar_reference",
            "corporate_actions_file",
            "corporate_actions_reference",
            "coverage_start",
            "coverage_end",
            "identity_reference",
            "identity_valid_from",
            "identity_valid_until",
        )
        allowed = (*required, "wkn", "isin", "instrument_wkn", "instrument_isin", "delisted_at")
        if isinstance(spec, dict):
            source.update({key: spec[key] for key in allowed if key in spec})
        if any(not source.get(k) for k in required):
            issue("missing_metadata")
            return result
        identities = {k: source.get(k) or source.get("instrument_" + k) for k in ("wkn", "isin")}
        if not any(identities.values()):
            issue("missing_metadata")
        if not any(value and value == instrument.get(key) for key, value in identities.items()):
            issue("instrument_mismatch")
        for key, value in identities.items():
            if value and instrument.get(key) and value != instrument[key]:
                issue("instrument_mismatch")
            if source.get(key) and source.get("instrument_" + key):
                if source[key] != source["instrument_" + key]:
                    issue("instrument_mismatch")
        source.update({k: v for k, v in identities.items() if v})
        if source["currency"] != instrument.get("currency"):
            issue("currency_mismatch")
        if source["adjustment"] != "raw":
            issue("corporate_action_requires_reconciliation")
        try:
            zone = ZoneInfo(source["timezone"])
            available_at, as_of = _at(available_at), _at(as_of)
            if available_at > as_of:
                raise ValueError("invalid window")
            baseline = min(_at(instrument.get("levels_as_of", available_at)), available_at)
            identity_start = _at(source["identity_valid_from"])
            identity_end = _at(source["identity_valid_until"])
            if identity_start > baseline or identity_end < as_of or identity_start > identity_end:
                issue("instrument_mismatch")
            retrieved = _at(source["retrieved_at"])
            start, end = _at(source["coverage_start"]), _at(source["coverage_end"])
            if start > baseline or end < as_of or start > end or retrieved < as_of:
                issue("stale_metadata")
            if source.get("delisted_at") and _at(source["delisted_at"]) <= as_of:
                issue("delisted_without_exit")
        except (ValueError, TypeError, KeyError):
            issue("missing_metadata")
            return result

        def local_at(value):
            stamp = _at(value)
            if stamp.utcoffset() != stamp.astimezone(zone).utcoffset():
                raise ValueError("timestamp does not match venue timezone")
            return stamp

        def rows(key, columns):
            try:
                path = (self.root / source[key]).resolve()
                if not path.is_relative_to(self.root):
                    raise ValueError("path escapes root")
                raw = path.read_bytes()
                source["sha256"][key] = hashlib.sha256(raw).hexdigest()
                reader = csv.DictReader(io.StringIO(raw.decode("utf-8-sig")))
                if not set(columns).issubset(reader.fieldnames or []):
                    raise ValueError("missing CSV columns")
                return list(reader)
            except (OSError, ValueError, TypeError, UnicodeError, csv.Error):
                issue(
                    "data_unavailable"
                    if key == "file"
                    else "invalid_calendar"
                    if key == "calendar_file"
                    else "missing_metadata"
                )
                return None

        calendar = rows("calendar_file", ("timestamp", "end_timestamp"))
        actions = rows("corporate_actions_file", ("timestamp", "type"))
        raw_bars = rows(
            "file", ("timestamp", "end_timestamp", "open", "high", "low", "close", "volume")
        )
        expected = {}
        if calendar is not None:
            try:
                all_sessions = {}
                for row in calendar:
                    opened, closed = local_at(row["timestamp"]), local_at(row["end_timestamp"])
                    if closed <= opened or opened in all_sessions:
                        raise ValueError("invalid session")
                    all_sessions[opened] = closed
                    if opened > available_at and closed <= as_of:
                        expected[opened] = closed
                ordered = sorted(all_sessions.items())
                if any(a[1] > b[0] for a, b in zip(ordered, ordered[1:], strict=False)):
                    raise ValueError("overlapping sessions")
            except (ValueError, TypeError, KeyError):
                issue("invalid_calendar")
        if raw_bars is not None:
            seen = set()
            for row in raw_bars:
                try:
                    opened = _at(row["timestamp"])
                    if opened <= available_at or opened > as_of:
                        continue
                    closed = _at(row["end_timestamp"])
                    if closed > as_of:
                        continue
                    opened, closed = local_at(row["timestamp"]), local_at(row["end_timestamp"])
                    if opened in seen:
                        issue("invalid_ohlc")
                        continue
                    seen.add(opened)
                    if expected.get(opened) != closed:
                        issue("invalid_calendar")
                        continue
                    prices = [Decimal(row[k]) for k in ("open", "high", "low", "close")]
                    volume = Decimal(row["volume"])
                    if not all(v.is_finite() for v in prices + [volume]) or volume < 0:
                        raise ValueError("nonfinite prices or invalid volume")
                    result.bars.append(
                        Bar(
                            at=opened,
                            end_at=closed,
                            open=prices[0],
                            high=prices[1],
                            low=prices[2],
                            close=prices[3],
                            volume=volume,
                        )
                    )
                except (ValueError, TypeError, KeyError, ArithmeticError):
                    issue("invalid_ohlc")
            if set(expected) - {bar.at for bar in result.bars}:
                issue("missing_sessions")
        result.bars.sort(key=lambda b: b.at)
        if not result.bars:
            issue("data_unavailable")
        if actions is not None:
            try:
                for row in actions:
                    stamp = _at(row["timestamp"])
                    if baseline <= stamp <= as_of:
                        local_at(row["timestamp"])
                        # Unknown action types are deliberately conservative, too.
                        issue("corporate_action_requires_reconciliation")
            except (ValueError, TypeError, KeyError):
                issue("missing_metadata")
        return result
