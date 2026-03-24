from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class PipelineRunRequest(BaseModel):
    bench_height: int = Field(default=15, ge=10, le=30)
    max_blocks: int = Field(default=60, ge=10, le=300)
    spatial_neighbors: int = Field(default=2, ge=1, le=5)
    spatial_radius: float = Field(default=450.0, ge=50.0, le=2000.0)
    exact_solver_limit: int = Field(default=20, ge=4, le=30)


class DatasetResponse(BaseModel):
    dataset: str
    rows: list[dict[str, Any]]
    total_rows: int


class DashboardResponse(BaseModel):
    counts: dict[str, int]
    resources: list[dict[str, str]]
    previews: dict[str, list[dict[str, str]]]
    schedule_metrics: dict[str, int]
    sources: dict[str, str]
    artifacts: dict[str, str]


class PipelineRunResponse(BaseModel):
    preparation: dict[str, Any]
    schedule: dict[str, Any]
    best_scenario: dict[str, Any]
    scenario_comparison: list[dict[str, Any]]
    artifacts: dict[str, str]
