from dataclasses import dataclass, field
from datetime import date

EXTRACTOR_VERSION = "hebeltrader-rules-v1"


@dataclass
class RecommendationData:
    values: dict = field(default_factory=dict)
    evidence: dict[str, list[dict]] = field(default_factory=dict)
    flags: list[dict] = field(default_factory=list)


@dataclass
class Extraction:
    publication_date: date | None = None
    issue_number: int | None = None
    issue_year: int | None = None
    metadata_evidence: list[dict] = field(default_factory=list)
    recommendations: list[RecommendationData] = field(default_factory=list)
    pages: list[dict] = field(default_factory=list)
    flags: list[dict] = field(default_factory=list)
