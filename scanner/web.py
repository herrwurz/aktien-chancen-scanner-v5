"""Password-protected standalone deployment of the existing teaser application."""

import base64
import binascii
import hmac
import os
from pathlib import Path
from urllib.parse import urlsplit

import httpx
from fastapi import HTTPException
from fastapi.responses import Response
from pydantic import SecretStr

from scanner.config import Settings
from scanner.db import create_db
from scanner.main import create_app
from scanner.models import Base


def _secret(name):
    path = os.environ.get(name)
    if not path:
        raise ValueError(f"{name} must point to a private secret file")
    value = Path(path).read_text().strip()
    if len(value) < 12:
        raise ValueError(f"{name} must contain at least 12 characters")
    return value


def create_web_app():
    password = _secret("TEASER_PASSWORD_FILE")
    token = _secret("TEASER_TOKEN_FILE")
    username = os.environ.get("TEASER_USERNAME", "admin")
    state = Path(os.environ.get("TEASER_STATE_DIR", "/data"))
    state.mkdir(parents=True, exist_ok=True)
    settings = Settings(
        _env_file=None,
        database_url=SecretStr("sqlite:///" + str(state.resolve() / "web.db")),
        detective_public_root=state / "detective",
        detective_live_api_token=SecretStr(token),
    )
    # Only this deployment's dedicated database; never migrate an external database.
    engine = create_db(settings)
    Base.metadata.create_all(engine)
    engine.dispose()
    app = create_app(settings)

    @app.get("/api/hebeltrader/references")
    def historical_library():
        from scanner.reference_library import library

        try:
            return library(state)
        except FileNotFoundError:
            raise HTTPException(404, "Referenzbestand noch nicht geladen") from None
        except (ValueError, OSError):
            raise HTTPException(503, "Referenzbestand konnte nicht geprüft werden") from None

    @app.post("/api/hebeltrader/references/import")
    def import_historical_library():
        from scanner.reference_library import import_library

        try:
            return import_library(state)
        except (ValueError, OSError, httpx.HTTPError):
            raise HTTPException(
                503, "Referenzimport nicht verfügbar; bitte erneut versuchen"
            ) from None

    @app.middleware("http")
    async def protect(request, call_next):
        supplied = request.headers.get("authorization", "")
        try:
            scheme, encoded = supplied.split(" ", 1)
            if scheme.lower() != "basic":
                raise ValueError("scheme")
            user, secret = base64.b64decode(encoded, validate=True).decode().split(":", 1)
            valid = hmac.compare_digest(user.encode(), username.encode()) & hmac.compare_digest(
                secret.encode(), password.encode()
            )
        except (ValueError, UnicodeError, binascii.Error):
            valid = False
        if not valid:
            return Response(
                status_code=401,
                headers={
                    "WWW-Authenticate": 'Basic realm="Teaser Detektiv", charset="UTF-8"',
                    "Cache-Control": "no-store",
                },
            )
        if request.method not in ("GET", "HEAD", "OPTIONS"):
            origin = request.headers.get("origin")
            if (origin and urlsplit(origin).netloc != request.headers.get("host")) or (
                request.headers.get("sec-fetch-site") == "cross-site"
            ):
                return Response(status_code=403)
        request.scope["teaser_web"] = True
        request.scope["headers"] = [
            (key, value)
            for key, value in request.scope["headers"]
            if key.lower() != b"x-research-authorization"
        ] + [(b"x-research-authorization", token.encode())]
        response = await call_next(request)
        response.headers["Cache-Control"] = "no-store"
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        return response

    return app
