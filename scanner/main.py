from contextlib import asynccontextmanager
from pathlib import Path
from typing import Annotated, Literal

from fastapi import Depends, FastAPI, Query, Request
from fastapi.responses import JSONResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError

from scanner.config import Settings
from scanner.db import create_db, create_sessions
from scanner.domain import Candle
from scanner.models import Base, Evaluation, MarketCandle, ScanRun

templates = Jinja2Templates(directory=Path(__file__).parent / "templates")


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

    @app.get("/")
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

    return app
