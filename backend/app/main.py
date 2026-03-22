from __future__ import annotations

from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import FileResponse
from fastapi.middleware.cors import CORSMiddleware

from mine_scheduler.pipeline import (
    DEFAULT_OUTPUT_DIR,
    count_csv_rows,
    get_dashboard_snapshot,
    read_csv_rows,
    run_web_pipeline,
)

from .schemas import DashboardResponse, DatasetResponse, PipelineRunRequest, PipelineRunResponse

DATASET_FILES = {
    "block_model": DEFAULT_OUTPUT_DIR / "block_model.csv",
    "ore_blocks": DEFAULT_OUTPUT_DIR / "ore_blocks.csv",
    "block_precedence": DEFAULT_OUTPUT_DIR / "block_precedence.csv",
    "tasks": DEFAULT_OUTPUT_DIR / "tasks.csv",
    "task_precedence": DEFAULT_OUTPUT_DIR / "task_precedence.csv",
    "maintenance": DEFAULT_OUTPUT_DIR / "maintenance.csv",
    "resources": DEFAULT_OUTPUT_DIR / "resources.csv",
    "schedule": DEFAULT_OUTPUT_DIR / "schedule_output.csv",
    "scenario_comparison": DEFAULT_OUTPUT_DIR / "scenario_comparison.csv",
}

ARTIFACT_FILES = {
    "gantt_svg": DEFAULT_OUTPUT_DIR / "gantt_chart.svg",
    "gantt_html": DEFAULT_OUTPUT_DIR / "gantt_chart.html",
    "report_markdown": DEFAULT_OUTPUT_DIR / "project_report.md",
    "report_html": DEFAULT_OUTPUT_DIR / "project_report.html",
}

app = FastAPI(
    title="Mine Planning Dashboard API",
    version="0.1.0",
    description="API for running and inspecting the web-derived open-pit planning pipeline.",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/api/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/api/dashboard", response_model=DashboardResponse)
def dashboard() -> DashboardResponse:
    snapshot = get_dashboard_snapshot()
    return DashboardResponse(**snapshot)


@app.post("/api/pipeline/run", response_model=PipelineRunResponse)
def run_pipeline(payload: PipelineRunRequest) -> PipelineRunResponse:
    result = run_web_pipeline(
        bench_height=payload.bench_height,
        max_blocks=payload.max_blocks,
        spatial_neighbors=payload.spatial_neighbors,
        spatial_radius=payload.spatial_radius,
        exact_solver_limit=payload.exact_solver_limit,
    )
    return PipelineRunResponse(**result)


@app.get("/api/datasets/{dataset_name}", response_model=DatasetResponse)
def dataset(
    dataset_name: str,
    limit: int = Query(default=50, ge=1, le=500),
) -> DatasetResponse:
    path = DATASET_FILES.get(dataset_name)
    if path is None:
        raise HTTPException(status_code=404, detail=f"Unknown dataset: {dataset_name}")

    return DatasetResponse(
        dataset=dataset_name,
        rows=read_csv_rows(path, limit=limit),
        total_rows=count_csv_rows(path),
    )


@app.get("/api/files")
def files() -> dict[str, str]:
    return {
        **{name: str(path) for name, path in DATASET_FILES.items()},
        **{name: str(path) for name, path in ARTIFACT_FILES.items()},
    }


@app.get("/api/artifacts/{artifact_name}")
def artifact(artifact_name: str) -> FileResponse:
    path = ARTIFACT_FILES.get(artifact_name)
    if path is None or not path.exists():
        raise HTTPException(status_code=404, detail=f"Unknown artifact: {artifact_name}")
    media_type = "text/plain"
    if path.suffix == ".svg":
        media_type = "image/svg+xml"
    elif path.suffix == ".html":
        media_type = "text/html"
    elif path.suffix == ".md":
        media_type = "text/markdown"
    return FileResponse(path, media_type=media_type, filename=path.name)
