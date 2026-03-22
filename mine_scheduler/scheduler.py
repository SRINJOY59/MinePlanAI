from __future__ import annotations

from collections import defaultdict

from .economics import EconomicParameters, discounted_value
from .models import Block, MaintenanceWindow, SchedulerConfig, TaskWindow


class CapacityCalendar:
    def __init__(
        self,
        capacities: dict[str, int],
        maintenance: list[MaintenanceWindow],
    ) -> None:
        self.capacities = capacities
        self.usage: dict[str, dict[int, int]] = defaultdict(lambda: defaultdict(int))
        self.maintenance: dict[str, dict[int, int]] = defaultdict(lambda: defaultdict(int))

        for window in maintenance:
            for hour in range(window.start_hour, window.end_hour):
                self.maintenance[window.resource_type][hour] += window.units_offline

    def available(self, resource_type: str, hour: int) -> int:
        base = self.capacities.get(resource_type, 0)
        offline = self.maintenance[resource_type].get(hour, 0)
        return max(base - offline, 0)

    def can_place(self, resource_type: str, start_hour: int, duration: int) -> bool:
        for hour in range(start_hour, start_hour + duration):
            if self.usage[resource_type][hour] >= self.available(resource_type, hour):
                return False
        return True

    def place(self, resource_type: str, start_hour: int, duration: int) -> None:
        for hour in range(start_hour, start_hour + duration):
            self.usage[resource_type][hour] += 1


class MineScheduler:
    def __init__(
        self,
        blocks: list[Block],
        precedence: list[tuple[str, str]],
        capacities: dict[str, int],
        maintenance: list[MaintenanceWindow],
        config: SchedulerConfig | None = None,
    ) -> None:
        self.blocks = {block.block_id: block for block in blocks}
        self.predecessors: dict[str, set[str]] = defaultdict(set)
        self.successors: dict[str, set[str]] = defaultdict(set)
        for predecessor, successor in precedence:
            self.predecessors[successor].add(predecessor)
            self.successors[predecessor].add(successor)

        self.capacities = capacities
        self.maintenance = maintenance
        self.config = config or SchedulerConfig()
        self._reset_state()

    def _reset_state(self) -> None:
        self.calendar = CapacityCalendar(self.capacities, self.maintenance)
        self.task_windows: list[TaskWindow] = []
        self.block_completion: dict[str, int] = {}
        self.bench_reentry_ready: dict[str, int] = defaultdict(int)

    def solve(
        self,
        strategy: str = "priority",
        forced_order: list[str] | None = None,
    ) -> list[TaskWindow]:
        self._reset_state()
        unscheduled = set(self.blocks)
        order_rank = {block_id: index for index, block_id in enumerate(forced_order or [])}

        while unscheduled:
            ready = [
                self.blocks[block_id]
                for block_id in unscheduled
                if self.predecessors[block_id].issubset(self.block_completion)
            ]
            if not ready:
                missing = {
                    block_id: sorted(self.predecessors[block_id] - self.block_completion.keys())
                    for block_id in unscheduled
                }
                raise ValueError(f"No schedulable blocks remain. Cyclic or broken precedence: {missing}")

            block = self._select_block(ready, strategy=strategy, order_rank=order_rank)
            self._schedule_block(block)
            unscheduled.remove(block.block_id)

        return sorted(self.task_windows, key=lambda item: (item.start_hour, item.block_id, item.task_type))

    def _select_block(
        self,
        ready: list[Block],
        strategy: str,
        order_rank: dict[str, int],
    ) -> Block:
        if order_rank:
            ready.sort(
                key=lambda block: (
                    order_rank.get(block.block_id, len(order_rank) + 10_000),
                    -block.priority,
                    -block.net_value,
                )
            )
            return ready[0]

        ready.sort(key=lambda block: self._block_score(block, strategy), reverse=True)
        return ready[0]

    def _block_score(self, block: Block, strategy: str) -> tuple[float, float, float, float]:
        if strategy == "grade":
            return (block.ore_grade, block.value_density, block.net_value, block.tonnage)
        if strategy == "value_density":
            return (block.value_density, block.net_value, block.ore_grade, block.tonnage)
        if strategy == "net_value":
            return (block.net_value, block.value_density, block.ore_grade, block.tonnage)
        if strategy == "tonnage":
            return (block.tonnage, block.net_value, block.ore_grade, block.priority)
        return (block.priority, block.net_value, block.ore_grade, block.tonnage)

    def _schedule_block(self, block: Block) -> None:
        predecessor_ready = 0
        if self.predecessors[block.block_id]:
            predecessor_ready = max(
                self.block_completion[predecessor]
                for predecessor in self.predecessors[block.block_id]
            )

        drill_start = self._find_earliest_start(
            resource_type="DRILL",
            duration=block.drill_hours,
            earliest_start=max(predecessor_ready, self.bench_reentry_ready[block.bench]),
        )
        drill_end = drill_start + block.drill_hours
        self._commit_task(block, "drill", "DRILL", drill_start, drill_end)

        blast_start = self._find_earliest_start(
            resource_type="BLAST",
            duration=block.blast_hours,
            earliest_start=max(drill_end, self.bench_reentry_ready[block.bench]),
        )
        blast_end = blast_start + block.blast_hours
        self._commit_task(block, "blast", "BLAST", blast_start, blast_end)
        self.bench_reentry_ready[block.bench] = blast_end + self.config.blast_reentry_gap_hours

        haul_start = self._find_earliest_start(
            resource_type="HAUL",
            duration=block.haul_hours,
            earliest_start=blast_end + self.config.post_blast_wait_hours,
        )
        haul_end = haul_start + block.haul_hours
        self._commit_task(block, "haul", "HAUL", haul_start, haul_end)
        self.block_completion[block.block_id] = haul_end

    def _find_earliest_start(self, resource_type: str, duration: int, earliest_start: int) -> int:
        for start_hour in range(earliest_start, self.config.max_search_hour + 1):
            if self.calendar.can_place(resource_type, start_hour, duration):
                return start_hour
        raise ValueError(
            f"Unable to place task for resource {resource_type} within {self.config.max_search_hour} hours."
        )

    def _commit_task(
        self,
        block: Block,
        task_type: str,
        resource_type: str,
        start_hour: int,
        end_hour: int,
    ) -> None:
        self.calendar.place(resource_type, start_hour, end_hour - start_hour)
        self.task_windows.append(
            TaskWindow(
                block_id=block.block_id,
                task_type=task_type,
                resource_type=resource_type,
                start_hour=start_hour,
                end_hour=end_hour,
                bench=block.bench,
            )
        )


def summarize_solution(
    tasks: list[TaskWindow],
    blocks: dict[str, Block],
    economics: EconomicParameters | None = None,
) -> dict[str, float]:
    settings = economics or EconomicParameters()
    if not tasks:
        return {
            "makespan_hours": 0.0,
            "total_tonnage": 0.0,
            "average_ore_grade": 0.0,
            "total_revenue": 0.0,
            "total_cost": 0.0,
            "net_value": 0.0,
            "discounted_npv": 0.0,
        }

    makespan = max(task.end_hour for task in tasks)
    haul_tasks = [task for task in tasks if task.task_type == "haul"]
    total_tonnage = sum(blocks[task.block_id].tonnage for task in haul_tasks)
    avg_grade = (
        sum(blocks[task.block_id].tonnage * blocks[task.block_id].ore_grade for task in haul_tasks)
        / total_tonnage
        if total_tonnage
        else 0.0
    )
    total_revenue = sum(blocks[task.block_id].revenue for task in haul_tasks)
    total_cost = sum(blocks[task.block_id].cost for task in haul_tasks)
    total_net = sum(blocks[task.block_id].net_value for task in haul_tasks)
    discounted_npv = sum(
        discounted_value(
            blocks[task.block_id].net_value,
            task.end_hour,
            settings.discount_rate_per_hour,
        )
        for task in haul_tasks
    )
    return {
        "makespan_hours": float(makespan),
        "total_tonnage": float(total_tonnage),
        "average_ore_grade": round(avg_grade, 4),
        "total_revenue": round(total_revenue, 2),
        "total_cost": round(total_cost, 2),
        "net_value": round(total_net, 2),
        "discounted_npv": round(discounted_npv, 2),
    }
