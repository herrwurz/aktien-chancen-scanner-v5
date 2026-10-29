"""Shared container start, with explicit opt-in to the protected web application."""

import os

import uvicorn


def main():
    factory = os.environ.get("SCANNER_APP_FACTORY", "scanner.main:create_app")
    if factory not in ("scanner.main:create_app", "scanner.web:create_web_app"):
        raise ValueError("Unsupported SCANNER_APP_FACTORY")
    uvicorn.run(factory, factory=True, host="0.0.0.0", port=8000)


if __name__ == "__main__":
    main()
