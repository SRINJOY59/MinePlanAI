from __future__ import annotations

import argparse

from .pipeline import run_web_pipeline


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Run the full MinePlan AI pipeline with scenario comparison, optimization, and reporting."
    )
    parser.add_argument("--bench-height", type=int, default=100)
    parser.add_argument("--max-blocks", type=int, default=60)
    parser.add_argument("--spatial-neighbors", type=int, default=2)
    parser.add_argument("--spatial-radius", type=float, default=450.0)
    parser.add_argument("--exact-solver-limit", type=int, default=12)
    return parser


def main() -> None:
    args = build_parser().parse_args()
    result = run_web_pipeline(
        bench_height=args.bench_height,
        max_blocks=args.max_blocks,
        spatial_neighbors=args.spatial_neighbors,
        spatial_radius=args.spatial_radius,
        exact_solver_limit=args.exact_solver_limit,
    )
    print(f"Best scenario: {result['best_scenario']['name']}")
    print(f"Discounted NPV: {result['best_scenario']['discounted_npv']}")
    print(f"Gantt SVG: {result['artifacts']['gantt_svg']}")
    print(f"Report HTML: {result['artifacts']['report_html']}")


if __name__ == "__main__":
    main()
