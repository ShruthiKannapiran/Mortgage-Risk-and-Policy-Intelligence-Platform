"""FastAPI service exposing pipeline status, portfolio analytics, data-quality results,
and the RAG policy assistant.

Run with: uvicorn src.api.main:app --reload
Docs at:  http://localhost:8000/docs
"""
from __future__ import annotations

import json
from datetime import datetime, timezone

import duckdb
from fastapi import Depends, FastAPI, HTTPException, Query
from fastapi.responses import JSONResponse

from src.api import queries
from src.api.dependencies import get_db
from src.api.schemas import (
    DataQualityReportResponse,
    HealthResponse,
    PipelineStatusResponse,
    PolicyAnswerResponse,
    PolicyQuestionRequest,
    PortfolioSummaryResponse,
    PortfolioTrendsResponse,
)
from src.common.config import get_paths, load_config
from src.common.logging_setup import get_logger

logger = get_logger("api")
cfg = load_config()

app = FastAPI(
    title=cfg["api"]["title"],
    version=cfg["api"]["version"],
    description=(
        "REST API over the Mortgage Risk and Policy Intelligence Platform's gold-layer "
        "analytics, pipeline health, and RAG-based lending-policy assistant."
    ),
)


@app.exception_handler(Exception)
async def unhandled_exception_handler(request, exc: Exception):
    logger.exception("Unhandled error on %s %s", request.method, request.url.path)
    return JSONResponse(status_code=500, content={"detail": "An internal error occurred. Please try again later."})


VALID_STATES = {
    "AL", "AK", "AZ", "AR", "CA", "CO", "CT", "DE", "FL", "GA", "HI", "ID", "IL", "IN",
    "IA", "KS", "KY", "LA", "ME", "MD", "MA", "MI", "MN", "MS", "MO", "MT", "NE", "NV",
    "NH", "NJ", "NM", "NY", "NC", "ND", "OH", "OK", "OR", "PA", "RI", "SC", "SD", "TN",
    "TX", "UT", "VT", "VA", "WA", "WV", "WI", "WY", "DC",
}
VALID_LOAN_TYPES = {"Conventional", "FHA", "VA", "USDA"}
VALID_STATUSES = {"Approved", "Denied", "Withdrawn", "Incomplete"}


def _validate_filters(state: str | None, loan_type: str | None, status: str | None) -> None:
    if state and state.strip().upper() not in VALID_STATES:
        raise HTTPException(status_code=422, detail=f"Unknown state code: {state!r}")
    if loan_type and loan_type not in VALID_LOAN_TYPES:
        raise HTTPException(status_code=422, detail=f"Unknown loan_type: {loan_type!r}. Expected one of {sorted(VALID_LOAN_TYPES)}")
    if status and status not in VALID_STATUSES:
        raise HTTPException(status_code=422, detail=f"Unknown status: {status!r}. Expected one of {sorted(VALID_STATUSES)}")


@app.get("/health", response_model=HealthResponse, tags=["system"])
def health() -> HealthResponse:
    return HealthResponse(status="ok", timestamp=datetime.now(timezone.utc))


@app.get("/pipeline/status", response_model=PipelineStatusResponse, tags=["system"])
def pipeline_status(con: duckdb.DuckDBPyConnection = Depends(get_db)) -> PipelineStatusResponse:
    run_id, stages = queries.latest_pipeline_stages(con)
    return PipelineStatusResponse(latest_run_id=run_id, stages=stages)


@app.get("/portfolio/summary", response_model=PortfolioSummaryResponse, tags=["analytics"])
def portfolio_summary(
    state: str | None = Query(None, description="Two-letter US state code, e.g. CA"),
    lender: str | None = Query(None),
    loan_type: str | None = Query(None, description="Conventional | FHA | VA | USDA"),
    status: str | None = Query(None, description="Approved | Denied | Withdrawn | Incomplete"),
    con: duckdb.DuckDBPyConnection = Depends(get_db),
) -> PortfolioSummaryResponse:
    _validate_filters(state, loan_type, status)
    result = queries.portfolio_summary(con, state, lender, loan_type, status)
    return PortfolioSummaryResponse(**result)


@app.get("/portfolio/trends", response_model=PortfolioTrendsResponse, tags=["analytics"])
def portfolio_trends(
    state: str | None = Query(None, description="Two-letter US state code, e.g. CA"),
    lender: str | None = Query(None),
    loan_type: str | None = Query(None, description="Conventional | FHA | VA | USDA"),
    status: str | None = Query(None, description="Approved | Denied | Withdrawn | Incomplete"),
    con: duckdb.DuckDBPyConnection = Depends(get_db),
) -> PortfolioTrendsResponse:
    _validate_filters(state, loan_type, status)
    points = queries.portfolio_trends(con, state, lender, loan_type, status)
    return PortfolioTrendsResponse(points=points)


@app.get("/data-quality/latest", response_model=DataQualityReportResponse, tags=["quality"])
def data_quality_latest() -> DataQualityReportResponse:
    paths = get_paths()
    report_path = paths["reports_dir"] / "data_quality_report.json"
    if not report_path.exists():
        raise HTTPException(status_code=404, detail="No data-quality report found. Run the pipeline first.")
    with open(report_path, "r", encoding="utf-8") as fh:
        report = json.load(fh)
    return DataQualityReportResponse(**report)


@app.post("/policy/ask", response_model=PolicyAnswerResponse, tags=["rag"])
def policy_ask(request: PolicyQuestionRequest) -> PolicyAnswerResponse:
    from src.rag.pipeline import answer_question  # lazy import: avoids loading the embedding model at API startup

    try:
        result = answer_question(request.question)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    return PolicyAnswerResponse(
        question=result.question,
        answer=result.answer,
        is_answerable=result.is_answerable,
        citations=result.citations,
        retrieved_passages=result.retrieved_passages,
    )
