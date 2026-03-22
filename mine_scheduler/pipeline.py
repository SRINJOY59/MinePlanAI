from __future__ import annotations

import csv
from pathlib import Path

from .economics import EconomicParameters
from .io import (
    load_blocks,
    load_maintenance,
    load_precedence,
    load_resources,
    write_csv,
    write_schedule_csv,
)
from .optimizer import optimize_block_order
from .prepare_web_data import prepare_web_dataset
from .reporting import write_report_html, write_report_markdown
from .scheduler import MineScheduler, summarize_solution
from .visualization import generate_gantt_html, generate_gantt_svg

DEFAULT_DRILLHOLES = Path("external_data/geomet_drillholes.csv")
DEFAULT_OPENMINES_CONFIG = Path("external_data/openmines-main/openmines/src/conf/north_pit_mine.json")
DEFAULT_OUTPUT_DIR = Path("data/web_derived")
DEFAULT_SCENARIOS = [
    {"name": "priority_heuristic", "solver": "heuristic", "strategy": "priority"},
    {"name": "grade_heuristic", "solver": "heuristic", "strategy": "grade"},
    {"name": "value_density_heuristic", "solver": "heuristic", "strategy": "value_density"},
    {"name": "net_value_heuristic", "solver": "heuristic", "strategy": "net_value"},
    {"name": "optimized_branch_and_bound", "solver": "branch_and_bound", "strategy": "optimized_bnb"},
]


def _serialize_schedule(tasks: list, blocks_by_id: dict) -> list[dict[str, object]]:
    return [
        {
            "block_id": task.block_id,
            "bench": task.bench,
            "task_type": task.task_type,
            "resource_type": task.resource_type,
            "start_hour": task.start_hour,
            "end_hour": task.end_hour,
            "duration_hours": task.end_hour - task.start_hour,
            "ore_grade": blocks_by_id[task.block_id].ore_grade,
            "tonnage": blocks_by_id[task.block_id].tonnage,
            "net_value": blocks_by_id[task.block_id].net_value,
        }
        for task in tasks
    ]


def _run_scenario(
    scenario: dict[str, str],
    blocks,
    precedence,
    resources,
    maintenance,
    output_dir: Path,
    economics: EconomicParameters,
    exact_solver_limit: int,
) -> dict[str, object]:
    blocks_by_id = {block.block_id: block for block in blocks}
    scheduler = MineScheduler(
        blocks=blocks,
        precedence=precedence,
        capacities=resources,
        maintenance=maintenance,
    )

    solver_metadata: dict[str, object] = {}
    forced_order: list[str] | None = None
    if scenario["strategy"] == "optimized_bnb":
        forced_order, solver_metadata = optimize_block_order(
            blocks=blocks,
            precedence=precedence,
            candidate_limit=exact_solver_limit,
            economics=economics,
        )
        tasks = scheduler.solve(strategy="priority", forced_order=forced_order)
    else:
        tasks = scheduler.solve(strategy=scenario["strategy"])

    summary = summarize_solution(tasks, blocks_by_id, economics)
    schedule_rows = _serialize_schedule(tasks, blocks_by_id)
    schedule_path = output_dir / "scenarios" / f"{scenario['name']}_schedule.csv"
    write_schedule_csv(schedule_path, schedule_rows)

    result = {
        "name": scenario["name"],
        "solver": scenario["solver"],
        "strategy": scenario["strategy"],
        "schedule_file": str(schedule_path),
        "task_rows": len(schedule_rows),
        "makespan_hours": int(summary["makespan_hours"]),
        "total_tonnage": int(summary["total_tonnage"]),
        "average_ore_grade": float(summary["average_ore_grade"]),
        "total_revenue": float(summary["total_revenue"]),
        "total_cost": float(summary["total_cost"]),
        "net_value": float(summary["net_value"]),
        "discounted_npv": float(summary["discounted_npv"]),
    }
    result.update(solver_metadata)
    return {
        "tasks": tasks,
        "summary": result,
    }


def _write_scenario_comparison(output_dir: Path, scenarios: list[dict[str, object]]) -> Path:
    path = output_dir / "scenario_comparison.csv"
    rows = []
    for scenario in scenarios:
        row = dict(scenario)
        if "candidate_blocks" in row:
            row["candidate_blocks"] = ",".join(str(item) for item in row["candidate_blocks"])
        rows.append(row)
    write_csv(
        path,
        [
            "name",
            "solver",
            "strategy",
            "task_rows",
            "makespan_hours",
            "total_tonnage",
            "average_ore_grade",
            "total_revenue",
            "total_cost",
            "net_value",
            "discounted_npv",
            "candidate_limit",
            "candidate_count",
            "visited_nodes",
            "best_surrogate_objective",
            "candidate_blocks",
            "schedule_file",
        ],
        rows,
    )
    return path


def run_web_pipeline(
    drillholes: Path = DEFAULT_DRILLHOLES,
    openmines_config: Path = DEFAULT_OPENMINES_CONFIG,
    output_dir: Path = DEFAULT_OUTPUT_DIR,
    bench_height: int = 100,
    max_blocks: int = 60,
    spatial_neighbors: int = 2,
    spatial_radius: float = 450.0,
    exact_solver_limit: int = 12,
) -> dict[str, object]:
    economics = EconomicParameters()
    preparation_result = prepare_web_dataset(
        drillholes=drillholes,
        openmines_config=openmines_config,
        output_dir=output_dir,
        bench_height=bench_height,
        max_blocks=max_blocks,
        spatial_neighbors=spatial_neighbors,
        spatial_radius=spatial_radius,
    )

    blocks = load_blocks(output_dir / "blocks.csv")
    precedence = load_precedence(output_dir / "precedence.csv")
    resources = load_resources(output_dir / "resources.csv")
    maintenance = load_maintenance(output_dir / "maintenance.csv")

    scenario_runs = [
        _run_scenario(
            scenario=scenario,
            blocks=blocks,
            precedence=precedence,
            resources=resources,
            maintenance=maintenance,
            output_dir=output_dir,
            economics=economics,
            exact_solver_limit=exact_solver_limit,
        )
        for scenario in DEFAULT_SCENARIOS
    ]
    scenario_summaries = [run["summary"] for run in scenario_runs]

    best_run = max(
        scenario_runs,
        key=lambda item: (
            item["summary"]["discounted_npv"],
            item["summary"]["net_value"],
            -item["summary"]["makespan_hours"],
        ),
    )
    best_summary = best_run["summary"]
    best_tasks = best_run["tasks"]

    final_schedule_rows = _serialize_schedule(best_tasks, {block.block_id: block for block in blocks})
    final_schedule_path = output_dir / "schedule_output.csv"
    write_schedule_csv(final_schedule_path, final_schedule_rows)

    scenario_comparison_path = _write_scenario_comparison(output_dir, scenario_summaries)

    gantt_svg_path = output_dir / "gantt_chart.svg"
    gantt_html_path = output_dir / "gantt_chart.html"
    generate_gantt_svg(best_tasks, gantt_svg_path, "MinePlan AI Schedule Gantt Chart")
    generate_gantt_html(gantt_svg_path, gantt_html_path, "MinePlan AI Schedule Gantt Chart")

    report_md_path = output_dir / "project_report.md"
    report_html_path = output_dir / "project_report.html"
    artifacts = {
        "gantt_svg": str(gantt_svg_path),
        "gantt_html": str(gantt_html_path),
        "report_markdown": str(report_md_path),
        "report_html": str(report_html_path),
        "scenario_comparison_csv": str(scenario_comparison_path),
        "schedule_csv": str(final_schedule_path),
    }
    write_report_markdown(
        report_md_path,
        project_name="MinePlan AI",
        best_scenario=best_summary,
        scenarios=scenario_summaries,
        artifacts=artifacts,
        preparation=preparation_result,
    )
    write_report_html(
        report_html_path,
        project_name="MinePlan AI",
        best_scenario=best_summary,
        scenarios=scenario_summaries,
        artifacts=artifacts,
        preparation=preparation_result,
    )

    return {
        "preparation": preparation_result,
        "schedule": {
            "task_rows": best_summary["task_rows"],
            "makespan_hours": best_summary["makespan_hours"],
            "total_tonnage": best_summary["total_tonnage"],
            "average_ore_grade": best_summary["average_ore_grade"],
            "total_revenue": best_summary["total_revenue"],
            "total_cost": best_summary["total_cost"],
            "net_value": best_summary["net_value"],
            "discounted_npv": best_summary["discounted_npv"],
            "output_file": str(final_schedule_path),
        },
        "best_scenario": best_summary,
        "scenario_comparison": scenario_summaries,
        "artifacts": artifacts,
    }


def read_csv_rows(path: Path, limit: int | None = None) -> list[dict[str, str]]:
    if not path.exists():
        return []

    with path.open("r", newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        rows = list(reader)

    if limit is None:
        return rows
    return rows[:limit]


def count_csv_rows(path: Path) -> int:
    if not path.exists():
        return 0
    with path.open("r", newline="", encoding="utf-8") as handle:
        reader = csv.reader(handle)
        next(reader, None)
        return sum(1 for _ in reader)


def get_dashboard_snapshot(output_dir: Path = DEFAULT_OUTPUT_DIR) -> dict[str, object]:
    files = {
        "block_model": output_dir / "block_model.csv",
        "ore_blocks": output_dir / "ore_blocks.csv",
        "block_precedence": output_dir / "block_precedence.csv",
        "tasks": output_dir / "tasks.csv",
        "task_precedence": output_dir / "task_precedence.csv",
        "maintenance": output_dir / "maintenance.csv",
        "resources": output_dir / "resources.csv",
        "schedule": output_dir / "schedule_output.csv",
        "scenario_comparison": output_dir / "scenario_comparison.csv",
    }

    counts = {name: count_csv_rows(path) for name, path in files.items()}
    resource_rows = read_csv_rows(files["resources"])
    schedule_rows = read_csv_rows(files["schedule"], limit=12)
    task_rows = read_csv_rows(files["tasks"], limit=12)
    block_rows = read_csv_rows(files["block_model"], limit=12)
    maintenance_rows = read_csv_rows(files["maintenance"], limit=12)
    scenario_rows = read_csv_rows(files["scenario_comparison"], limit=12)

    schedule_metrics = {
        "makespan_hours": 0,
        "net_value": 0,
        "discounted_npv": 0,
    }
    if scenario_rows:
        best = max(
            scenario_rows,
            key=lambda row: float(row["discounted_npv"]),
        )
        schedule_metrics = {
            "makespan_hours": int(float(best["makespan_hours"])),
            "net_value": int(float(best["net_value"])),
            "discounted_npv": int(float(best["discounted_npv"])),
        }

    artifacts = {
        "gantt_svg": str(output_dir / "gantt_chart.svg"),
        "gantt_html": str(output_dir / "gantt_chart.html"),
        "report_markdown": str(output_dir / "project_report.md"),
        "report_html": str(output_dir / "project_report.html"),
    }

    return {
        "counts": counts,
        "resources": resource_rows,
        "previews": {
            "block_model": block_rows,
            "tasks": task_rows,
            "schedule": schedule_rows,
            "maintenance": maintenance_rows,
            "scenario_comparison": scenario_rows,
        },
        "schedule_metrics": schedule_metrics,
        "sources": {
            "drillholes": str(DEFAULT_DRILLHOLES),
            "openmines_config": str(DEFAULT_OPENMINES_CONFIG),
            "output_dir": str(output_dir),
        },
        "artifacts": artifacts,
    }
