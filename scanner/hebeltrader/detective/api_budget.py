"""Atomic, pessimistic monthly API reservations in a dedicated private ledger.

The euro ceiling is stored in the ledger. The constructor only seeds it when no
ceiling exists yet. After the month is exhausted the operator can store a higher
ceiling; past reservations stay counted.
"""

import sqlite3
from contextlib import contextmanager
from datetime import UTC, datetime
from pathlib import Path

# Typo guard. The operator-facing form uses the same ceiling.
HARD_MAX_CENTS = 200_000
# At the historical €20 seed this is 1 500 searches and 600 model calls.
_CALLS_PER_EURO = {"search": 75, "ai": 30}


class ApiBudget:
    def __init__(self, path, *, cap_cents=2000):
        if not isinstance(cap_cents, int) or not 1 <= cap_cents <= HARD_MAX_CENTS:
            raise ValueError("Monthly API reservation cap must be EUR 0.01–2000.00")
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._default_cap = cap_cents
        with self._db() as db:
            db.execute(
                "CREATE TABLE IF NOT EXISTS reservations "
                "(id INTEGER PRIMARY KEY, month TEXT, provider TEXT, cents INTEGER, at TEXT)"
            )
            db.execute("CREATE TABLE IF NOT EXISTS ledger_meta (key TEXT PRIMARY KEY, value TEXT)")
            migrated = db.execute("SELECT value FROM ledger_meta WHERE key='pricing_v2'").fetchone()
            if migrated is None:
                # V1 charged a fictional EUR 0.05/0.10 per call. One cent is a
                # conservative ceiling for the configured Tavily Basic request and
                # bounded GPT-4.1-mini request at the published provider tariffs.
                db.execute("UPDATE reservations SET cents=1 WHERE cents>1")
                db.execute("INSERT INTO ledger_meta VALUES('pricing_v2','2026-10-29')")
            self._cap(db)

    @contextmanager
    def _db(self):
        db = sqlite3.connect(self.path, timeout=15)
        try:
            with db:
                yield db
        finally:
            db.close()

    def _cap(self, db) -> int:
        row = db.execute("SELECT value FROM ledger_meta WHERE key='monthly_cap_cents'").fetchone()
        if row is None:
            db.execute(
                "INSERT INTO ledger_meta(key, value) VALUES('monthly_cap_cents', ?)",
                (str(self._default_cap),),
            )
            return self._default_cap
        try:
            value = int(row[0])
        except (TypeError, ValueError):
            value = self._default_cap
        if not 1 <= value <= HARD_MAX_CENTS:
            return self._default_cap
        return value

    def _call_limit(self, provider: str, cap_cents: int) -> int:
        return max(1, (cap_cents * _CALLS_PER_EURO[provider]) // 100)

    def reserve(self, provider, cents):
        if provider not in ("search", "ai") or cents <= 0:
            raise ValueError("Invalid API reservation")
        now = datetime.now(UTC)
        month = now.strftime("%Y-%m")
        with self._db() as db:
            db.execute("BEGIN IMMEDIATE")
            cap = self._cap(db)
            used = db.execute(
                "SELECT COALESCE(SUM(cents),0) FROM reservations WHERE month=?", (month,)
            ).fetchone()[0]
            count = db.execute(
                "SELECT COUNT(*) FROM reservations WHERE month=? AND provider=?", (month, provider)
            ).fetchone()[0]
            if used + cents > cap or count >= self._call_limit(provider, cap):
                raise ValueError("Monthly API budget exhausted")
            db.execute(
                "INSERT INTO reservations(month,provider,cents,at) VALUES(?,?,?,?)",
                (month, provider, cents, now.isoformat()),
            )

    def set_cap(self, cents: int) -> dict:
        """Store a new monthly ceiling. It must exceed what this month already reserved."""
        if not isinstance(cents, int) or not 1 <= cents <= HARD_MAX_CENTS:
            raise ValueError("Monatsbudget muss zwischen 0,01 € und 2000,00 € liegen")
        month = datetime.now(UTC).strftime("%Y-%m")
        with self._db() as db:
            db.execute("BEGIN IMMEDIATE")
            used = db.execute(
                "SELECT COALESCE(SUM(cents),0) FROM reservations WHERE month=?", (month,)
            ).fetchone()[0]
            if cents <= used:
                raise ValueError(
                    "Neues Monatsbudget muss über dem bereits vorgemerkten Betrag liegen"
                )
            db.execute(
                "INSERT INTO ledger_meta(key, value) VALUES('monthly_cap_cents', ?) "
                "ON CONFLICT(key) DO UPDATE SET value=excluded.value",
                (str(cents),),
            )
        return self.summary()

    def summary(self):
        with self._db() as db:
            month = datetime.now(UTC).strftime("%Y-%m")
            cap = self._cap(db)
            used = db.execute(
                "SELECT COALESCE(SUM(cents),0) FROM reservations WHERE month=?", (month,)
            ).fetchone()[0]
            rows = db.execute(
                "SELECT provider, COUNT(*), COALESCE(SUM(cents),0) "
                "FROM reservations WHERE month=? GROUP BY provider",
                (month,),
            ).fetchall()
        per_provider = {provider: (calls, cents) for provider, calls, cents in rows}
        remaining = max(cap - used, 0)
        return {
            "month": month,
            "reserved_cents": used,
            "cap_cents": cap,
            "remaining_cents": remaining,
            "exhausted": remaining <= 0,
            "max_cap_cents": HARD_MAX_CENTS,
            "providers": {
                "search": {
                    "calls": per_provider.get("search", (0, 0))[0],
                    "reserved_cents": per_provider.get("search", (0, 0))[1],
                },
                "ai": {
                    "calls": per_provider.get("ai", (0, 0))[0],
                    "reserved_cents": per_provider.get("ai", (0, 0))[1],
                },
            },
            "accounting": "conservative_call_ceiling_not_provider_invoice",
        }
