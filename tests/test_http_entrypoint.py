import pytest

from scanner import http_entrypoint


@pytest.mark.parametrize("factory", ["scanner.main:create_app", "scanner.web:create_web_app"])
def test_explicit_container_factory(monkeypatch, factory):
    monkeypatch.setenv("SCANNER_APP_FACTORY", factory)
    calls = []
    monkeypatch.setattr(http_entrypoint.uvicorn, "run", lambda *a, **k: calls.append((a, k)))
    http_entrypoint.main()
    assert calls == [((factory,), dict(factory=True, host="0.0.0.0", port=8000))]


def test_invalid_factory_rejected(monkeypatch):
    monkeypatch.setenv("SCANNER_APP_FACTORY", "unknown:app")
    with pytest.raises(ValueError):
        http_entrypoint.main()
