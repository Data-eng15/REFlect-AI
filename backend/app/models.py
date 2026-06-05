from __future__ import annotations

from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


class AgentState(str, Enum):
    pending = "pending"
    running = "running"
    complete = "complete"
    warning = "warning"
    error = "error"


class AnalyzeRequest(BaseModel):
    query: str = Field(min_length=2, max_length=500)


class AgentStatus(BaseModel):
    name: str
    label: str
    state: AgentState
    detail: str


class TraceLog(BaseModel):
    timestamp: str
    agent: str
    message: str
    data: dict[str, Any] = Field(default_factory=dict)


class PaperMetadata(BaseModel):
    title: str = "Unknown title"
    authors: list[str] = Field(default_factory=list)
    year: int | None = None
    doi: str | None = None
    abstract: str | None = None
    source_url: str | None = None


class EvidenceItem(BaseModel):
    title: str
    url: str | None = None
    year: int | None = None
    authors: list[str] = Field(default_factory=list)
    snippet: str | None = None
    source: str
    kind: str = "citation"
    citation_count: int | None = None
    metric_label: str | None = None
    metric_value: str | None = None


class ImpactSection(BaseModel):
    title: str
    body: str


class AnalyzeResponse(BaseModel):
    metadata: PaperMetadata
    summary: str
    sections: list[ImpactSection]
    evidence: list[EvidenceItem]
    agent_statuses: list[AgentStatus]
    logs: list[TraceLog]
    faithfulness_score: float
    citation_count: int
    topics: list[str] = Field(default_factory=list)
    model_provider: str = "deterministic"
    rag_context_count: int = 0
    guardrail_status: str = "not_run"
    limitations: list[str] = Field(default_factory=list)
    ref_report: str = ""
    validation_report: dict = Field(default_factory=dict)
