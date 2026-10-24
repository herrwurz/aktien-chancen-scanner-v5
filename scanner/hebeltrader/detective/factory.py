"""Configured detective construction; live sources remain lazy at API startup."""

from datetime import UTC, datetime

from scanner.hebeltrader.detective.catalog import default_candidate_source, load_products
from scanner.hebeltrader.detective.research_source import ResearchCandidateSource
from scanner.hebeltrader.detective.service import DetectiveService
from scanner.hebeltrader.detective.sources import UnavailableResearchSource
from scanner.research_live import collect_sec_snapshot
from scanner.research_providers.sec_edgar import SecEdgarClient
from scanner.research_snapshot import load_snapshot


def _cached_source(path, *, now=None):
    now = now or datetime.now(UTC)
    try:
        snapshot = load_snapshot(path)
    except (OSError, ValueError, KeyError, TypeError):
        return UnavailableResearchSource("cached_snapshot_unavailable_or_invalid")
    generated = datetime.fromisoformat(snapshot["generated_at"])
    coverage = dict(snapshot["coverage"])
    coverage.update(
        status="partial" if coverage.get("errors") else "ok",
        real_market_data=coverage.get("kind") == "real_archived",
        candidate_count=len(snapshot["assets"]),
        data_age_seconds=max(0, int((now - generated).total_seconds())),
        generated_at=generated.isoformat(),
    )
    return ResearchCandidateSource(
        snapshot["assets"], snapshot["events"], facts=snapshot["facts"], coverage=coverage
    )


class LazyLiveResearchSource:
    source_id = "sec-live-bounded-snapshot"

    def __init__(self, client, snapshot_path, max_candidates):
        self.client = client
        self.snapshot_path = snapshot_path
        self.max_candidates = max_candidates
        self.delegate = None
        self.coverage = {
            "status": "not_started",
            "kind": "real_research",
            "real_market_data": False,
            "candidate_count": 0,
        }

    def _ensure(self):
        if self.delegate is not None:
            return
        try:
            collect_sec_snapshot(
                self.client, self.snapshot_path, max_candidates=self.max_candidates
            )
            self.delegate = _cached_source(self.snapshot_path, now=self.client.now())
        except (OSError, ValueError, KeyError, TypeError) as exc:
            self.delegate = UnavailableResearchSource(type(exc).__name__)
        self.coverage = self.delegate.coverage

    def load_candidates(self):
        self._ensure()
        return self.delegate.load_candidates()

    def evidence_for(self, identity):
        self._ensure()
        return self.delegate.evidence_for(identity)


def build_detective(settings, *, clock=None, sec_client=None):
    mode = settings.detective_research_mode
    if mode == "fixture":
        source = default_candidate_source()
    elif mode == "cached_research":
        source = _cached_source(settings.detective_research_snapshot)
    elif not (
        settings.detective_live_allow_network
        and settings.detective_live_max_requests > 0
        and settings.sec_user_agent
        and "@" in settings.sec_user_agent
    ):
        source = UnavailableResearchSource("live_not_authorized")
    else:
        client = sec_client or SecEdgarClient(
            settings.detective_research_cache_dir,
            user_agent=settings.sec_user_agent,
            allow_network=True,
            max_requests=settings.detective_live_max_requests,
        )
        source = LazyLiveResearchSource(
            client,
            settings.detective_research_snapshot,
            settings.detective_live_max_candidates,
        )
    return DetectiveService(
        candidate_source=source,
        news_source=source,
        products=load_products(),
        clock=clock,
        research_mode=mode,
    )
