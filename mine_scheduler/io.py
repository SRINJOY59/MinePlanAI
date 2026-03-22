from __future__ import annotations

import csv
from pathlib import Path

from .models import Block, MaintenanceWindow


def load_blocks(path: Path) -> list[Block]:
    with path.open("r", newline="", encoding="utf-8") as handle:
        rows = csv.DictReader(handle)
        return [
            Block(
                block_id=row["block_id"].strip(),
                bench=row["bench"].strip(),
                tonnage=float(row["tonnage"]),
                ore_grade=float(row["ore_grade"]),
                priority=int(row["priority"]),
                drill_hours=int(row["drill_hours"]),
                blast_hours=int(row["blast_hours"]),
                haul_hours=int(row["haul_hours"]),
                centroid_x=float(row.get("centroid_x", 0.0) or 0.0),
                centroid_y=float(row.get("centroid_y", 0.0) or 0.0),
                centroid_z=float(row.get("centroid_z", 0.0) or 0.0),
                revenue=float(row.get("revenue", 0.0) or 0.0),
                cost=float(row.get("cost", 0.0) or 0.0),
                net_value=float(row.get("net_value", 0.0) or 0.0),
                value_density=float(row.get("value_density", 0.0) or 0.0),
            )
            for row in rows
        ]


def load_precedence(path: Path) -> list[tuple[str, str]]:
    with path.open("r", newline="", encoding="utf-8") as handle:
        rows = csv.DictReader(handle)
        return [
            (row["predecessor"].strip(), row["successor"].strip())
            for row in rows
        ]


def load_resources(path: Path) -> dict[str, int]:
    with path.open("r", newline="", encoding="utf-8") as handle:
        rows = csv.DictReader(handle)
        return {row["resource_type"].strip(): int(row["count"]) for row in rows}


def load_maintenance(path: Path) -> list[MaintenanceWindow]:
    with path.open("r", newline="", encoding="utf-8") as handle:
        rows = csv.DictReader(handle)
        return [
            MaintenanceWindow(
                resource_type=row["resource_type"].strip(),
                start_hour=int(row["start_hour"]),
                end_hour=int(row["end_hour"]),
                units_offline=int(row["units_offline"]),
            )
            for row in rows
        ]


def ensure_parent(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)


def write_schedule_csv(path: Path, tasks: list[dict[str, object]]) -> None:
    if not tasks:
        raise ValueError("No tasks were produced.")

    ensure_parent(path)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(tasks[0].keys()))
        writer.writeheader()
        writer.writerows(tasks)


def write_csv(path: Path, fieldnames: list[str], rows: list[dict[str, object]]) -> None:
    ensure_parent(path)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)
