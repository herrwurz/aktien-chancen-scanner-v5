from pathlib import Path

import yaml


def test_compose_is_isolated_and_database_private():
    cfg = yaml.safe_load(Path("compose.yaml").read_text())
    assert cfg["name"] == "chancen-scanner-v6"
    assert set(cfg["volumes"]) == {"scanner_postgres", "cross_asset_research"}
    assert cfg["services"]["cross-asset-research"]["profiles"] == ["research"]
    assert cfg["services"]["cross-asset-research"]["networks"] == ["egress"]
    assert cfg["services"]["cross-asset-research"]["volumes"] == ["cross_asset_research:/data"]
    assert "depends_on" not in cfg["services"]["cross-asset-research"]
    assert set(cfg["networks"]) == {"backend", "egress", "web"}
    assert cfg["networks"]["backend"]["internal"] is True
    assert cfg["services"]["api"]["networks"] == ["backend", "web"]
    assert "ports" not in cfg["services"]["db"]
    assert cfg["services"]["api"]["ports"] == ["127.0.0.1:${DASHBOARD_PORT:-8066}:8000"]
    assert "container_name" not in str(cfg)
    assert "external" not in str(cfg)
    assert "immich" not in str(cfg).lower()
    assert (
        cfg["services"]["worker"]["depends_on"]["migrate"]["condition"]
        == "service_completed_successfully"
    )


def test_image_excludes_secrets_and_runs_nonroot():
    ignore = Path(".dockerignore").read_text().splitlines()
    assert ".env" in ignore
    assert ".git" in ignore
    dockerfile = Path("Dockerfile").read_text()
    assert "USER scanner" in dockerfile
    assert "requirements.lock" in dockerfile
