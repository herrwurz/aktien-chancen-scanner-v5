import hashlib
import json
import subprocess
from pathlib import Path

from scanner.hebeltrader.detective.real_acceptance import write_acceptance_preflight


def test_missing_original_material_writes_stable_pending_artifacts(tmp_path):
    first = write_acceptance_preflight(
        teaser_path=tmp_path / "missing.pdf",
        publication_at=None,
        rights_status=None,
        research_index=tmp_path / "missing.db",
        output_dir=tmp_path / "first",
    )
    second = write_acceptance_preflight(
        teaser_path=tmp_path / "missing.pdf",
        publication_at=None,
        rights_status=None,
        research_index=tmp_path / "missing.db",
        output_dir=tmp_path / "second",
    )

    assert first["status"] == "pending_external_material"
    assert first["blockers"] == [
        "original_teaser_missing",
        "publication_time_missing",
        "research_index_missing",
        "rights_status_missing",
    ]
    assert first["payload_sha256"] == second["payload_sha256"]
    report = Path(first["artifacts"]["json"])
    assert (
        hashlib.sha256(report.read_bytes()).hexdigest()
        == Path(first["artifacts"]["sha256"]).read_text().split()[0]
    )
    assert Path(first["artifacts"]["csv"]).exists()


def test_runner_uses_read_only_isolated_mounts_without_solution_or_secrets():
    script = Path("scripts/run_detective_v3_real.sh").read_text()
    assert "--network none" in script
    assert "readonly" in script
    assert "solution" not in script.casefold()
    assert "API_TOKEN" not in script
    assert "TIINGO" not in script
    assert "sh -c" not in script
    subprocess.run(["bash", "-n", "scripts/run_detective_v3_real.sh"], check=True)


def test_preflight_report_never_claims_real_success(tmp_path):
    teaser = tmp_path / "teaser.txt"
    teaser.write_text("Unveränderter Teaser", encoding="utf-8")
    index = tmp_path / "index.db"
    index.write_bytes(b"index")
    result = write_acceptance_preflight(
        teaser_path=teaser,
        publication_at="2025-01-01T12:00:00Z",
        rights_status="authorized_local_analysis",
        research_index=index,
        output_dir=tmp_path / "out",
    )
    payload = json.loads(Path(result["artifacts"]["json"]).read_text())
    assert payload["status"] == "ready_for_read_only_scan"
    assert payload["real_end_to_end_completed"] is False
    assert payload["teaser_sha256"] == hashlib.sha256(teaser.read_bytes()).hexdigest()
