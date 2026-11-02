"""Operator live Stufe-3b path (Tavily + optional OpenAI).

Unlike ``simulated_falsification``, this hits real providers. Cost approval is
mandatory. Do not pass ``documents`` into ``analyze()`` — packets force the
offline/historical path and skip live falsification.

Env (either naming works):

- Search: ``DETECTIVE_SEARCH_API_KEY`` or ``TAVILY_API_KEY``
- AI (optional): ``DETECTIVE_SOURCE_AI_API_KEY`` or ``OPENAI_API_KEY``
- Approval: ``DETECTIVE_EXTERNAL_API_APPROVED=true`` or ``--approve-cost``
"""

from __future__ import annotations

import argparse
import json
import os
from datetime import UTC, datetime
from pathlib import Path

from pydantic import SecretStr

from scanner.config import Settings

from .api_budget import ApiBudget
from .external_research import ApiConfigurationError, ApiPublicResearch, ResearchApis
from .investigation import InvestigationRequest, Investigator


def _secret(primary: str, *aliases: str) -> str | None:
    for name in (primary, *aliases):
        value = os.environ.get(name, "").strip()
        if value:
            return value
    return None


def build_live_web(root: Path, *, approved: bool, max_requests: int = 40):
    """Build ApiPublicResearch from process env; never logs credential values."""
    if not approved:
        raise ApiConfigurationError("External API cost approval is required")
    search_key = _secret("DETECTIVE_SEARCH_API_KEY", "TAVILY_API_KEY")
    if not search_key:
        raise ApiConfigurationError("Tavily search API credential is missing")
    ai_key = _secret("DETECTIVE_SOURCE_AI_API_KEY", "OPENAI_API_KEY")
    source_ai = bool(ai_key) and os.environ.get("DETECTIVE_SOURCE_AI_ENABLED", "true").lower() in (
        "1",
        "true",
        "yes",
    )
    if source_ai and not ai_key:
        raise ApiConfigurationError("OpenAI source API credential is missing")
    settings = Settings(
        detective_public_root=root,
        detective_public_allow_network=True,
        detective_public_max_requests=max_requests,
        detective_search_provider="tavily",
        detective_search_api_key=SecretStr(search_key),
        detective_source_ai_enabled=source_ai,
        detective_source_ai_api_key=SecretStr(ai_key) if ai_key else None,
        detective_external_api_approved=True,
    )
    api = ResearchApis(
        root=root / "api-audit",
        budget=ApiBudget(
            root / "api-budget.db", cap_cents=settings.detective_api_monthly_budget_eur * 100
        ),
        approved=True,
        search_key=search_key,
        ai_key=ai_key if source_ai else None,
        extraction_model=settings.detective_extraction_model,
        reasoning_model=settings.detective_reasoning_model,
    )
    return ApiPublicResearch(
        root / "sources",
        apis=api,
        allow_network=True,
        max_requests=max_requests,
        primary_domains={},
        discovery_feeds=settings.detective_discovery_feeds,
    )


def run_live_falsification(
    root: Path,
    *,
    teaser_text: str,
    publication_at: datetime | None = None,
    approved: bool = False,
    max_requests: int = 40,
) -> dict:
    """Live Investigator run; returns report with basis=live_falsification when gates pass."""
    publication_at = publication_at or datetime.now(UTC)
    web = build_live_web(root, approved=approved, max_requests=max_requests)
    report = Investigator(root, clock=lambda: publication_at, web=web).analyze(
        InvestigationRequest(teaser_text=teaser_text, publication_at=publication_at)
    )
    apis = getattr(web, "apis", None)
    report["_harness"] = {
        "kind": "live_falsification_v1",
        "approved": True,
        "search_configured": True,
        "ai_configured": bool(getattr(apis, "ai_key", None)),
        "note": (
            "Live network. Documents must not be passed to analyze(); packets force "
            "historical_source_packet / offline falsification skip."
        ),
    }
    return report


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path("/tmp/ht-live-3b"))
    parser.add_argument("--text-file", type=Path, required=True)
    parser.add_argument("--publication-at")
    parser.add_argument("--max-requests", type=int, default=40)
    parser.add_argument(
        "--approve-cost",
        action="store_true",
        help="One-shot cost approval (or set DETECTIVE_EXTERNAL_API_APPROVED)",
    )
    args = parser.parse_args(argv)
    if not 1 <= args.max_requests <= 100:
        parser.error("--max-requests must be 1..100")
    approved = args.approve_cost or os.environ.get(
        "DETECTIVE_EXTERNAL_API_APPROVED", ""
    ).strip().lower() in ("1", "true", "yes")
    publication_at = (
        datetime.fromisoformat(args.publication_at) if args.publication_at else datetime.now(UTC)
    )
    try:
        report = run_live_falsification(
            args.root,
            teaser_text=args.text_file.read_text(encoding="utf-8"),
            publication_at=publication_at,
            approved=approved,
            max_requests=args.max_requests,
        )
    except ApiConfigurationError as exc:
        print(json.dumps({"status": "blocked", "error": str(exc)}, ensure_ascii=False, indent=2))
        return 2
    print(json.dumps(report, ensure_ascii=False, indent=2, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
