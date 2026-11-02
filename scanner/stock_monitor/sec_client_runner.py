"""Run a bounded stock SEC pass using the repository's existing SEC cache client.

Network is disabled unless explicitly requested; never executes trades.
"""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

from scanner.research_providers.sec_edgar import SecEdgarClient
from scanner.stock_monitor.worker import SecTarget, run_sec_monitor


def run_with_sec_client(
    *,
    cache_root: Path,
    journal_path: Path,
    targets: list[SecTarget],
    run_id: str,
    code_version: str,
    allow_network: bool = False,
    max_requests: int = 0,
    user_agent: str | None = None,
    cutoff: datetime | None = None,
    live_mode: bool = False,
) -> dict:
    """Reuse SEC cache, User-Agent policy, retries and request budget."""
    if max_requests < 0 or max_requests > 100:
        raise ValueError("SEC request budget must be 0..100")
    if allow_network and max_requests == 0:
        raise ValueError("Explicit positive request budget required")
    if not allow_network and max_requests:
        raise ValueError("Nonzero request budget requires explicit network opt-in")
    client = SecEdgarClient(
        cache_root,
        user_agent=user_agent,
        allow_network=allow_network,
        max_requests=max_requests,
    )
    return run_sec_monitor(
        fetch_submissions=lambda cik: client.fetch("submissions", cik),
        targets=targets,
        journal_path=journal_path,
        run_id=run_id,
        code_version=code_version,
        cutoff=cutoff or datetime.now(UTC),
        max_targets=100,
        live_mode=live_mode,
    )
