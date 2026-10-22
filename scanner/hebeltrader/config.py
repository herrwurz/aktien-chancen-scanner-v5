from pathlib import Path

from pydantic import Field

from scanner.config import Settings


class ImportSettings(Settings):
    hebeltrader_pdf_dir: Path = Path("data/hebeltrader")
    hebeltrader_report_dir: Path = Path("reports/hebeltrader")
    hebeltrader_expected_count: int | None = Field(default=None, ge=1)
