import hashlib
import json
import shutil
import subprocess
from pathlib import Path

import pytest

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
        "research_index_manifest_missing",
        "rights_status_missing",
    ]
    assert first["gold_label_must_remain_unmounted"] is True
    assert first["next_steps"]
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
    assert "pending_external_material" in script
    assert "ready_for_read_only_scan" in script
    assert "solution" not in script.casefold()
    assert "API_TOKEN" not in script
    assert "TIINGO" not in script
    assert "sh -c" not in script

    blind = Path("scripts/run_detective_v3_blind_scan.sh").read_text()
    assert "--network none" in blind
    assert "--read-only" in blind
    assert "solutions" not in blind.casefold()
    assert blind.count("--mount") == 4
    bash = shutil.which("bash")
    if not bash:
        pytest.skip("bash not available for shell syntax check")
    probe = subprocess.run([bash, "-c", "exit 0"], capture_output=True)
    if probe.returncode != 0:
        pytest.skip("bash is present but not executable in this environment")
    subprocess.run([bash, "-n", "scripts/run_detective_v3_real.sh"], check=True)
    subprocess.run([bash, "-n", "scripts/run_detective_v3_blind_scan.sh"], check=True)


def test_preflight_report_never_claims_real_success(tmp_path):
    teaser = tmp_path / "teaser.txt"
    teaser.write_text("Unveränderter Teaser", encoding="utf-8")
    index = tmp_path / "index.db"
    index.write_bytes(b"index")
    (tmp_path / "index.db.manifest.json").write_text("{}", encoding="utf-8")
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
    assert payload["gold_label_must_remain_unmounted"] is True
    assert payload["teaser_sha256"] == hashlib.sha256(teaser.read_bytes()).hexdigest()


def test_unrecognized_rights_status_blocks_real_acceptance(tmp_path):
    teaser = tmp_path / "teaser.txt"
    teaser.write_text("Teaser", encoding="utf-8")
    index = tmp_path / "index.db"
    index.write_bytes(b"index")
    (tmp_path / "index.db.manifest.json").write_text("{}", encoding="utf-8")
    result = write_acceptance_preflight(
        teaser_path=teaser,
        publication_at="2025-01-01T12:00:00Z",
        rights_status="copied_from_newsletter_without_clearance",
        research_index=index,
        output_dir=tmp_path / "blocked",
    )
    assert result["status"] == "pending_external_material"
    assert "rights_status_unrecognized" in result["blockers"]
