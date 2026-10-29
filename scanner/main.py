import base64
import binascii
import hashlib
import hmac
import json
import sqlite3
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Annotated, Literal

import httpx
from fastapi import Depends, FastAPI, HTTPException, Query, Request
from fastapi.responses import JSONResponse
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError

from scanner.config import Settings
from scanner.db import create_db, create_sessions
from scanner.domain import Candle
from scanner.hebeltrader.detective.case_journal import CaseJournal
from scanner.hebeltrader.detective.external_research import (
    ApiConfigurationError,
    build_public_research,
)
from scanner.hebeltrader.detective.factory import build_detective, live_api_access_status
from scanner.hebeltrader.detective.investigation import InvestigationRequest, Investigator
from scanner.hebeltrader.detective.resolution import ResolutionRequest
from scanner.hebeltrader.detective.schemas import DetectiveRequest
from scanner.hebeltrader.detective.workflow import run_case
from scanner.hebeltrader.parser import extract_pdf
from scanner.models import Base, Evaluation, MarketCandle, ScanRun

templates = Jinja2Templates(directory=Path(__file__).parent / "templates")


class ArchiveCaseRequest(BaseModel):
    reason: str = Field(min_length=3, max_length=500)


class PromoteReferenceRequest(BaseModel):
    source: str = Field(min_length=3, max_length=500)


class ProspectiveCaseRequest(BaseModel):
    basis: str = Field(min_length=3, max_length=500)


def evidence(evaluation):
    c = evaluation.candle
    return {
        "id": evaluation.id,
        "provider": c.provider,
        "asset_class": c.asset_class,
        "symbol": c.symbol,
        "interval": c.interval,
        "candle_open_time": c.open_time,
        "candle_close_time": c.close_time,
        "observed_at": c.observed_at,
        "evaluated_at": evaluation.evaluated_at,
        "volume": str(c.volume),
        "quote_volume": str(c.quote_volume),
        "baseline_volume": str(evaluation.baseline_volume)
        if evaluation.baseline_volume is not None
        else None,
        "ratio": str(evaluation.ratio) if evaluation.ratio is not None else None,
        "is_signal": evaluation.is_signal,
        "reason": evaluation.reason,
        "detector_key": evaluation.detector_key,
        "actionable": False,
    }


def filters(
    symbol: Annotated[str | None, Query(pattern=r"^[A-Z0-9]{3,30}$")] = None,
    interval: Literal["5m", "15m"] | None = None,
    provider: Annotated[str | None, Query(max_length=40)] = None,
    asset_class: Literal["crypto", "stock"] | None = None,
    limit: Annotated[int, Query(ge=1, le=500)] = 100,
    offset: Annotated[int, Query(ge=0, le=100000)] = 0,
):
    return dict(
        symbol=symbol,
        interval=interval,
        provider=provider,
        asset_class=asset_class,
        limit=limit,
        offset=offset,
    )


def filtered(statement, values):
    for key in ("symbol", "interval", "provider", "asset_class"):
        if values[key] is not None:
            statement = statement.where(getattr(MarketCandle, key) == values[key])
    return statement.limit(values["limit"]).offset(values["offset"])


class SolutionPdfRequest(BaseModel):
    pdf_base64: str = Field(min_length=1, max_length=28_000_000)


def create_app(settings: Settings | None = None, engine=None):
    settings = settings or Settings()
    owned_engine = engine is None
    engine = engine or create_db(settings)
    sessions = create_sessions(engine)

    @asynccontextmanager
    async def lifespan(app):
        yield
        if owned_engine:
            engine.dispose()

    app = FastAPI(title="Multi-Asset Chancen-Scanner V6", version="0.1.0", lifespan=lifespan)
    detective = build_detective(settings)

    @app.exception_handler(SQLAlchemyError)
    async def database_error(request, exc):
        return JSONResponse(
            status_code=503, content={"detail": "Database unavailable or migration missing"}
        )

    @app.get("/api/health")
    def health():
        return {"status": "ok"}

    @app.get("/api/ready")
    def ready():
        with sessions() as session:
            for table in Base.metadata.sorted_tables:
                session.execute(select(table).limit(0))
        return {"status": "ready"}

    @app.get("/api/candles")
    def candles(values: Annotated[dict, Depends(filters)]):
        query = filtered(
            select(MarketCandle).order_by(MarketCandle.open_time.desc(), MarketCandle.id.desc()),
            values,
        )
        with sessions() as session:
            return [
                Candle(**{k: getattr(c, k) for k in Candle.model_fields}).model_dump(mode="json")
                | {"id": c.id, "observed_at": c.observed_at}
                for c in session.scalars(query)
            ]

    def read_evaluations(values, signals_only=False):
        query = (
            select(Evaluation)
            .join(Evaluation.candle)
            .order_by(Evaluation.evaluated_at.desc(), Evaluation.id.desc())
        )
        if signals_only:
            query = query.where(Evaluation.is_signal.is_(True))
        with sessions() as session:
            return [evidence(e) for e in session.scalars(filtered(query, values))]

    @app.get("/api/evaluations")
    def evaluations(values: Annotated[dict, Depends(filters)]):
        return read_evaluations(values)

    @app.get("/api/signals")
    def signals(values: Annotated[dict, Depends(filters)]):
        return read_evaluations(values, signals_only=True)

    @app.get("/api/runs")
    def runs(limit: Annotated[int, Query(ge=1, le=100)] = 20):
        with sessions() as session:
            records = session.scalars(select(ScanRun).order_by(ScanRun.id.desc()).limit(limit))
            return [
                dict(
                    id=r.id,
                    provider=r.provider,
                    started_at=r.started_at,
                    finished_at=r.finished_at,
                    status=r.status,
                    error_count=r.error_count,
                    errors=r.errors,
                )
                for r in records
            ]

    @app.get("/market-scanner")
    def dashboard(request: Request):
        values = dict(
            symbol=None, interval=None, provider=None, asset_class=None, limit=50, offset=0
        )
        return templates.TemplateResponse(
            request=request,
            name="dashboard.html",
            context={
                "signals": read_evaluations(values, signals_only=True),
                "runs": runs(5),
                "configured_provider": settings.provider,
            },
        )

    @app.get("/")
    @app.get("/hebeltrader")
    def hebeltrader_detective(request: Request):
        return templates.TemplateResponse(request=request, name="detective.html", context={})

    @app.get("/api/hebeltrader/updates")
    def teaser_updates(limit: int = Query(20, ge=1, le=100)):
        from scanner.hebeltrader.detective.monitor import notification_feed

        try:
            return notification_feed(settings.detective_public_root, limit)
        except sqlite3.Error:
            raise HTTPException(503, "Teaser notifications unavailable") from None

    @app.post("/api/hebeltrader/investigate")
    def investigate(payload: InvestigationRequest, request: Request):
        if settings.detective_public_allow_network:
            expected = settings.detective_live_api_token
            if expected is None or not expected.get_secret_value().strip():
                raise HTTPException(503, "Public research API authorization is not configured")
            provided = request.headers.get("X-Research-Authorization", "")
            if not hmac.compare_digest(expected.get_secret_value(), provided):
                raise HTTPException(403, "Research authorization required")
        try:
            domains = (
                json.loads(settings.detective_primary_domains.read_text())
                if settings.detective_primary_domains
                else {}
            )
            web = build_public_research(settings, domains)
            issuers = (
                json.loads(settings.detective_product_issuers.read_text())
                if settings.detective_product_issuers
                else {}
            )
            return run_case(
                Investigator(settings.detective_public_root, web=web, product_issuers=issuers),
                payload,
                register_path=settings.detective_case_register,
            )
        except ApiConfigurationError as exc:
            raise HTTPException(503, str(exc)) from None
        except (ValueError, httpx.HTTPError) as exc:
            raise HTTPException(422, "Public research unavailable: " + type(exc).__name__) from None

    def case_access(request: Request):
        expected = settings.detective_live_api_token
        if expected is None or not expected.get_secret_value().strip():
            raise HTTPException(503, "Case journal access token is not configured")
        if not hmac.compare_digest(
            expected.get_secret_value(), request.headers.get("X-Research-Authorization", "")
        ):
            raise HTTPException(403, "Case journal authorization required")

    @app.post("/api/hebeltrader/cases/solution-pdf")
    def case_solution_pdf(payload: SolutionPdfRequest, request: Request):
        case_access(request)
        try:
            data = base64.b64decode(payload.pdf_base64, validate=True)
            extraction = extract_pdf(data)
        except (binascii.Error, ValueError):
            raise HTTPException(422, "Solution PDF could not be read") from None
        recommendation = extraction.recommendations[0].values if extraction.recommendations else {}
        issue = (
            f"{extraction.issue_number}/{extraction.issue_year}" if extraction.issue_number else ""
        )
        return {
            "name": recommendation.get("stock_name"),
            "stock_wkn": recommendation.get("stock_wkn"),
            "call_wkn": recommendation.get("derivative_wkn"),
            "issue": issue,
            "pdf_sha256": hashlib.sha256(data).hexdigest(),
            "flags": [flag.get("code") for flag in extraction.flags],
        }

    @app.get("/api/hebeltrader/cases")
    def case_list(request: Request, include_archived: bool = False):
        case_access(request)
        return CaseJournal(settings.detective_public_root / "cases").cases(include_archived)

    @app.get("/api/hebeltrader/quality")
    def case_quality(request: Request):
        case_access(request)
        return CaseJournal(settings.detective_public_root / "cases").quality()

    @app.get("/api/hebeltrader/cases/{case_id}")
    def case_detail(case_id: str, request: Request):
        case_access(request)
        try:
            return CaseJournal(settings.detective_public_root / "cases").case(case_id)
        except ValueError:
            raise HTTPException(404, "Case unavailable or integrity check failed") from None

    @app.post("/api/hebeltrader/cases/{case_id}/archive")
    def case_archive(case_id: str, payload: ArchiveCaseRequest, request: Request):
        case_access(request)
        try:
            return CaseJournal(settings.detective_public_root / "cases").archive(
                case_id, payload.reason
            )
        except ValueError:
            raise HTTPException(404, "Case unavailable or archive request invalid") from None

    @app.post("/api/hebeltrader/cases/{case_id}/restore")
    def case_restore(case_id: str, payload: ArchiveCaseRequest, request: Request):
        case_access(request)
        try:
            return CaseJournal(settings.detective_public_root / "cases").restore(
                case_id, payload.reason
            )
        except ValueError:
            raise HTTPException(404, "Case unavailable or restore request invalid") from None

    @app.get("/api/hebeltrader/prospective-references")
    def prospective_references(request: Request):
        case_access(request)
        return CaseJournal(settings.detective_public_root / "cases").references()

    @app.post("/api/hebeltrader/cases/{case_id}/reference-promotion")
    def case_reference_promotion(case_id: str, payload: PromoteReferenceRequest, request: Request):
        case_access(request)
        try:
            return CaseJournal(settings.detective_public_root / "cases").promote_reference(
                case_id, payload.source
            )
        except ValueError as exc:
            raise HTTPException(422, str(exc)) from None

    @app.post("/api/hebeltrader/cases/{case_id}/prospective")
    def case_mark_prospective(case_id: str, payload: ProspectiveCaseRequest, request: Request):
        case_access(request)
        try:
            return CaseJournal(settings.detective_public_root / "cases").mark_prospective(
                case_id, payload.basis
            )
        except ValueError as exc:
            raise HTTPException(422, str(exc)) from None

    @app.post("/api/hebeltrader/cases/{case_id}/resolution")
    def case_resolution(case_id: str, payload: ResolutionRequest, request: Request):
        case_access(request)
        journal = CaseJournal(settings.detective_public_root / "cases")
        try:
            result = journal.resolve(case_id, payload.model_dump(exclude_none=True))
            journal.export_register(settings.detective_public_root / "case-register.md")
            if settings.detective_case_register:
                journal.export_register(settings.detective_case_register)
            return result
        except ValueError:
            raise HTTPException(
                422, "Resolution requires a valid frozen case and provenance"
            ) from None

    @app.post("/api/hebeltrader/detective/analyze")
    def analyze_hebeltrader_teaser(payload: DetectiveRequest, request: Request):
        access = live_api_access_status(settings, request.headers.get("X-Research-Authorization"))
        if access == "token_missing":
            raise HTTPException(status_code=503, detail="Live research API token is not configured")
        if access == "unauthorized":
            raise HTTPException(status_code=403, detail="Live research authorization required")
        try:
            return detective.analyze(payload)
        except ValueError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc

    return app
