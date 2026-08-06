"""Pydantic request/response models for the REST API."""
from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field


class HealthResponse(BaseModel):
    status: str
    timestamp: datetime


class PipelineStageStatus(BaseModel):
    run_id: str
    stage: str
    started_at: datetime
    ended_at: datetime | None
    status: str
    rows_read: int | None
    rows_new: int | None
    rows_updated: int | None
    rows_unchanged: int | None
    rows_rejected: int | None
    error_message: str | None


class PipelineStatusResponse(BaseModel):
    latest_run_id: str | None
    stages: list[PipelineStageStatus]


class PortfolioSummaryResponse(BaseModel):
    total_applications: int
    total_requested_loan_amount: float
    approval_rate_pct: float
    denial_rate_pct: float
    average_loan_amount: float
    average_applicant_income: float
    high_risk_application_count: int


class TrendPoint(BaseModel):
    year_month: str
    total_applications: int
    approved_applications: int
    approval_rate_pct: float
    total_loan_amount: float


class PortfolioTrendsResponse(BaseModel):
    points: list[TrendPoint]


class DataQualityCheckResult(BaseModel):
    name: str
    passed: bool
    details: str


class DataQualityReportResponse(BaseModel):
    generated_at: str
    overall_status: str
    checks_passed: int
    checks_total: int
    checks: list[DataQualityCheckResult]


class PolicyQuestionRequest(BaseModel):
    question: str = Field(..., min_length=3, max_length=500, description="A question about lending policy.")


class Citation(BaseModel):
    document_name: str
    section_title: str
    similarity_score: float


class RetrievedPassage(BaseModel):
    document_name: str
    section_title: str
    text: str
    score: float


class PolicyAnswerResponse(BaseModel):
    question: str
    answer: str
    is_answerable: bool
    citations: list[Citation]
    retrieved_passages: list[RetrievedPassage]
