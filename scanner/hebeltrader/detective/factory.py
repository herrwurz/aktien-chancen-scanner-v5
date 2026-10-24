"""Configured detective construction; live sources remain lazy at API startup."""

import hmac
from datetime import UTC, datetime
from threading import Lock

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
    investigated = len(snapshot["assets"])
    universe_size = coverage.get("unique_issuer_total", investigated)
    sector_count = sum(asset.sector is not None for asset in snapshot["assets"])
    metric_issuers = {fact.asset.cik for fact in snapshot["facts"]}
    if coverage.get("candidate_selection") == "stable_sha256_cik_v1":
        coverage.update(
            sampling_strategy="stable_sha256_cik_v1",
            search_scope="independent_sample_not_global_candidate_search",
            full_universe_size=universe_size,
            listing_count=coverage.get("universe_total"),
            investigated_count=investigated,
            coverage_ratio=investigated / universe_size if universe_size else 0.0,
            sector_available_count=sector_count,
            missing_sector_rate=1 - sector_count / investigated if investigated else 1.0,
            company_metrics_available_count=len(metric_issuers),
            company_metrics_coverage_ratio=(
                len(metric_issuers) / investigated if investigated else 0.0
            ),
            recall_unmeasurable=True,
            not_covered_markets=["non_SEC_US", "DE", "AT", "CH", "EU"],
        )
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

    def __init__(self, client, snapshot_path, max_candidates, max_duration_seconds):
        self.client = client
        self.snapshot_path = snapshot_path
        self.max_candidates = max_candidates
        self.max_duration_seconds = max_duration_seconds
        self.delegate = None
        self._lock = Lock()
        self.coverage = {
            "status": "not_started",
            "kind": "real_research",
            "real_market_data": False,
            "candidate_count": 0,
        }

    def _ensure(self):
        if self.delegate is not None:
            return
        with self._lock:
            if self.delegate is not None:
                return
            try:
                collect_sec_snapshot(
                    self.client,
                    self.snapshot_path,
                    max_candidates=self.max_candidates,
                    max_duration_seconds=self.max_duration_seconds,
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


def live_api_access_status(settings, provided_token):
    if settings.detective_research_mode != "live_research":
        return "not_required"
    configured = settings.detective_live_api_token
    if configured is None:
        return "token_missing"
    expected = configured.get_secret_value()
    if not provided_token or not hmac.compare_digest(expected, provided_token):
        return "unauthorized"
    return "authorized"


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
    elif settings.detective_live_max_requests < 1 + 2 * settings.detective_live_max_candidates:
        source = UnavailableResearchSource("live_request_budget_insufficient")
    else:
        client = sec_client or SecEdgarClient(
            settings.detective_research_cache_dir,
            user_agent=settings.sec_user_agent,
            allow_network=True,
            max_requests=settings.detective_live_max_requests,
            request_timeout_seconds=settings.detective_live_request_timeout_seconds,
        )
        source = LazyLiveResearchSource(
            client,
            settings.detective_research_snapshot,
            settings.detective_live_max_candidates,
            settings.detective_live_max_duration_seconds,
        )
    return DetectiveService(
        candidate_source=source,
        news_source=source,
        products=load_products(),
        clock=clock,
        research_mode=mode,
    )
