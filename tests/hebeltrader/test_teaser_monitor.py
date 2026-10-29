from datetime import UTC, datetime

from scanner.hebeltrader.detective.monitor import TeaserMonitor

NOW = datetime(2026, 10, 28, 12, tzinfo=UTC)


class Web:
    def search(self, query, limit=10):
        return [{"url": "https://publisher.example/teaser"}]

    def fetch(self, url):
        return {
            "url": url,
            "title": "HEBELTRADER: Unbekannter Chipkonzern",
            "text": "HEBELTRADER: Bis zu plus 1.191 Prozent Renditechance mit einem Call.",
            "published_at": NOW.isoformat(),
            "retrieved_at": NOW.isoformat(),
            "source_kind": "news",
        }


class Engine:
    def __init__(self):
        self.calls = 0
        self.improved = False

    def analyze(self, request):
        self.calls += 1
        return {
            "identification": {"status": "identified" if self.improved else "not_identified"},
            "candidates": [
                {
                    "evidence_score": 100 if self.improved else 0,
                    "confirmed_specific_clues": ["a", "b"] if self.improved else [],
                    "hard_contradictions": [],
                }
            ],
            "artifact_directory": "synthetic-archive",
            "analysis_seconds": 1,
        }


def test_new_only_dedup_and_material_improvement_notifications(tmp_path):
    engine = Engine()
    monitor = TeaserMonitor(tmp_path, web=Web(), engine=engine, clock=lambda: NOW)
    assert monitor.scan_once()["new_teasers"] == 1
    assert monitor.scan_once()["new_teasers"] == 0
    assert engine.calls == 1
    assert len(monitor.notifications()) == 1
    engine.improved = True
    assert monitor.scan_once(force_recheck=True)["improved_identifications"] == 1
    assert len(monitor.notifications()) == 2
    monitor.scan_once(force_recheck=True)
    assert len(monitor.notifications()) == 2


def test_regular_marketing_article_without_teaser_is_not_an_alert(tmp_path):
    web = Web()
    web.fetch = lambda url: {
        "url": url,
        "title": "Interview",
        "text": (
            "HEBELTRADER erklärt Risikomanagement. Werbung: bis zu 100 Prozent Rendite mit Call."
        ),
        "published_at": None,
        "retrieved_at": NOW.isoformat(),
    }
    monitor = TeaserMonitor(tmp_path, web=web, engine=Engine(), clock=lambda: NOW)
    assert monitor.scan_once()["new_teasers"] == 0
    assert not monitor.notifications()


def test_oversized_original_is_archived_but_never_silently_truncated(tmp_path):
    web = Web()
    fetch = web.fetch
    web.fetch = lambda url: dict(fetch(url), text=fetch(url)["text"] + " x" * 11000)
    engine = Engine()
    result = TeaserMonitor(tmp_path, web=web, engine=engine, clock=lambda: NOW).scan_once()
    assert result["analyzed"] == 0
    assert "teaser_text_exceeds_input_limit" in result["errors"]
    assert list((tmp_path / "teasers").rglob("*.json"))
