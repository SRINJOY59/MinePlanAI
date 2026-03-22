from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Block:
    block_id: str
    bench: str
    tonnage: float
    ore_grade: float
    priority: int
    drill_hours: int
    blast_hours: int
    haul_hours: int
    centroid_x: float = 0.0
    centroid_y: float = 0.0
    centroid_z: float = 0.0
    revenue: float = 0.0
    cost: float = 0.0
    net_value: float = 0.0
    value_density: float = 0.0


@dataclass(frozen=True)
class MaintenanceWindow:
    resource_type: str
    start_hour: int
    end_hour: int
    units_offline: int


@dataclass(frozen=True)
class TaskWindow:
    block_id: str
    task_type: str
    resource_type: str
    start_hour: int
    end_hour: int
    bench: str


@dataclass(frozen=True)
class SchedulerConfig:
    blast_reentry_gap_hours: int = 2
    post_blast_wait_hours: int = 1
    max_search_hour: int = 24 * 365
