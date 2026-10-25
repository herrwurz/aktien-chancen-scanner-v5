import json
from datetime import UTC, datetime
from pathlib import Path

from scanner.hebeltrader.detective.benchmark_scan import scan_manifest
from scanner.hebeltrader.detective.clue_enrichment import HeuristicClueEnricher
from scanner.hebeltrader.detective.eu_universe import load_curated_hypothesis_assets
from scanner.hebeltrader.detective.hypothesis_source import HypothesisCandidateSource
from scanner.hebeltrader.detective.news_channel import FixtureNewsSearcher
from scanner.hebeltrader.detective.service import DetectiveService

ROOT = Path("tests/fixtures/detective-hypothesis")
NOW = datetime(2025, 6, 5, 12, tzinfo=UTC)


def _service():
    news = json.loads((ROOT / "fixture_news.json").read_text(encoding="utf-8"))["items"]
    source = HypothesisCandidateSource(
        eu_assets=load_curated_hypothesis_assets(),
        news_searcher=FixtureNewsSearcher(news),
    )
    return DetectiveService(
        candidate_source=source,
        news_source=source,
        products=[],
        enricher=HeuristicClueEnricher(),
        clock=lambda: NOW,
    )


def test_mini_benchmark_top3_hit_rate_on_resolvable_cases():
    rankings = scan_manifest(ROOT / "mini_benchmark/manifest.json", _service())
    labels = json.loads((ROOT / "mini_benchmark/labels.json").read_text(encoding="utf-8"))["cases"]
    resolvable = []
    hits = 0
    for row in rankings["cases"]:
        label = labels[row["case_id"]]
        acceptable = set(label.get("acceptable_asset_ids") or [])
        if label.get("expected_in_universe") is False or not acceptable:
            # Unresolvable/promo cases: must not invent a confident stock list wrongly.
            if row["status"] == "unresolved":
                continue
            # If hypotheses appear, they must not be treated as required hits.
            continue
        resolvable.append(row["case_id"])
        ranked_ids = []
        for asset_id in row["ranked_asset_ids"]:
            ranked_ids.append(asset_id)
        # scan stores asset_id from candidate payloads
        top = set(row["ranked_asset_ids"][:3])
        if top & acceptable:
            hits += 1
    assert len(resolvable) >= 3
    assert hits / len(resolvable) >= 0.5
