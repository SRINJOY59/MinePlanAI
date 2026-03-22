from __future__ import annotations

from collections import defaultdict

from .economics import EconomicParameters, discounted_value
from .models import Block


def _economic_duration(block: Block) -> int:
    return block.drill_hours + block.blast_hours + block.haul_hours


def optimize_block_order(
    blocks: list[Block],
    precedence: list[tuple[str, str]],
    candidate_limit: int = 12,
    economics: EconomicParameters | None = None,
    fallback_strategy: str = "value_density",
) -> tuple[list[str], dict[str, object]]:
    settings = economics or EconomicParameters()
    blocks_by_id = {block.block_id: block for block in blocks}

    ranked = sorted(
        blocks,
        key=lambda block: (block.net_value, block.value_density, block.ore_grade, block.tonnage),
        reverse=True,
    )
    candidate_ids = [block.block_id for block in ranked[:candidate_limit]]
    candidate_set = set(candidate_ids)

    candidate_predecessors: dict[str, set[str]] = defaultdict(set)
    candidate_successors: dict[str, set[str]] = defaultdict(set)
    for predecessor, successor in precedence:
        if predecessor in candidate_set and successor in candidate_set:
            candidate_predecessors[successor].add(predecessor)
            candidate_successors[predecessor].add(successor)

    ready = sorted(
        [block_id for block_id in candidate_ids if not candidate_predecessors[block_id]],
        key=lambda block_id: blocks_by_id[block_id].net_value,
        reverse=True,
    )

    best_sequence: list[str] = []
    best_score = float("-inf")
    visited_nodes = 0

    def optimistic_bound(remaining: list[str], current_time: int, current_score: float) -> float:
        time_cursor = current_time
        bound = current_score
        for block_id in sorted(
            remaining,
            key=lambda item: blocks_by_id[item].net_value,
            reverse=True,
        ):
            block = blocks_by_id[block_id]
            time_cursor += max(1, _economic_duration(block))
            contribution = discounted_value(
                block.net_value,
                time_cursor,
                settings.discount_rate_per_hour,
            )
            if contribution > 0:
                bound += contribution
        return bound

    def search(
        sequence: list[str],
        ready_nodes: list[str],
        remaining: set[str],
        current_time: int,
        current_score: float,
    ) -> None:
        nonlocal best_sequence, best_score, visited_nodes
        visited_nodes += 1

        if not remaining:
            if current_score > best_score:
                best_score = current_score
                best_sequence = list(sequence)
            return

        if optimistic_bound(list(remaining), current_time, current_score) <= best_score:
            return

        branch_nodes = sorted(
            ready_nodes,
            key=lambda block_id: (
                blocks_by_id[block_id].net_value,
                blocks_by_id[block_id].value_density,
                blocks_by_id[block_id].ore_grade,
            ),
            reverse=True,
        )

        for block_id in branch_nodes:
            block = blocks_by_id[block_id]
            next_time = current_time + max(1, _economic_duration(block))
            next_score = current_score + discounted_value(
                block.net_value,
                next_time,
                settings.discount_rate_per_hour,
            )

            next_sequence = sequence + [block_id]
            next_remaining = set(remaining)
            next_remaining.remove(block_id)
            next_ready = [node for node in ready_nodes if node != block_id]

            for successor in candidate_successors[block_id]:
                if successor in next_remaining and candidate_predecessors[successor].issubset(next_sequence):
                    if successor not in next_ready:
                        next_ready.append(successor)

            search(next_sequence, next_ready, next_remaining, next_time, next_score)

    search([], ready, set(candidate_ids), 0, 0.0)

    best_sequence_set = set(best_sequence)
    if fallback_strategy == "grade":
        tail = sorted(
            [block for block in ranked if block.block_id not in best_sequence_set],
            key=lambda block: (block.ore_grade, block.value_density, block.net_value),
            reverse=True,
        )
    else:
        tail = sorted(
            [block for block in ranked if block.block_id not in best_sequence_set],
            key=lambda block: (block.value_density, block.net_value, block.ore_grade),
            reverse=True,
        )

    combined_order = best_sequence + [block.block_id for block in tail]
    metadata = {
        "solver": "branch_and_bound",
        "candidate_limit": candidate_limit,
        "candidate_count": len(candidate_ids),
        "visited_nodes": visited_nodes,
        "best_surrogate_objective": round(best_score, 2),
        "candidate_blocks": candidate_ids,
    }
    return combined_order, metadata
