"""Provider-neutral provenance records for historical stock bars."""

from typing import Protocol


class HistoricalBarArchive(Protocol):
    """Collectors archive vendor bytes; adapters normalize them without trading logic."""

    def fetch(self, symbol: str, *, start: str, end: str) -> dict: ...


RAW_BAR_FIELDS = ("date", "open", "high", "low", "close", "volume")
ADJUSTED_BAR_FIELDS = ("adjusted_open", "adjusted_high", "adjusted_low", "adjusted_close")


def compare_daily_coverage(provider_rows):
    """Compare delivered dates only; never infer sessions or splice provider histories."""
    dates = {
        provider: {str(row["date"]) for row in rows}
        for provider, rows in sorted(provider_rows.items())
    }
    union = set().union(*dates.values()) if dates else set()
    shared = set.intersection(*dates.values()) if dates else set()
    return {
        "providers": {
            provider: {
                "delivered_rows": len(provider_dates),
                "first_date": min(provider_dates) if provider_dates else None,
                "last_date": max(provider_dates) if provider_dates else None,
                "missing_vs_union": sorted(union - provider_dates),
            }
            for provider, provider_dates in dates.items()
        },
        "shared_dates": sorted(shared),
        "series_merged": False,
        "calendar_completeness": "requires_independent_review",
        "corporate_action_and_currency_reconciliation": "required_before_provider_fallback",
    }
