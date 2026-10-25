"""Curated operating-company universes for hypothesis retrieval (EU/DACH + US seed)."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

from pydantic import ValidationError

from scanner.research import AssetIdentity
from scanner.research_index.builder import build_index
from scanner.research_index.identity import stable_asset_id

from .geo import country_matches

DEFAULT_AS_OF = datetime(2024, 1, 1, 12, tzinfo=UTC)
PACKAGE_DIR = Path(__file__).resolve().parent
TEST_DIR = Path(__file__).resolve().parents[3] / "tests/fixtures/detective-hypothesis"
PACKAGE_DATA = PACKAGE_DIR / "eu_dach_universe.json"
TEST_FIXTURE = TEST_DIR / "eu_dach_universe.json"
PACKAGE_FIXTURE = PACKAGE_DATA if PACKAGE_DATA.is_file() else TEST_FIXTURE
US_PACKAGE_DATA = PACKAGE_DIR / "us_seed_universe.json"
US_TEST_FIXTURE = TEST_DIR / "us_seed_universe.json"
US_PACKAGE_FIXTURE = US_PACKAGE_DATA if US_PACKAGE_DATA.is_file() else US_TEST_FIXTURE


def _load_curated_assets(
    path: Path,
    *,
    source_id: str,
    default_available_at: datetime = DEFAULT_AS_OF,
) -> list[AssetIdentity]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    assets = []
    for row in payload["assets"]:
        values = dict(row)
        values.setdefault("asset_type", "stock")
        values.setdefault("instrument_type", "operating_company")
        values.setdefault("instrument_type_status", "source_verified")
        values.setdefault("source_id", source_id)
        values.setdefault("source_available_at", default_available_at.isoformat())
        values.setdefault("retrieved_at", values.get("source_available_at"))
        assets.append(AssetIdentity.model_validate(values))
    return assets


def load_eu_dach_assets(path: Path | None = None) -> list[AssetIdentity]:
    return _load_curated_assets(
        path or PACKAGE_FIXTURE,
        source_id="eu-dach-curated-v1",
    )


def load_us_seed_assets(path: Path | None = None) -> list[AssetIdentity]:
    """Small US seed for hypothesis tests (JNJ/JPM/COST + sector peers)."""
    return _load_curated_assets(
        path or US_PACKAGE_FIXTURE,
        source_id="us-seed-curated-v1",
        default_available_at=datetime(2020, 1, 2, 12, tzinfo=UTC),
    )


def load_curated_hypothesis_assets(
    *,
    eu_path: Path | None = None,
    us_path: Path | None = None,
) -> list[AssetIdentity]:
    return merge_universes(load_eu_dach_assets(eu_path), load_us_seed_assets(us_path))


def load_openfigi_identity_records(path: Path) -> list[AssetIdentity]:
    """Load previously collected OpenFIGI identity JSON into AssetIdentity rows.

    Expects the offline collector shape used by hebeltrader identity assistants:
    ``{"records":[{"query_wkn":..., "candidates":[{"name","ticker","isin","exchange",...}]}]}``.
    """
    payload = json.loads(path.read_text(encoding="utf-8"))
    assets = []
    for record in payload.get("records", []):
        wkn = record.get("query_wkn")
        for candidate in record.get("candidates", []):
            name = candidate.get("name") or candidate.get("security_name")
            if not name:
                continue
            values = {
                "asset_type": "stock",
                "name": name,
                "ticker": candidate.get("ticker") or candidate.get("symbol"),
                "wkn": wkn or candidate.get("wkn"),
                "isin": candidate.get("isin"),
                "exchange": candidate.get("exchange") or candidate.get("exchCode"),
                "country": candidate.get("country"),
                "sector": candidate.get("sector"),
                "instrument_type": "operating_company",
                "instrument_type_status": "inferred",
                "source_id": "openfigi-cache",
                "source_available_at": DEFAULT_AS_OF.isoformat(),
                "retrieved_at": DEFAULT_AS_OF.isoformat(),
                "quality_status": "candidate",
            }
            try:
                assets.append(AssetIdentity.model_validate(values))
            except ValidationError:
                continue
    return assets


def merge_universes(*groups: list[AssetIdentity]) -> list[AssetIdentity]:
    merged = {}
    for group in groups:
        for asset in group:
            merged[stable_asset_id(asset)] = asset
    return list(merged.values())


def assets_for_research_index(
    *,
    base_assets: list[AssetIdentity] | None = None,
    eu_path: Path | None = None,
    us_path: Path | None = None,
    openfigi_path: Path | None = None,
) -> list[AssetIdentity]:
    """Merge SEC/base assets with curated EU/US seeds and optional OpenFIGI cache."""
    groups: list[list[AssetIdentity]] = []
    if base_assets:
        groups.append(list(base_assets))
    groups.append(load_curated_hypothesis_assets(eu_path=eu_path, us_path=us_path))
    if openfigi_path is not None and Path(openfigi_path).is_file():
        groups.append(load_openfigi_identity_records(Path(openfigi_path)))
    return merge_universes(*groups)


def build_index_with_eu_universe(
    path: Path,
    *,
    assets: list[AssetIdentity] | None = None,
    events=None,
    facts=None,
    news=None,
    eu_path: Path | None = None,
    us_path: Path | None = None,
    openfigi_path: Path | None = None,
):
    """Build a research index that includes curated EU/US (+ optional OpenFIGI) assets."""
    merged = assets_for_research_index(
        base_assets=assets or [],
        eu_path=eu_path,
        us_path=us_path,
        openfigi_path=openfigi_path,
    )
    return build_index(
        path,
        assets=merged,
        events=events or [],
        facts=facts or [],
        news=news or [],
    )


def assets_by_id(assets: list[AssetIdentity]) -> dict[str, AssetIdentity]:
    return {stable_asset_id(asset): asset for asset in assets}


# Teaser wording often uses umbrella sectors; curated assets use finer labels.
SECTOR_EQUIVALENCE = {
    "healthcare": frozenset({"healthcare", "pharma", "medical_technology"}),
    "pharma": frozenset({"pharma", "healthcare"}),
    "medical_technology": frozenset({"medical_technology", "healthcare"}),
}


def _sector_overlap(clue_sectors: set[str], asset_sector: str | None) -> bool:
    if not asset_sector or not clue_sectors:
        return False
    if asset_sector in clue_sectors:
        return True
    for clue in clue_sectors:
        if asset_sector in SECTOR_EQUIVALENCE.get(clue, ()):
            return True
    return False


def filter_assets_by_clues(
    assets: list[AssetIdentity],
    clues,
    *,
    as_of: datetime | None = None,
) -> list[tuple[AssetIdentity, int, list[str]]]:
    """Score curated assets against structured stock clues (point-in-time aware)."""
    sectors = {
        clue.value or clue.normalized
        for clue in clues
        if clue.category == "sectors"
        and clue.instrument_scope == "stock"
        and clue.polarity == "asserted"
    }
    countries = {
        clue.value or clue.normalized
        for clue in clues
        if clue.category == "countries"
        and clue.instrument_scope == "stock"
        and clue.polarity == "asserted"
    }
    ranked = []
    for asset in assets:
        if as_of is not None and not asset.historically_available_at(as_of):
            continue
        score = 0
        reasons = []
        if sectors and asset.sector in sectors:
            score += 45
            reasons.append(f"sector_exact:{asset.sector}")
        elif sectors and _sector_overlap(sectors, asset.sector):
            score += 30
            reasons.append(f"sector_related:{asset.sector}")
        elif sectors and asset.sector:
            score -= 15
            reasons.append(f"sector_mismatch:{asset.sector}")
        if countries and any(country_matches(country, asset.country) for country in countries):
            score += 25
            reasons.append(f"country:{asset.country}")
        elif countries and asset.country:
            score -= 25
            reasons.append(f"country_mismatch:{asset.country}")
        if score > 0:
            ranked.append((asset, score, reasons))
    ranked.sort(key=lambda item: (-item[1], item[0].name))
    return ranked
