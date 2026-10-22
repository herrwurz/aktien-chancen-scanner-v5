from pathlib import Path

import yaml


def test_import_service_is_optional_private_and_uses_readonly_source():
    cfg = yaml.safe_load(Path("compose.yaml").read_text())
    service = cfg["services"]["pdf-import"]
    assert service["profiles"] == ["analysis"]
    assert service["restart"] == "no"
    assert service["networks"] == ["backend"]
    assert "ports" not in service
    mounts = {m["target"]: m for m in service["volumes"]}
    assert mounts["/input"]["read_only"] is True
    assert mounts["/input"]["bind"]["create_host_path"] is False
    assert mounts["/reports"].get("read_only", False) is False
    assert not any("HEBELTRADER" in k for k in cfg["services"]["worker"]["environment"])
    assert cfg["services"]["worker"]["command"] == ["python", "-m", "scanner.worker"]
    assert cfg["services"]["api"]["ports"] == ["127.0.0.1:${DASHBOARD_PORT:-8066}:8000"]
