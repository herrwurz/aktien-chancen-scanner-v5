# syntax=docker/dockerfile:1
FROM python:3.12.12-slim-bookworm
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
WORKDIR /app
COPY requirements.lock ./
# Optional CA secret supports managed build proxies without embedding certificates.
RUN --mount=type=secret,id=proxy_ca \
    if [ -f /run/secrets/proxy_ca ]; then export PIP_CERT=/run/secrets/proxy_ca; fi; \
    pip install --no-cache-dir -r requirements.lock
RUN groupadd --gid 10001 scanner && useradd --uid 10001 --gid scanner --no-create-home scanner
COPY --chown=10001:10001 scanner ./scanner
COPY --chown=10001:10001 alembic.ini ./
COPY --chown=10001:10001 migrations ./migrations
# Permit a one-shot offline container to use the invoking host UID for a writable
# bind-mounted report directory. Source remains read-only in the runtime image.
RUN chmod -R a+rX /app
USER scanner
EXPOSE 8000
CMD ["uvicorn", "scanner.main:create_app", "--factory", "--host", "0.0.0.0", "--port", "8000"]
