"""Forward-only SEC news pilot. No execution, paid providers, or buy alerts."""

from __future__ import annotations

import argparse
import fcntl
import hashlib
import json
import os
import sqlite3
import time
import uuid
from datetime import UTC, datetime, timedelta
from decimal import Decimal, InvalidOperation
from pathlib import Path
from zoneinfo import ZoneInfo

import httpx

from scanner.hebeltrader.eodhd import canonical, exclusive, sha
from scanner.hebeltrader.tiingo import TiingoClient
from scanner.market_data.pilot import EXCHANGES
from scanner.market_data.quota import TiingoQuotaLedger
from scanner.opportunities.features import compute_features
from scanner.research_providers.sec_edgar import (
    SecEdgarClient,
    normalize_submission_events,
    normalize_universe,
)

NY = ZoneInfo("America/New_York")


def clock():
    return datetime.now(UTC)


def aware(value):
    result = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if result.utcoffset() is None:
        raise ValueError("explicit timezone required")
    return result.astimezone(UTC)


class Journal:
    """Transactional append-only API with tamper evidence, not administrator-proof WORM."""

    def __init__(self, path, *, read_only=False):
        self.path = Path(path).resolve()
        self.read_only = read_only
        if read_only:
            self.verify()
            return
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with sqlite3.connect(self.path) as db:
            db.executescript("""
                CREATE TABLE IF NOT EXISTS audit (
                    seq INTEGER PRIMARY KEY, kind TEXT NOT NULL, payload TEXT NOT NULL,
                    previous_sha256 TEXT, sha256 TEXT NOT NULL UNIQUE);
                CREATE TRIGGER IF NOT EXISTS audit_no_update BEFORE UPDATE ON audit
                    BEGIN SELECT RAISE(ABORT, 'append only'); END;
                CREATE TRIGGER IF NOT EXISTS audit_no_delete BEFORE DELETE ON audit
                    BEGIN SELECT RAISE(ABORT, 'append only'); END;
            """)
        self.verify()

    def records(self):
        with sqlite3.connect(self.path.as_uri() + "?mode=ro", uri=True) as db:
            db.row_factory = sqlite3.Row
            return [
                dict(row) | {"payload": json.loads(row["payload"])}
                for row in db.execute("SELECT * FROM audit ORDER BY seq")
            ]

    def verify(self):
        previous = None
        records = self.records()
        for seq, row in enumerate(records, 1):
            body = {key: row[key] for key in ("seq", "kind", "payload", "previous_sha256")}
            if (
                row["seq"] != seq
                or row["previous_sha256"] != previous
                or sha(canonical(body)) != row["sha256"]
            ):
                raise ValueError("audit integrity error")
            previous = row["sha256"]
        return len(records)

    def append(self, kind, payload):
        if self.read_only:
            raise ValueError("read-only journal")
        # Startup/full verification detects tampering; triggers guard normal writes.
        # Do not rehash all historical payloads on every individual append.
        with sqlite3.connect(self.path, timeout=30) as db:
            db.execute("BEGIN IMMEDIATE")
            row = db.execute("SELECT seq, sha256 FROM audit ORDER BY seq DESC LIMIT 1").fetchone()
            body = {
                "seq": row[0] + 1 if row else 1,
                "kind": kind,
                "payload": payload,
                "previous_sha256": row[1] if row else None,
            }
            digest = sha(canonical(body))
            db.execute(
                "INSERT INTO audit VALUES (?, ?, ?, ?, ?)",
                (
                    body["seq"],
                    kind,
                    json.dumps(payload, sort_keys=True),
                    body["previous_sha256"],
                    digest,
                ),
            )
        return digest

    def discovered(self, event_id):
        return any(
            row["kind"] == "event_discovered" and row["payload"].get("event_id") == event_id
            for row in self.records()
        )


def select_universe(assets, count):
    groups = {}
    for asset in assets:
        groups.setdefault(asset.cik, []).append(asset)
    eligible, excluded = [], []
    for cik, rows in sorted(groups.items()):
        reason = None
        if len({(row.ticker, row.exchange) for row in rows}) != 1:
            reason = "ambiguous_listing"
        elif rows[0].exchange not in EXCHANGES:
            reason = "unsupported_exchange"
        elif rows[0].instrument_type == "fund":
            reason = "fund_name_pattern"
        if reason:
            excluded.append({"cik": cik, "reason": reason})
        else:
            eligible.append(rows[0])
    eligible.sort(key=lambda asset: hashlib.sha256(f"sec-cik:{asset.cik}".encode()).hexdigest())
    selected = eligible[:count]
    excluded.extend(
        {"cik": asset.cik, "reason": "outside_bounded_universe"} for asset in eligible[count:]
    )
    return selected, excluded


def assess_event(event, prices, *, now, benchmark=None):
    published = aware(event["published_at"])
    retrieved = aware(event["retrieved_at"])
    if now.utcoffset() is None:
        raise ValueError("explicit timezone required")
    if published > now or retrieved > now:
        raise ValueError("future event or retrieval timestamp")
    day = published.astimezone(NY).date()
    today = now.astimezone(NY).date()
    reasons = [
        "no_current_executable_quote",
        "fundamental_relevance_unverified",
        "exchange_calendar_unverified",
        "isin_unverified",
        "flatex_unverified",
    ]
    # Without a verified close calendar use completed prior calendar dates only;
    # exclude publication day entirely to avoid claiming a pre-news close was a reaction.
    valid = sorted(
        [row for row in prices if row["date"][:10] < today.isoformat()], key=lambda row: row["date"]
    )
    if len({row["date"][:10] for row in valid}) != len(valid):
        raise ValueError("duplicate price dates")
    for row in valid:
        for field in ("close", "adjClose", "volume"):
            number = Decimal(str(row[field]))
            if not number.is_finite() or number <= 0:
                raise ValueError("invalid prices")
    before = [row for row in valid if row["date"][:10] < day.isoformat()]
    after = [row for row in valid if row["date"][:10] > day.isoformat()]
    reaction = {"status": "unavailable", "basis": "adjusted_eod_excluding_publication_day"}
    status = "BEOBACHTEN"
    if not before:
        reasons.append("pre_publication_price_missing")
    if not after:
        reasons.append("post_publication_price_missing")
    if before and after:
        base, last = before[-1], after[-1]
        change = Decimal(str(last["adjClose"])) / Decimal(str(base["adjClose"])) - 1
        reaction |= {
            "status": "observed_eod",
            "before_date": base["date"],
            "after_date": last["date"],
            "before_adjusted_close": base["adjClose"],
            "after_adjusted_close": last["adjClose"],
            "change": str(change),
            "after_raw_volume": last["volume"],
        }
        if change > Decimal("0.15"):
            status = "ABLEHNEN"
            reasons.append("reaction_already_above_15_percent")
    if not valid:
        status = "NICHT VERFÜGBAR"
        reasons.append("market_data_unavailable")
    if valid and (today - datetime.fromisoformat(valid[-1]["date"][:10]).date()).days > 5:
        reasons.append("stale_eod")
    features = None
    try:

        def feature_rows(rows):
            return [
                {
                    "session_date": row["date"][:10],
                    "raw": {key: row[key] for key in ("open", "high", "low", "close", "volume")},
                    "adjusted": {
                        key: row["adj" + key.title()]
                        for key in ("open", "high", "low", "close", "volume")
                    },
                }
                for row in rows
            ]

        cutoff = datetime.fromisoformat(valid[-1]["date"][:10]).date()
        features = compute_features(feature_rows(valid), signal_date=cutoff)
        if benchmark:
            aligned = [row for row in benchmark if row["date"][:10] <= cutoff.isoformat()]
            if aligned and aligned[-1]["date"][:10] == cutoff.isoformat():
                features = compute_features(
                    feature_rows(valid), signal_date=cutoff, benchmark_bars=feature_rows(aligned)
                )
        if features.median_dollar_volume_20 < Decimal("1000000"):
            status = "ABLEHNEN"
            reasons.append("insufficient_dollar_liquidity")
        features = features.model_dump(mode="json")
        features["momentum_1"] = str(
            Decimal(str(valid[-1]["adjClose"])) / Decimal(str(valid[-2]["adjClose"])) - 1
        )
    except (KeyError, ValueError, IndexError):
        reasons.append("technical_features_incomplete")
    items = {item.strip() for item in event.get("items", "").split(",")}
    if "3.02" in items or event.get("form", "").startswith(("S-", "424B")):
        status = "ABLEHNEN"
        reasons.append("dilution_risk")
    return {
        "event_id": event["event_id"],
        "decided_at": now.isoformat(),
        "strategy": "A",
        "status": status,
        "reasons": sorted(set(reasons)),
        "market_reaction": reaction,
        "features": features,
        "current_price": None,
        "entry_limit": None,
        "stop": None,
        "target_1": None,
        "target_2": None,
        "net_crv": None,
        "valid_until": None,
        "executable": False,
        "flatex_status": "unverified",
        "investment_strategy_status": "not_evaluated",
        "price_scope": "historical_eod_not_realtime",
        "identity": event["identity"],
    }


class BoundedHTTP:
    """One budget/deadline across SEC, documents and Tiingo, including retries."""

    def __init__(self, journal, run_id, *, limit, seconds):
        self.journal, self.run_id = journal, run_id
        self.remaining = limit
        self.deadline = time.monotonic() + seconds
        self.client = httpx.Client(timeout=10, follow_redirects=False)
        self.last = 0.0

    def get(self, url, **kwargs):
        if self.remaining <= 0 or time.monotonic() >= self.deadline:
            raise ValueError("global_request_or_duration_limit")
        time.sleep(max(0, 0.125 - (time.monotonic() - self.last)))
        if time.monotonic() >= self.deadline:
            raise ValueError("duration_limit_before_request")
        self.remaining -= 1
        self.last = time.monotonic()
        started = clock().isoformat()
        recorded = False
        try:
            kwargs["timeout"] = min(10, self.deadline - time.monotonic())
            with self.client.stream("GET", url, **kwargs) as response:
                content = bytearray()
                for chunk in response.iter_bytes():
                    content.extend(chunk)
                    if len(content) > 32 * 1024 * 1024:
                        raise ValueError("response_size_limit")
                    if time.monotonic() >= self.deadline:
                        raise ValueError("duration_limit")
                if time.monotonic() >= self.deadline:
                    raise ValueError("duration_limit")
                result = httpx.Response(
                    response.status_code, content=bytes(content), request=response.request
                )
            self.journal.append(
                "source_attempt",
                {
                    "run_id": self.run_id,
                    "url": url,
                    "started_at": started,
                    "retrieved_at": clock().isoformat(),
                    "http_status": result.status_code,
                    "remaining_requests": self.remaining,
                },
            )
            recorded = True
            if result.status_code in {403, 429}:
                self.remaining = 0
                raise ValueError("source_denied_or_rate_limited_global_stop")
            return result
        except (httpx.HTTPError, ValueError) as exc:
            if not recorded:
                self.journal.append(
                    "source_attempt",
                    {
                        "run_id": self.run_id,
                        "url": url,
                        "started_at": started,
                        "failed_at": clock().isoformat(),
                        "error": _safe_error(exc),
                    },
                )
            raise


def _document(event, submissions, identity, http, folder, user_agent):
    recent = submissions["payload"]["filings"]["recent"]
    index = recent["accessionNumber"].index(event.facts["accession_number"])
    name = recent.get("primaryDocument", [])[index]
    # Never follow document-provided external URLs, redirects or path components.
    if not name or "/" in name or "\\" in name or name in {".", ".."}:
        raise ValueError("unsafe_primary_document")
    accession = event.facts["accession_number"].replace("-", "")
    url = f"https://www.sec.gov/Archives/edgar/data/{int(identity.cik)}/{accession}/{name}"
    response = http.get(url, headers={"User-Agent": user_agent})
    if response.status_code != 200:
        raise ValueError("primary_document_unavailable")
    digest = sha(response.content)
    exclusive(folder / f"raw/{digest}.html", response.content)
    text = response.text.casefold()
    hints = [
        label
        for label, terms in {
            "earnings": ("results of operations", "quarterly results"),
            "acquisition": ("merger agreement", "acquisition agreement"),
            "guidance": ("raises guidance", "raised its guidance"),
            "clinical": ("clinical trial", "fda approval"),
            "contract": ("purchase agreement", "supply agreement"),
            "dilution": ("unregistered sales", "public offering"),
        }.items()
        if any(term in text for term in terms)
    ]
    return {
        "document_status": "archived",
        "document_url": url,
        "document_sha256": digest,
        "document_retrieved_at": clock().isoformat(),
        "text_hints": hints,
        "fundamental_confirmation": "unverified_text_hints_only",
        "financial_quantities": [],
        "counterarguments": ["full_exhibit_review_required"],
    }


def run_scan(
    root,
    *,
    count=100,
    max_requests=150,
    max_seconds=180,
    lookback_hours=72,
    authorize_tiingo=False,
    max_events=10,
):
    if not 100 <= count <= 1000 or not 1 <= max_requests <= 1000:
        raise ValueError("count 100..1000 and requests 1..1000 required")
    if not 1 <= max_seconds <= 300 or not 1 <= lookback_hours <= 168 or not 1 <= max_events <= 100:
        raise ValueError("invalid duration, lookback or event limit")
    required = count + 1 + max_events + (3 * (max_events + 1) if authorize_tiingo else 0)
    if max_requests < required:
        raise ValueError(
            f"request budget must be at least {required} for this universe/event limit"
        )
    root = Path(root)
    root.mkdir(parents=True, exist_ok=True)
    with (root / "scan.lock").open("a") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        journal = Journal(root / "audit.db")
        records = journal.records()
        finished = {
            row["payload"]["run_id"]
            for row in records
            if row["kind"] in {"scan_finished", "scan_interrupted"}
        }
        for row in records:
            if row["kind"] == "scan_started" and row["payload"]["run_id"] not in finished:
                journal.append(
                    "scan_interrupted",
                    {"run_id": row["payload"]["run_id"], "observed_at": clock().isoformat()},
                )
        run_id = uuid.uuid4().hex
        started = clock()
        journal.append(
            "scan_started",
            {
                "run_id": run_id,
                "at": started.isoformat(),
                "universe_requested": count,
                "max_requests": max_requests,
                "max_seconds": max_seconds,
                "lookback_hours": lookback_hours,
                "max_events": max_events,
                "additional_cost_eur": 0,
            },
        )
        http = BoundedHTTP(journal, run_id, limit=max_requests, seconds=max_seconds)
        summary = {
            "run_id": run_id,
            "status": "partial",
            "new_events": 0,
            "evaluated_events": 0,
            "checked_issuers": 0,
            "buy_signals": 0,
            "uncovered_markets": ["DE", "AT", "CH"],
            "errors": [],
        }
        folder = root / "runs" / run_id
        try:
            ua = os.getenv("SEC_USER_AGENT", "")
            if "@" not in ua:
                raise ValueError("SEC_USER_AGENT_with_contact_email_required")
            sec = SecEdgarClient(
                folder / "sec",
                user_agent=ua,
                allow_network=True,
                max_requests=max_requests,
                client=http,
                now=clock,
            )
            universe_record = sec.fetch("universe")
            selected, excluded = select_universe(normalize_universe(universe_record), count)
            journal.append(
                "universe",
                {
                    "run_id": run_id,
                    "retrieved_at": universe_record["retrieved_at"],
                    "source_sha256": universe_record["raw_sha256"],
                    "selected": [asset.model_dump(mode="json") for asset in selected],
                    "excluded": excluded,
                    "selection": "stable_sha256_cik_v1",
                    "sector_coverage": "not_verified",
                    "actual_count": len(selected),
                },
            )
            if len(selected) < 100:
                raise ValueError("fewer_than_100_unambiguous_listings")
            benchmark = None
            tiingo = TiingoClient(
                folder / "tiingo",
                allow_network=True,
                authorize_usage=authorize_tiingo,
                max_requests=max_requests,
                monthly_cost_eur="0",
                client=http,
            )

            price_cache = {}

            def prices(symbol):
                if symbol in price_cache:
                    return price_cache[symbol]
                if http.remaining <= 0 or time.monotonic() >= http.deadline:
                    raise ValueError("global_request_or_duration_limit")
                if not authorize_tiingo or not os.getenv("TIINGO_API_TOKEN"):
                    raise ValueError("TIINGO_API_TOKEN_and_usage_authorization_required")
                TiingoQuotaLedger(root / "tiingo-quota.jsonl").reserve(
                    symbols=[symbol], max_requests=3, at=clock()
                )
                record = tiingo.fetch(
                    symbol,
                    start=(started - timedelta(days=400)).date().isoformat(),
                    end=(started - timedelta(days=1)).date().isoformat(),
                )
                journal.append(
                    "market_data",
                    {
                        "run_id": run_id,
                        "symbol": symbol,
                        "retrieved_at": record["retrieved_at"],
                        "raw_sha256": record["raw_sha256"],
                        "source_reference": record["source_reference"],
                        "scope": "EOD_only",
                    },
                )
                price_cache[symbol] = record["payload"]
                return price_cache[symbol]

            if authorize_tiingo:
                try:
                    benchmark = prices("SPY")
                except (ValueError, httpx.HTTPError) as exc:
                    journal.append(
                        "data_unavailable",
                        {"run_id": run_id, "symbol": "SPY", "error": _safe_error(exc)},
                    )
            pending = []
            known = {
                row["payload"].get("event_id")
                for row in journal.records()
                if row["kind"] == "event_discovered"
            }
            # Resume after the last attempted issuer on interrupted passes.
            attempted = [
                row["payload"].get("cik")
                for row in journal.records()
                if row["kind"] in {"issuer_checked", "issuer_error"}
            ]
            order = selected
            if attempted:
                positions = {asset.cik: index for index, asset in enumerate(selected)}
                offset = positions.get(attempted[-1], -1) + 1
                order = selected[offset:] + selected[:offset]
            for identity in order:
                if http.remaining <= 0 or time.monotonic() >= http.deadline:
                    summary["errors"].append("global_request_or_duration_limit")
                    break
                try:
                    submissions = sec.fetch("submissions", identity.cik)
                    events = normalize_submission_events(submissions, identity)
                    summary["checked_issuers"] += 1
                    journal.append(
                        "issuer_checked",
                        {
                            "run_id": run_id,
                            "cik": identity.cik,
                            "ticker": identity.ticker,
                            "at": clock().isoformat(),
                            "submissions_sha256": submissions["raw_sha256"],
                            "filings_in_response": len(events),
                        },
                    )
                    exclusions = []
                    for event in events:
                        reason = None
                        if event.published_at > clock():
                            reason = "future_publication"
                        elif event.published_at < started - timedelta(hours=lookback_hours):
                            reason = "outside_recent_window"
                        elif event.facts["form"] not in {
                            "8-K",
                            "6-K",
                            "10-Q",
                            "10-K",
                            "S-1",
                            "S-3",
                            "424B5",
                            "4",
                        }:
                            reason = "form_outside_pilot"
                        if reason:
                            exclusions.append(
                                {
                                    "event_id": event.event_id,
                                    "published_at": event.published_at.isoformat(),
                                    "reason": reason,
                                }
                            )
                            continue
                        value = {
                            "event_id": event.event_id,
                            "run_id": run_id,
                            "published_at": event.published_at.isoformat(),
                            "publication_basis": "SEC_acceptance_not_earliest_issuer_release",
                            "retrieved_at": event.retrieved_at.isoformat(),
                            "source_url": event.evidence.url,
                            **event.facts,
                            "identity": identity.model_dump(mode="json"),
                            "first_realistic_trade_at": None,
                            "trade_time_status": "calendar_and_original_release_unverified",
                        }
                        is_new = event.event_id not in known
                        if is_new:
                            journal.append("event_discovered", value)
                            known.add(event.event_id)
                            summary["new_events"] += 1
                        value["new_to_scanner"] = is_new
                        pending.append((is_new, event, submissions, identity, value))
                    journal.append(
                        "events_excluded",
                        {
                            "run_id": run_id,
                            "cik": identity.cik,
                            "at": clock().isoformat(),
                            "events": exclusions,
                        },
                    )
                except (ValueError, httpx.HTTPError, KeyError, TypeError) as exc:
                    journal.append(
                        "issuer_error",
                        {
                            "run_id": run_id,
                            "cik": identity.cik,
                            "ticker": identity.ticker,
                            "at": clock().isoformat(),
                            "error": _safe_error(exc),
                        },
                    )
                    summary["errors"].append(f"issuer:{identity.cik}:{_safe_error(exc)}")
            # New discoveries first, then least recently evaluated events. This prevents
            # the first few issuers consuming every scan's event budget forever.
            evaluated = {
                row["payload"].get("event_id"): row["seq"]
                for row in journal.records()
                if row["kind"] == "decision"
            }
            pending.sort(
                key=lambda item: (
                    not item[0],
                    evaluated.get(item[1].event_id, 0),
                    -item[1].published_at.timestamp(),
                )
            )
            for index, (is_new, event, submissions, identity, value) in enumerate(pending):
                if index >= max_events:
                    journal.append(
                        "event_deferred",
                        {
                            "run_id": run_id,
                            "event_id": event.event_id,
                            "at": clock().isoformat(),
                            "reason": "event_budget_exhausted",
                        },
                    )
                    continue
                try:
                    value |= _document(event, submissions, identity, http, folder, ua)
                except (ValueError, httpx.HTTPError, IndexError) as exc:
                    value |= {"document_status": "unavailable", "error": _safe_error(exc)}
                journal.append("event_evidence", value)
                market = []
                try:
                    market = prices(identity.ticker)
                except (ValueError, httpx.HTTPError) as exc:
                    journal.append(
                        "data_unavailable",
                        {
                            "run_id": run_id,
                            "event_id": event.event_id,
                            "error": _safe_error(exc),
                        },
                    )
                try:
                    decision = assess_event(value, market, now=clock(), benchmark=benchmark)
                except (KeyError, TypeError, ValueError, InvalidOperation):
                    decision = assess_event(value, [], now=clock())
                    decision["reasons"].append("invalid_market_data")
                    journal.append(
                        "data_unavailable",
                        {
                            "run_id": run_id,
                            "event_id": event.event_id,
                            "error": "invalid_market_data",
                            "at": clock().isoformat(),
                        },
                    )
                journal.append(
                    "decision",
                    decision
                    | {
                        "run_id": run_id,
                        "new_to_scanner": is_new,
                        "event_evidence_sha256": sha(canonical(value)),
                    },
                )
                summary["evaluated_events"] += 1
            if summary["checked_issuers"] == len(selected) and not summary["errors"]:
                summary["status"] = "completed"
        except (ValueError, httpx.HTTPError, KeyError, TypeError) as exc:
            summary["status"] = "blocked"
            summary["errors"].append(_safe_error(exc))
        finally:
            http.client.close()
            summary["finished_at"] = clock().isoformat()
            journal.verify()
            journal.append("scan_finished", summary)
        return summary


def _safe_error(exc):
    # Never record provider response bodies, request headers or credential-bearing exceptions.
    return str(exc) if isinstance(exc, ValueError) and len(str(exc)) < 160 else type(exc).__name__


def create_app():
    """Local, read-only pilot API; mount audit storage read-only in its container."""
    from fastapi import FastAPI, HTTPException, Query

    app = FastAPI(title="Scanner V2.7 pilot — EOD research")

    def journal():
        try:
            return Journal(
                Path(os.getenv("LIVE_PILOT_ROOT", "/data/live-v27")) / "audit.db", read_only=True
            )
        except (ValueError, sqlite3.Error):
            raise HTTPException(503, "audit_unavailable_or_integrity_failure") from None

    @app.get("/health")
    def health():
        audit = journal()
        return {"verified_rows": audit.verify(), "executable_buy_support": False}

    @app.get("/decisions")
    def decisions(limit: int = Query(50, ge=1, le=500)):
        return {
            "records": [row for row in journal().records() if row["kind"] == "decision"][-limit:]
        }

    @app.get("/scans")
    def scans(limit: int = Query(20, ge=1, le=100)):
        kinds = {"scan_started", "scan_finished", "scan_interrupted"}
        return {"records": [row for row in journal().records() if row["kind"] in kinds][-limit:]}

    return app


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=["scan", "watch", "export", "verify"])
    parser.add_argument("--root", default="/data/live-v27")
    parser.add_argument("--count", type=int, default=100)
    parser.add_argument("--max-requests", type=int, default=150)
    parser.add_argument("--max-seconds", type=int, default=180)
    parser.add_argument("--max-events", type=int, default=10)
    parser.add_argument("--lookback-hours", type=int, default=72)
    parser.add_argument("--interval-seconds", type=int, default=900)
    parser.add_argument("--authorize-tiingo", action="store_true")
    args = parser.parse_args(argv)
    if args.command in {"export", "verify"}:
        journal = Journal(Path(args.root) / "audit.db", read_only=True)
        result = (
            journal.records() if args.command == "export" else {"verified_rows": journal.verify()}
        )
        print(json.dumps(result, ensure_ascii=False))
        return 0
    if args.interval_seconds < 300:
        parser.error("minimum polling interval is 300 seconds")
    while True:
        result = run_scan(
            args.root,
            count=args.count,
            max_requests=args.max_requests,
            max_seconds=args.max_seconds,
            lookback_hours=args.lookback_hours,
            authorize_tiingo=args.authorize_tiingo,
            max_events=args.max_events,
        )
        print(json.dumps(result, ensure_ascii=False), flush=True)
        if args.command == "scan":
            return 0 if result["status"] == "completed" else 2
        # Short waits permit clean container shutdown and keep polling bounded.
        for _ in range(args.interval_seconds):
            time.sleep(1)


if __name__ == "__main__":
    raise SystemExit(main())
