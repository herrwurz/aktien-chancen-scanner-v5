"""Atomic, pessimistic monthly API reservations in a dedicated private ledger."""

import sqlite3
from contextlib import contextmanager
from datetime import UTC, datetime
from pathlib import Path


class ApiBudget:
    def __init__(self, path, *, cap_cents=2000):
        if not 1 <= cap_cents <= 2000:
            raise ValueError("Monthly API reservation cap must be EUR 0.01–20.00")
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.cap_cents = cap_cents
        with self._db() as db:
            db.execute(
                "CREATE TABLE IF NOT EXISTS reservations "
                "(id INTEGER PRIMARY KEY, month TEXT, provider TEXT, cents INTEGER, at TEXT)"
            )

    @contextmanager
    def _db(self):
        db = sqlite3.connect(self.path, timeout=15)
        try:
            with db:
                yield db
        finally:
            db.close()

    def reserve(self, provider, cents):
        if provider not in ("search", "ai") or cents <= 0:
            raise ValueError("Invalid API reservation")
        now = datetime.now(UTC)
        month = now.strftime("%Y-%m")
        with self._db() as db:
            db.execute("BEGIN IMMEDIATE")
            used = db.execute(
                "SELECT COALESCE(SUM(cents),0) FROM reservations WHERE month=?", (month,)
            ).fetchone()[0]
            count = db.execute(
                "SELECT COUNT(*) FROM reservations WHERE month=? AND provider=?", (month, provider)
            ).fetchone()[0]
            if used + cents > self.cap_cents or count >= (500 if provider == "search" else 200):
                raise ValueError("Monthly API budget exhausted")
            db.execute(
                "INSERT INTO reservations(month,provider,cents,at) VALUES(?,?,?,?)",
                (month, provider, cents, now.isoformat()),
            )

    def summary(self):
        with self._db() as db:
            month = datetime.now(UTC).strftime("%Y-%m")
            used = db.execute(
                "SELECT COALESCE(SUM(cents),0) FROM reservations WHERE month=?", (month,)
            ).fetchone()[0]
        return {
            "month": month,
            "reserved_cents": used,
            "cap_cents": self.cap_cents,
            "accounting": "pessimistic_reservations_not_provider_invoice",
        }
