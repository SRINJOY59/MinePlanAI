from __future__ import annotations

import argparse
from pathlib import Path

from .io import load_blocks, load_maintenance, load_precedence, load_resources, write_schedule_csv
from .scheduler import MineScheduler, summarize_solution


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Generate a feasible open-pit mine schedule using a constrained heuristic."
    )
    parser.add_argument("--blocks", type=Path, default=Path("data/blocks.csv"))
    parser.add_argument("--precedence", type=Path, default=Path("data/precedence.csv"))
    parser.add_argument("--resources", type=Path, default=Path("data/resources.csv"))
    parser.add_argument("--maintenance", type=Path, default=Path("data/maintenance.csv"))
    parser.add_argument("--output", type=Path, default=Path("schedule_output.csv"))
    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()

    blocks = load_blocks(args.blocks)
    precedence = load_precedence(args.precedence)
    resources = load_resources(args.resources)
    maintenance = load_maintenance(args.maintenance)

    scheduler = MineScheduler(
        blocks=blocks,
        precedence=precedence,
        capacities=resources,
        maintenance=maintenance,
    )
    tasks = scheduler.solve()

    output_rows: list[dict[str, object]] = [
        {
            "block_id": task.block_id,
            "bench": task.bench,
            "task_type": task.task_type,
            "resource_type": task.resource_type,
            "start_hour": task.start_hour,
            "end_hour": task.end_hour,
            "duration_hours": task.end_hour - task.start_hour,
        }
        for task in tasks
    ]
    write_schedule_csv(args.output, output_rows)

    summary = summarize_solution(tasks, {block.block_id: block for block in blocks})
    print(f"Schedule written to: {args.output}")
    print(f"Makespan (hours): {int(summary['makespan_hours'])}")
    print(f"Total tonnage hauled: {summary['total_tonnage']:.0f}")
    print(f"Average ore grade: {summary['average_ore_grade']:.4f}")


if __name__ == "__main__":
    main()

