"""Opt-in public teaser polling and local notification outbox, never orders."""

import fcntl
import json
import sqlite3
from datetime import UTC, datetime
from pathlib import Path
from urllib.parse import urlsplit, urlunsplit

import httpx

from scanner.hebeltrader.eodhd import canonical, exclusive, sha

from .investigation import InvestigationRequest

DEFAULT_QUERY = 'site:deraktionaer.de "HEBELTRADER" "bis zu"'


class TeaserMonitor:
    def __init__(self, root, *, web, engine, clock=None, queries=None, recheck_seconds=86400):
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)
        self.web, self.engine = web, engine
        self.clock = clock or (lambda: datetime.now(UTC))
        self.queries = queries or [DEFAULT_QUERY]
        self.recheck_seconds = max(300, recheck_seconds)
        self.path = self.root / "teasers.db"
        with sqlite3.connect(self.path) as db:
            db.executescript("""
                CREATE TABLE IF NOT EXISTS teasers (
                    id TEXT PRIMARY KEY, url TEXT NOT NULL, best_score INTEGER NOT NULL,
                    identified INTEGER NOT NULL, analyzed_at TEXT NOT NULL,
                    latest_report TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS notifications (
                    seq INTEGER PRIMARY KEY, teaser_id TEXT NOT NULL, created_at TEXT NOT NULL,
                    kind TEXT NOT NULL, payload TEXT NOT NULL);
            """)

    def notifications(self):
        with sqlite3.connect(self.path) as db:
            return [
                {
                    "seq": row[0],
                    "teaser_id": row[1],
                    "created_at": row[2],
                    "kind": row[3],
                    "payload": json.loads(row[4]),
                }
                for row in db.execute("SELECT * FROM notifications ORDER BY seq")
            ]

    def scan_once(self, *, force_recheck=False):
        with (self.root / "monitor.lock").open("a") as lock:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
            now = self.clock()
            outcome = {
                "scanned_at": now.isoformat(),
                "new_teasers": 0,
                "improved_identifications": 0,
                "analyzed": 0,
                "duplicate_or_unchanged": 0,
                "errors": [],
                "notification_delivery": "local_outbox_only",
            }
            urls = {}
            for query in self.queries[:4]:
                try:
                    for hit in self.web.search(query, limit=20):
                        urls[hit["url"]] = hit
                except (ValueError, httpx.HTTPError) as exc:
                    outcome["errors"].append(type(exc).__name__)
            for url in list(urls)[:20]:
                try:
                    document = self.web.fetch(url)
                    text = document.get("text", "")
                    import re

                    title = document.get("title", "")
                    if not (
                        re.search(
                            r"dieser|dieses|diese|aktie|titel|unbekannt|\w*(?:konzern|gigant|riese|schwergewicht)",
                            title,
                            re.I,
                        )
                        and re.search(r"hebeltrader", text, re.I)
                        and re.search(r"\bbis zu\b", text, re.I)
                        and re.search(r"prozent|%", text, re.I)
                    ):
                        continue
                    parsed = urlsplit(url)
                    canonical_url = urlunsplit(
                        (parsed.scheme, parsed.netloc, parsed.path, parsed.query, "")
                    )
                    teaser_id = sha(
                        canonical(
                            {"url": canonical_url, "publication": document.get("published_at")}
                        )
                    )
                    exclusive(
                        self.root / "teasers" / teaser_id / f"{sha(canonical(document))}.json",
                        canonical(document),
                    )
                    if len(text) > 20000:
                        outcome["errors"].append("teaser_text_exceeds_input_limit")
                        continue
                    with sqlite3.connect(self.path) as db:
                        old = db.execute(
                            "SELECT best_score,identified,analyzed_at FROM teasers WHERE id=?",
                            (teaser_id,),
                        ).fetchone()
                    if (
                        old
                        and not force_recheck
                        and (now - datetime.fromisoformat(old[2])).total_seconds()
                        < self.recheck_seconds
                    ):
                        outcome["duplicate_or_unchanged"] += 1
                        continue
                    request = InvestigationRequest(
                        teaser_text=text,
                        teaser_url=None,
                        headline=document.get("title", ""),
                        publisher=parsed.hostname or "",
                        publication_at=document.get("published_at"),
                    )
                    report = self.engine.analyze(request)
                    outcome["analyzed"] += 1
                    lead = (report.get("candidates") or [{}])[0]
                    score = int(lead.get("evidence_score", 0))
                    identified = report["identification"]["status"] == "identified"
                    material = bool(
                        old
                        and (
                            (identified and not old[1])
                            or (
                                score >= old[0] + 35
                                and len(lead.get("confirmed_specific_clues", [])) >= 2
                                and not lead.get("hard_contradictions")
                            )
                        )
                    )
                    kind = (
                        "new_teaser"
                        if old is None
                        else "identification_improved"
                        if material
                        else None
                    )
                    with sqlite3.connect(self.path) as db:
                        db.execute(
                            "INSERT OR REPLACE INTO teasers VALUES (?,?,?,?,?,?)",
                            (
                                teaser_id,
                                canonical_url,
                                max(score, old[0]) if old else score,
                                max(int(identified), old[1]) if old else int(identified),
                                now.isoformat(),
                                json.dumps(report, ensure_ascii=False),
                            ),
                        )
                        if kind:
                            db.execute(
                                "INSERT INTO notifications(teaser_id,created_at,kind,payload) "
                                "VALUES (?,?,?,?)",
                                (
                                    teaser_id,
                                    now.isoformat(),
                                    kind,
                                    json.dumps(report, ensure_ascii=False),
                                ),
                            )
                    outcome["new_teasers"] += old is None
                    outcome["improved_identifications"] += bool(material)
                except (ValueError, httpx.HTTPError) as exc:
                    outcome["errors"].append({"url": url, "error": type(exc).__name__})
            exclusive(self.root / "polls" / f"{sha(canonical(outcome))}.json", canonical(outcome))
            return outcome


def notification_feed(root, limit=20):
    """Read-only local notification outbox; no state creation on API reads."""
    path = (Path(root) / "teasers.db").resolve()
    if not path.is_file():
        return []
    with sqlite3.connect(path.as_uri() + "?mode=ro", uri=True) as db:
        rows = db.execute(
            "SELECT * FROM notifications ORDER BY seq DESC LIMIT ?", (max(1, min(100, limit)),)
        ).fetchall()
    return [
        {
            "seq": row[0],
            "teaser_id": row[1],
            "created_at": row[2],
            "kind": row[3],
            "payload": json.loads(row[4]),
        }
        for row in rows
    ]
