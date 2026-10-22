import json
import shutil
from pathlib import Path

from alembic import command
from alembic.config import Config

from scanner.hebeltrader.cli import main

FIXTURES = Path(__file__).parents[1] / "fixtures" / "hebeltrader"


def test_cli_import_report_inspect_review_and_export(tmp_path, monkeypatch, capsys):
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{tmp_path}/cli.db")
    command.upgrade(Config("alembic.ini"), "head")
    source = tmp_path / "pdf"
    source.mkdir()
    shutil.copyfile(FIXTURES / "complete.pdf", source / "test.pdf")
    reports = tmp_path / "reports"
    args = [
        "import",
        "--pdf-dir",
        str(source),
        "--report-dir",
        str(reports),
        "--expected-count",
        "1",
    ]
    assert main(args) == 0
    first = json.loads(capsys.readouterr().out)
    sha = first["files"][0]["sha256"]
    assert len(list(reports.glob("import-*.json"))) == 1
    assert main(args) == 0
    assert json.loads(capsys.readouterr().out)["skipped"] == 1
    assert main(["inspect", "--sha", sha]) == 0
    details = json.loads(capsys.readouterr().out)
    assert details["recommendations"][0]["evidence"]["entry_price"][0]["page"] == 1
    assert (
        main(
            [
                "review",
                "--sha",
                sha,
                "--action",
                "approve",
                "--reviewer",
                "test",
                "--note",
                "Source inspected, optional missing values accepted",
            ]
        )
        == 0
    )
    capsys.readouterr()
    target = tmp_path / "features.json"
    assert main(["export", "--as-of", "2025-02-15T00:00:00+01:00", "--output", str(target)]) == 0
    assert len(json.loads(target.read_text())) == 1


def test_count_mismatch_returns_nonzero_and_reports_it(tmp_path, monkeypatch, capsys):
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{tmp_path}/count.db")
    command.upgrade(Config("alembic.ini"), "head")
    source = tmp_path / "pdf"
    source.mkdir()
    assert (
        main(
            [
                "import",
                "--pdf-dir",
                str(source),
                "--report-dir",
                str(tmp_path / "reports"),
                "--expected-count",
                "118",
            ]
        )
        == 2
    )
    assert json.loads(capsys.readouterr().out)["warnings"][0]["code"] == "file_count_mismatch"
