"""Tamper-evident, conservative Tiingo free-tier quota reservations."""

from __future__ import annotations

import fcntl
import json
import os
import re
from datetime import UTC, datetime
from pathlib import Path

from scanner.hebeltrader.eodhd import canonical, sha
from scanner.hebeltrader.market_snapshot import _credentials


class TiingoQuotaLedger:
    """Reserve capacity before a live batch; reservations are deliberately never refunded."""

    def __init__(
        self,
        path,
        *,
        hourly_limit=50,
        daily_limit=1000,
        monthly_symbol_limit=500,
    ):
        if not all(
            type(value) is int and value > 0
            for value in (hourly_limit, daily_limit, monthly_symbol_limit)
        ):
            raise ValueError("quota limits must be positive integers")
        self.path = Path(path)
        self.hourly_limit = hourly_limit
        self.daily_limit = daily_limit
        self.monthly_symbol_limit = monthly_symbol_limit

    @staticmethod
    def _read(stream):
        previous = None
        records = []
        for line in stream.read().splitlines():
            record = json.loads(line)
            digest = record.pop("sha256")
            if record.get("previous_sha256") != previous or sha(canonical(record)) != digest:
                raise ValueError("quota ledger integrity error")
            _credentials(record)
            previous = digest
            records.append(record)
        return records, previous

    def _counts(self, records, at):
        at = at.astimezone(UTC)
        hour = at.strftime("%Y-%m-%dT%H")
        day = at.strftime("%Y-%m-%d")
        month = at.strftime("%Y-%m")
        reservations = [row["reservation"] for row in records]
        return {
            "hour_reserved_requests": sum(
                row["reserved_requests"] for row in reservations if row["hour_utc"] == hour
            ),
            "day_reserved_requests": sum(
                row["reserved_requests"] for row in reservations if row["day_utc"] == day
            ),
            "month_unique_symbols": len(
                {
                    symbol
                    for row in reservations
                    if row["month_utc"] == month
                    for symbol in row["symbols"]
                }
            ),
            "month_symbols": {
                symbol
                for row in reservations
                if row["month_utc"] == month
                for symbol in row["symbols"]
            },
        }

    def snapshot(self, at):
        self._validate_clock(at)
        if not self.path.exists():
            counts = self._counts([], at)
        else:
            with self.path.open("rb") as stream:
                records, _ = self._read(stream)
            counts = self._counts(records, at)
        counts.pop("month_symbols")
        return counts

    def reserve(self, *, symbols, max_requests, at):
        self._validate_clock(at)
        if type(max_requests) is not int or max_requests <= 0:
            raise ValueError("reserved requests must be a positive integer")
        symbols = sorted(set(symbols))
        if not symbols or any(not re.fullmatch(r"[A-Z0-9._-]{1,32}", value) for value in symbols):
            raise ValueError("invalid provider symbols")
        self.path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        fd = os.open(self.path, os.O_RDWR | os.O_CREAT | os.O_APPEND | os.O_NOFOLLOW, 0o600)
        with os.fdopen(fd, "r+b") as stream:
            fcntl.flock(stream, fcntl.LOCK_EX)
            records, previous = self._read(stream)
            counts = self._counts(records, at)
            if counts["hour_reserved_requests"] + max_requests > self.hourly_limit:
                raise ValueError("Tiingo hourly request limit exceeded")
            if counts["day_reserved_requests"] + max_requests > self.daily_limit:
                raise ValueError("Tiingo daily request limit exceeded")
            new_symbols = set(symbols) - counts["month_symbols"]
            if counts["month_unique_symbols"] + len(new_symbols) > self.monthly_symbol_limit:
                raise ValueError("Tiingo monthly symbol limit exceeded")
            instant = at.astimezone(UTC)
            reservation = {
                "at": instant.isoformat(),
                "hour_utc": instant.strftime("%Y-%m-%dT%H"),
                "day_utc": instant.strftime("%Y-%m-%d"),
                "month_utc": instant.strftime("%Y-%m"),
                "symbols": symbols,
                "reserved_requests": max_requests,
            }
            record = {"reservation": reservation, "previous_sha256": previous}
            record["sha256"] = sha(canonical(record))
            stream.write(canonical(record))
            stream.flush()
            os.fsync(stream.fileno())
        return reservation

    @staticmethod
    def _validate_clock(at):
        if not isinstance(at, datetime) or at.utcoffset() is None:
            raise ValueError("aware quota timestamp required")
