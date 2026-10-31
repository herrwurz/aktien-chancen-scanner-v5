"""Fixture-backed Stufe-3b harness (no Tavily / OpenAI / live network).

Live identification (``basis=live_falsification``) requires a web research object
and **no** pre-mounted ``documents`` (packets force the offline/historical path).
This module provides a deterministic ``SimulatedWeb`` that searches/fetches a
fixed peer packet so CI can exercise the 3b gates without API keys.

Operator path when keys arrive: replace ``SimulatedWeb`` with real
``PublicWebResearch`` / ``ApiPublicResearch``; keep the same Investigator call.
"""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

from .investigation import InvestigationRequest, Investigator


class SimulatedWeb:
    """Minimal web stub: search returns packet URLs; fetch returns the matching doc."""

    def __init__(self, docs: list[dict]):
        self.docs = list(docs)
        self.queries: list[str] = []

    def search(self, query, limit=10):
        self.queries.append(query)
        return [{"url": doc["url"]} for doc in self.docs[:limit]]

    def fetch(self, url):
        for doc in self.docs:
            if doc["url"] == url:
                return doc
        raise KeyError(url)


def acquisition_peer_packet(*, now: datetime | None = None) -> list[dict]:
    """Six peer issuers; lead (#5) uniquely owns AlphaPower+BetaLogic acquisitions."""
    now = now or datetime(2026, 10, 28, 12, tzinfo=UTC)
    docs = []
    for index in range(6):
        company = f"Company {index}"
        text = (
            f"{company} acquired AlphaPower and BetaLogic."
            if index == 5
            else (
                f"{company} develops chips and artificial intelligence, "
                "and discusses AlphaPower and BetaLogic."
            )
        )
        docs.append(
            {
                "company_name": company,
                "ticker": f"C{index}",
                "url": f"https://issuer{index}.example/release",
                "title": company + " company release",
                "text": text,
                "source_kind": "issuer",
                "published_at": "2026-10-25T12:00:00+00:00",
                "retrieved_at": now.isoformat(),
            }
        )
    return docs


def run_simulated_live_falsification(
    root: Path,
    *,
    teaser_text: str = "Übernahmen von AlphaPower und BetaLogic.",
    publication_at: datetime | None = None,
    docs: list[dict] | None = None,
) -> dict:
    """Run Investigator on SimulatedWeb; returns report with basis=live_falsification."""
    publication_at = publication_at or datetime(2026, 10, 28, 12, tzinfo=UTC)
    docs = docs if docs is not None else acquisition_peer_packet(now=publication_at)
    web = SimulatedWeb(docs)
    report = Investigator(root, clock=lambda: publication_at, web=web).analyze(
        InvestigationRequest(teaser_text=teaser_text, publication_at=publication_at)
    )
    report["_harness"] = {
        "kind": "simulated_live_falsification_v1",
        "queries": list(web.queries),
        "note": (
            "No network. Documents must not be passed to analyze(); packets force "
            "historical_source_packet / offline falsification skip."
        ),
    }
    return report
