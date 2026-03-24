from __future__ import annotations

import argparse
import csv
import json
import math
from collections import defaultdict
from pathlib import Path

from .economics import compute_block_economics
from .io import write_csv

ORE_CUTOFF_CU_PERCENT = 0.8


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Convert public web datasets into scheduler-ready CSV files."
    )
    parser.add_argument(
        "--drillholes",
        type=Path,
        default=Path("external_data/geomet_drillholes.csv"),
        help="Zenodo GeoMet drillhole CSV.",
    )
    parser.add_argument(
        "--openmines-config",
        type=Path,
        default=Path("external_data/openmines-main/openmines/src/conf/north_pit_mine.json"),
        help="OpenMines North Pit JSON configuration.",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("data/web_derived"),
        help="Directory where converted CSV files are written.",
    )
    parser.add_argument(
        "--bench-height",
        type=int,
        default=15,
        help="Bench height (10-30 m) used to aggregate drillhole samples into block-like units.",
    )
    parser.add_argument(
        "--max-blocks",
        type=int,
        default=60,
        help="Keep the highest-value derived blocks to keep the prototype schedule tractable.",
    )
    parser.add_argument(
        "--spatial-neighbors",
        type=int,
        default=2,
        help="Number of nearest upper-bench neighbors used for spatial precedence generation.",
    )
    parser.add_argument(
        "--spatial-radius",
        type=float,
        default=450.0,
        help="Maximum XY distance for spatial precedence arcs.",
    )
    return parser


def load_rows(path: Path) -> list[dict[str, str]]:
    with path.open("r", newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def derive_block_model(rows: list[dict[str, str]], bench_height: int, max_blocks: int) -> list[dict[str, object]]:
    grouped: dict[tuple[str, int], list[dict[str, str]]] = defaultdict(list)
    for row in rows:
        bench = int(math.floor(float(row["Z"]) / bench_height) * bench_height)
        grouped[(row["HOLEID"].strip(), bench)].append(row)

    block_model: list[dict[str, object]] = []
    for (hole_id, bench), samples in grouped.items():
        cu_values = [float(sample["Cu ppm"]) for sample in samples]
        ag_values = [float(sample["Ag ppm"]) for sample in samples]
        xs = [float(sample["X"]) for sample in samples]
        ys = [float(sample["Y"]) for sample in samples]
        zs = [float(sample["Z"]) for sample in samples]

        sample_count = len(samples)
        mean_cu_ppm = sum(cu_values) / sample_count
        mean_ag_ppm = sum(ag_values) / sample_count
        ore_grade = round(mean_cu_ppm / 10000.0, 4)

        # Inference: each drillhole sample is treated as a small regularized mining unit.
        tonnage = sample_count * 2500.0
        drill_hours = max(1, math.ceil(sample_count / 2))
        blast_hours = max(1, math.ceil(sample_count / 4))
        haul_hours = max(1, math.ceil(tonnage / 3500.0))
        economics = compute_block_economics(
            tonnage=tonnage,
            ore_grade=ore_grade,
            drill_hours=drill_hours,
            blast_hours=blast_hours,
            haul_hours=haul_hours,
        )

        block_model.append(
            {
                "block_id": f"H{hole_id}_B{bench:+04d}".replace("+", "P").replace("-", "M"),
                "hole_id": hole_id,
                "bench": str(bench),
                "centroid_x": round(sum(xs) / sample_count, 3),
                "centroid_y": round(sum(ys) / sample_count, 3),
                "centroid_z": round(sum(zs) / sample_count, 3),
                "samples": sample_count,
                "tonnage": round(tonnage, 2),
                "ore_grade": ore_grade,
                "material_type": "ORE" if ore_grade >= ORE_CUTOFF_CU_PERCENT else "WASTE",
                "priority_signal": mean_cu_ppm * tonnage,
                "mean_ag_ppm": round(mean_ag_ppm, 2),
                "drill_hours": drill_hours,
                "blast_hours": blast_hours,
                "haul_hours": haul_hours,
                "revenue": economics["revenue"],
                "cost": economics["cost"],
                "net_value": economics["net_value"],
                "value_density": economics["value_density"],
                "source_dataset": "Zenodo GeoMet 7051975",
            }
        )

    block_model.sort(
        key=lambda item: (item["priority_signal"], item["ore_grade"], item["tonnage"]),
        reverse=True,
    )
    block_model = block_model[:max_blocks]

    scores = [float(block["priority_signal"]) for block in block_model]
    min_score = min(scores)
    max_score = max(scores)
    score_span = max(max_score - min_score, 1.0)

    for block in block_model:
        normalized = (float(block["priority_signal"]) - min_score) / score_span
        block["priority"] = 1 + int(normalized * 4)

    return block_model


def derive_ore_blocks(block_model: list[dict[str, object]]) -> list[dict[str, object]]:
    ore_blocks = [block for block in block_model if str(block["material_type"]) == "ORE"]
    return sorted(
        ore_blocks,
        key=lambda item: (int(item["priority"]), float(item["ore_grade"]), float(item["tonnage"])),
        reverse=True,
    )


def derive_block_precedence(blocks: list[dict[str, object]]) -> list[dict[str, object]]:
    return derive_block_precedence_with_spatial_context(blocks, spatial_neighbors=2, spatial_radius=450.0)


def derive_block_precedence_with_spatial_context(
    blocks: list[dict[str, object]],
    spatial_neighbors: int,
    spatial_radius: float,
) -> list[dict[str, object]]:
    precedence_by_pair: dict[tuple[str, str], dict[str, object]] = {}
    by_hole: dict[str, list[dict[str, object]]] = defaultdict(list)
    by_bench: dict[int, list[dict[str, object]]] = defaultdict(list)

    for block in blocks:
        by_hole[str(block["hole_id"])].append(block)
        by_bench[int(str(block["bench"]))].append(block)

    def register_arc(
        predecessor: dict[str, object],
        successor: dict[str, object],
        reason: str,
        distance_xy: float | None = None,
    ) -> None:
        if predecessor["block_id"] == successor["block_id"]:
            return
        key = (str(predecessor["block_id"]), str(successor["block_id"]))
        if key in precedence_by_pair:
            return
        precedence_by_pair[key] = {
            "predecessor": str(predecessor["block_id"]),
            "successor": str(successor["block_id"]),
            "reason": reason,
            "vertical_drop": int(str(predecessor["bench"])) - int(str(successor["bench"])),
            "distance_xy": round(distance_xy, 2) if distance_xy is not None else "",
        }

    for hole_blocks in by_hole.values():
        hole_blocks.sort(key=lambda item: int(str(item["bench"])), reverse=True)
        for upper, lower in zip(hole_blocks, hole_blocks[1:]):
            register_arc(upper, lower, "same_hole_top_down_bench_precedence")

    sorted_benches = sorted(by_bench)
    for lower in blocks:
        lower_bench = int(str(lower["bench"]))
        upper_benches = [bench for bench in sorted_benches if bench > lower_bench]
        if not upper_benches:
            continue

        nearest_upper_bench = min(upper_benches)
        candidate_predecessors = []
        for upper in by_bench[nearest_upper_bench]:
            if upper["hole_id"] == lower["hole_id"]:
                continue
            dx = float(upper["centroid_x"]) - float(lower["centroid_x"])
            dy = float(upper["centroid_y"]) - float(lower["centroid_y"])
            distance_xy = math.sqrt((dx * dx) + (dy * dy))
            if distance_xy <= spatial_radius:
                candidate_predecessors.append((distance_xy, upper))

        for distance_xy, predecessor in sorted(candidate_predecessors, key=lambda item: item[0])[:spatial_neighbors]:
            register_arc(predecessor, lower, "spatial_cover_precedence", distance_xy=distance_xy)

    return sorted(
        precedence_by_pair.values(),
        key=lambda item: (item["predecessor"], item["successor"]),
    )


def derive_resources(openmines_config: Path) -> list[dict[str, object]]:
    config = json.loads(openmines_config.read_text(encoding="utf-8"))

    truck_count = sum(int(truck["count"]) for truck in config["charging_site"]["trucks"])
    load_site_count = len(config["load_sites"])

    # Inference: the public OpenMines config gives actual haulage assets and working faces,
    # but it does not expose drilling or blasting crew counts.
    drill_count = load_site_count
    blast_count = max(1, load_site_count // 2)

    return [
        {"resource_type": "DRILL", "count": drill_count},
        {"resource_type": "BLAST", "count": blast_count},
        {"resource_type": "HAUL", "count": truck_count},
    ]


def derive_tasks(blocks: list[dict[str, object]]) -> list[dict[str, object]]:
    tasks: list[dict[str, object]] = []
    for block in blocks:
        for task_type, resource_type, duration_key in (
            ("drill", "DRILL", "drill_hours"),
            ("blast", "BLAST", "blast_hours"),
            ("haul", "HAUL", "haul_hours"),
        ):
            tasks.append(
                {
                    "task_id": f"{block['block_id']}::{task_type}",
                    "block_id": block["block_id"],
                    "bench": block["bench"],
                    "task_type": task_type,
                    "resource_type": resource_type,
                    "duration_hours": block[duration_key],
                    "priority": block["priority"],
                    "tonnage": block["tonnage"],
                    "ore_grade": block["ore_grade"],
                }
            )
    return tasks


def derive_task_precedence(
    blocks: list[dict[str, object]],
    block_precedence: list[dict[str, object]],
) -> list[dict[str, object]]:
    block_lookup = {str(block["block_id"]): block for block in blocks}
    task_precedence: list[dict[str, object]] = []

    for block in blocks:
        block_id = str(block["block_id"])
        task_precedence.extend(
            [
                {
                    "predecessor_task": f"{block_id}::drill",
                    "successor_task": f"{block_id}::blast",
                    "reason": "within_block_sequence",
                },
                {
                    "predecessor_task": f"{block_id}::blast",
                    "successor_task": f"{block_id}::haul",
                    "reason": "within_block_sequence",
                },
            ]
        )

    for arc in block_precedence:
        predecessor = str(arc["predecessor"])
        successor = str(arc["successor"])
        if predecessor in block_lookup and successor in block_lookup:
            task_precedence.append(
                {
                    "predecessor_task": f"{predecessor}::haul",
                    "successor_task": f"{successor}::drill",
                    "reason": "cross_block_bench_precedence",
                }
            )

    return task_precedence


def estimate_horizon_hours(blocks: list[dict[str, object]], resources: list[dict[str, object]]) -> int:
    counts = {str(item["resource_type"]): int(item["count"]) for item in resources}
    drill_load = sum(int(block["drill_hours"]) for block in blocks) / max(counts["DRILL"], 1)
    blast_load = sum(int(block["blast_hours"]) for block in blocks) / max(counts["BLAST"], 1)
    haul_load = sum(int(block["haul_hours"]) for block in blocks) / max(counts["HAUL"], 1)
    return max(240, int(math.ceil(max(drill_load, blast_load, haul_load) + 120)))


def derive_maintenance(resources: list[dict[str, object]], horizon_hours: int) -> list[dict[str, object]]:
    counts = {str(item["resource_type"]): int(item["count"]) for item in resources}
    windows: list[dict[str, object]] = []

    for start in range(18, horizon_hours, 48):
        windows.append(
            {
                "resource_type": "DRILL",
                "start_hour": start,
                "end_hour": min(start + 4, horizon_hours),
                "units_offline": 1,
                "reason": "preventive_service",
                "cycle_hours": 48,
            }
        )

    for start in range(24, horizon_hours, 72):
        windows.append(
            {
                "resource_type": "BLAST",
                "start_hour": start,
                "end_hour": min(start + 3, horizon_hours),
                "units_offline": 1,
                "reason": "explosives_handling_and_service",
                "cycle_hours": 72,
            }
        )

    haul_units_offline = max(1, math.ceil(counts["HAUL"] * 0.1))
    for start in range(12, horizon_hours, 24):
        windows.append(
            {
                "resource_type": "HAUL",
                "start_hour": start,
                "end_hour": min(start + 4, horizon_hours),
                "units_offline": haul_units_offline,
                "reason": "fleet_service_rotation",
                "cycle_hours": 24,
            }
        )

    return windows


def write_dataset(
    output_dir: Path,
    block_model: list[dict[str, object]],
    ore_blocks: list[dict[str, object]],
    block_precedence: list[dict[str, object]],
    resources: list[dict[str, object]],
    tasks: list[dict[str, object]],
    task_precedence: list[dict[str, object]],
    maintenance: list[dict[str, object]],
) -> None:
    write_csv(
        output_dir / "block_model.csv",
        [
            "block_id",
            "hole_id",
            "bench",
            "centroid_x",
            "centroid_y",
            "centroid_z",
            "samples",
            "tonnage",
            "ore_grade",
            "material_type",
            "mean_ag_ppm",
            "priority",
            "priority_signal",
            "drill_hours",
            "blast_hours",
            "haul_hours",
            "revenue",
            "cost",
            "net_value",
            "value_density",
            "source_dataset",
        ],
        block_model,
    )
    write_csv(
        output_dir / "ore_blocks.csv",
        [
            "block_id",
            "hole_id",
            "bench",
            "tonnage",
            "ore_grade",
            "priority",
            "drill_hours",
            "blast_hours",
            "haul_hours",
            "centroid_x",
            "centroid_y",
            "centroid_z",
            "revenue",
            "cost",
            "net_value",
            "value_density",
        ],
        [
            {
                "block_id": block["block_id"],
                "hole_id": block["hole_id"],
                "bench": block["bench"],
                "tonnage": block["tonnage"],
                "ore_grade": block["ore_grade"],
                "priority": block["priority"],
                "drill_hours": block["drill_hours"],
                "blast_hours": block["blast_hours"],
                "haul_hours": block["haul_hours"],
                "centroid_x": block["centroid_x"],
                "centroid_y": block["centroid_y"],
                "centroid_z": block["centroid_z"],
                "revenue": block["revenue"],
                "cost": block["cost"],
                "net_value": block["net_value"],
                "value_density": block["value_density"],
            }
            for block in ore_blocks
        ],
    )
    write_csv(
        output_dir / "blocks.csv",
        [
            "block_id",
            "bench",
            "tonnage",
            "ore_grade",
            "priority",
            "drill_hours",
            "blast_hours",
            "haul_hours",
            "centroid_x",
            "centroid_y",
            "centroid_z",
            "revenue",
            "cost",
            "net_value",
            "value_density",
        ],
        [
            {
                "block_id": block["block_id"],
                "bench": block["bench"],
                "tonnage": block["tonnage"],
                "ore_grade": block["ore_grade"],
                "priority": block["priority"],
                "drill_hours": block["drill_hours"],
                "blast_hours": block["blast_hours"],
                "haul_hours": block["haul_hours"],
                "centroid_x": block["centroid_x"],
                "centroid_y": block["centroid_y"],
                "centroid_z": block["centroid_z"],
                "revenue": block["revenue"],
                "cost": block["cost"],
                "net_value": block["net_value"],
                "value_density": block["value_density"],
            }
            for block in ore_blocks
        ],
    )
    write_csv(
        output_dir / "block_precedence.csv",
        ["predecessor", "successor", "reason", "vertical_drop", "distance_xy"],
        block_precedence,
    )
    write_csv(
        output_dir / "precedence.csv",
        ["predecessor", "successor"],
        [
            {
                "predecessor": arc["predecessor"],
                "successor": arc["successor"],
            }
            for arc in block_precedence
        ],
    )
    write_csv(output_dir / "resources.csv", ["resource_type", "count"], resources)
    write_csv(
        output_dir / "tasks.csv",
        [
            "task_id",
            "block_id",
            "bench",
            "task_type",
            "resource_type",
            "duration_hours",
            "priority",
            "tonnage",
            "ore_grade",
        ],
        tasks,
    )
    write_csv(
        output_dir / "task_precedence.csv",
        ["predecessor_task", "successor_task", "reason"],
        task_precedence,
    )
    write_csv(
        output_dir / "maintenance.csv",
        ["resource_type", "start_hour", "end_hour", "units_offline", "reason", "cycle_hours"],
        maintenance,
    )
    write_csv(
        output_dir / "metadata.csv",
        [
            "block_id",
            "hole_id",
            "bench",
            "material_type",
            "samples",
            "tonnage",
            "ore_grade",
            "mean_ag_ppm",
            "priority",
            "priority_signal",
            "revenue",
            "cost",
            "net_value",
            "value_density",
        ],
        [
            {
                "block_id": block["block_id"],
                "hole_id": block["hole_id"],
                "bench": block["bench"],
                "material_type": block["material_type"],
                "samples": block["samples"],
                "tonnage": block["tonnage"],
                "ore_grade": block["ore_grade"],
                "mean_ag_ppm": block["mean_ag_ppm"],
                "priority": block["priority"],
                "priority_signal": round(float(block["priority_signal"]), 2),
                "revenue": block["revenue"],
                "cost": block["cost"],
                "net_value": block["net_value"],
                "value_density": block["value_density"],
            }
            for block in block_model
        ],
    )


def prepare_web_dataset(
    drillholes: Path,
    openmines_config: Path,
    output_dir: Path,
    bench_height: int,
    max_blocks: int,
    spatial_neighbors: int,
    spatial_radius: float,
) -> dict[str, object]:
    rows = load_rows(drillholes)
    block_model = derive_block_model(rows, bench_height=bench_height, max_blocks=max_blocks)
    ore_blocks = derive_ore_blocks(block_model)
    block_precedence = derive_block_precedence_with_spatial_context(
        ore_blocks,
        spatial_neighbors=spatial_neighbors,
        spatial_radius=spatial_radius,
    )
    resources = derive_resources(openmines_config)
    tasks = derive_tasks(ore_blocks)
    task_precedence = derive_task_precedence(ore_blocks, block_precedence)
    horizon_hours = estimate_horizon_hours(ore_blocks, resources)
    maintenance = derive_maintenance(resources, horizon_hours)

    write_dataset(
        output_dir,
        block_model=block_model,
        ore_blocks=ore_blocks,
        block_precedence=block_precedence,
        resources=resources,
        tasks=tasks,
        task_precedence=task_precedence,
        maintenance=maintenance,
    )

    return {
        "output_dir": str(output_dir),
        "block_model_rows": len(block_model),
        "ore_blocks": len(ore_blocks),
        "block_precedence_arcs": len(block_precedence),
        "task_rows": len(tasks),
        "task_precedence_arcs": len(task_precedence),
        "maintenance_windows": len(maintenance),
        "resource_summary": {str(item["resource_type"]): int(item["count"]) for item in resources},
        "spatial_neighbors": spatial_neighbors,
        "spatial_radius": spatial_radius,
    }


def main() -> None:
    args = build_parser().parse_args()
    result = prepare_web_dataset(
        drillholes=args.drillholes,
        openmines_config=args.openmines_config,
        output_dir=args.output_dir,
        bench_height=args.bench_height,
        max_blocks=args.max_blocks,
        spatial_neighbors=args.spatial_neighbors,
        spatial_radius=args.spatial_radius,
    )

    print(f"Wrote converted dataset to: {result['output_dir']}")
    print(f"Block model rows: {result['block_model_rows']}")
    print(f"Ore blocks: {result['ore_blocks']}")
    print(f"Block precedence arcs: {result['block_precedence_arcs']}")
    print(f"Task rows: {result['task_rows']}")
    print(f"Task precedence arcs: {result['task_precedence_arcs']}")
    print(f"Maintenance windows: {result['maintenance_windows']}")
    print(
        "Resources: "
        + ", ".join(
            f"{resource_type}={count}"
            for resource_type, count in dict(result["resource_summary"]).items()
        )
    )


if __name__ == "__main__":
    main()
