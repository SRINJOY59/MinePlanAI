from __future__ import annotations

from html import escape
from pathlib import Path


def _scenario_rows(scenarios: list[dict[str, object]]) -> str:
    header = "| Scenario | Solver | Makespan (h) | Tonnage | Net Value | Discounted NPV |\n"
    header += "| --- | --- | ---: | ---: | ---: | ---: |\n"
    rows = []
    for scenario in scenarios:
        rows.append(
            "| {name} | {solver} | {makespan} | {tonnage} | {net} | {npv} |".format(
                name=scenario["name"],
                solver=scenario["solver"],
                makespan=scenario["makespan_hours"],
                tonnage=scenario["total_tonnage"],
                net=scenario["net_value"],
                npv=scenario["discounted_npv"],
            )
        )
    return header + "\n".join(rows)


def write_report_markdown(
    output_path: Path,
    project_name: str,
    best_scenario: dict[str, object],
    scenarios: list[dict[str, object]],
    artifacts: dict[str, str],
    preparation: dict[str, object],
) -> None:
    content = f"""# {project_name} Report

## Summary

This report summarizes the latest run of the open-pit mine planning pipeline.

### Best Scenario

- **Scenario:** {best_scenario['name']}
- **Solver:** {best_scenario['solver']}
- **Makespan:** {best_scenario['makespan_hours']} hours
- **Total tonnage:** {best_scenario['total_tonnage']}
- **Net value:** {best_scenario['net_value']}
- **Discounted NPV:** {best_scenario['discounted_npv']}

## Preparation Output

- Block model rows: {preparation['block_model_rows']}
- Ore blocks: {preparation['ore_blocks']}
- Block precedence arcs: {preparation['block_precedence_arcs']}
- Task rows: {preparation['task_rows']}
- Task precedence arcs: {preparation['task_precedence_arcs']}
- Maintenance windows: {preparation['maintenance_windows']}

## Scenario Comparison

{_scenario_rows(scenarios)}

## Generated Artifacts

- Gantt SVG: `{artifacts['gantt_svg']}`
- Gantt HTML: `{artifacts['gantt_html']}`
- Scenario comparison CSV: `{artifacts['scenario_comparison_csv']}`
- Schedule CSV: `{artifacts['schedule_csv']}`

## Interpretation

The current best scenario is selected using the highest discounted NPV. The comparison table can be used in the course evaluation to discuss the effect of heuristic dispatch rules versus optimization-based ordering.
"""
    output_path.write_text(content, encoding="utf-8")


def write_report_html(
    output_path: Path,
    project_name: str,
    best_scenario: dict[str, object],
    scenarios: list[dict[str, object]],
    artifacts: dict[str, str],
    preparation: dict[str, object],
) -> None:
    rows = "".join(
        f"<tr><td>{escape(str(item['name']))}</td><td>{escape(str(item['solver']))}</td><td>{item['makespan_hours']}</td><td>{item['total_tonnage']}</td><td>{item['net_value']}</td><td>{item['discounted_npv']}</td></tr>"
        for item in scenarios
    )
    html = f"""<!DOCTYPE html>
<html lang="en">
  <head>
    <meta charset="utf-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1" />
    <title>{escape(project_name)} Report</title>
    <style>
      * {{
        box-sizing: border-box;
      }}
      body {{
        margin: 0;
        padding: 20px;
        font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
        background: #fff;
        color: #1a1a1a;
        line-height: 1.5;
      }}
      .shell {{
        width: 100%;
        max-width: 100%;
        margin: 0;
      }}
      h1 {{ font-size: 1.8rem; margin-top: 0; color: #111; }}
      h2 {{ font-size: 1.4rem; margin-top: 24px; border-bottom: 2px solid #f0f0f0; padding-bottom: 8px; }}
      ul {{ padding-left: 20px; }}
      li {{ margin-bottom: 8px; }}
      table {{
        width: 100%;
        border-collapse: collapse;
        margin-top: 16px;
        font-size: 0.9rem;
        display: block;
        overflow-x: auto;
      }}
      th, td {{
        padding: 12px;
        border-bottom: 1px solid #eee;
        text-align: left;
      }}
      th {{
        background: #fafafa;
        font-weight: 600;
        color: #666;
        text-transform: uppercase;
        font-size: 0.75rem;
        letter-spacing: 0.05em;
      }}
      code {{
        background: #f5f5f5;
        padding: 2px 4px;
        border-radius: 4px;
        font-family: monospace;
        font-size: 0.85rem;
        overflow-wrap: anywhere;
      }}
      @media (max-width: 640px) {{
        body {{
          padding: 12px;
        }}
        .shell {{
          padding-bottom: 12px;
        }}
        h1 {{
          font-size: 1.45rem;
        }}
        h2 {{
          font-size: 1.15rem;
        }}
      }}
    </style>
  </head>
  <body>
    <div class="shell">
      <h1>{escape(project_name)} Report</h1>
      <p>This report summarizes the latest planning run.</p>
      <h2>Best Scenario</h2>
      <ul>
        <li><strong>Scenario:</strong> {escape(str(best_scenario['name']))}</li>
        <li><strong>Solver:</strong> {escape(str(best_scenario['solver']))}</li>
        <li><strong>Makespan:</strong> {best_scenario['makespan_hours']} hours</li>
        <li><strong>Total tonnage:</strong> {best_scenario['total_tonnage']}</li>
        <li><strong>Net value:</strong> {best_scenario['net_value']}</li>
        <li><strong>Discounted NPV:</strong> {best_scenario['discounted_npv']}</li>
      </ul>
      <h2>Preparation Output</h2>
      <ul>
        <li>Block model rows: {preparation['block_model_rows']}</li>
        <li>Ore blocks: {preparation['ore_blocks']}</li>
        <li>Block precedence arcs: {preparation['block_precedence_arcs']}</li>
        <li>Task rows: {preparation['task_rows']}</li>
        <li>Task precedence arcs: {preparation['task_precedence_arcs']}</li>
        <li>Maintenance windows: {preparation['maintenance_windows']}</li>
      </ul>
      <h2>Scenario Comparison</h2>
      <table>
        <thead>
          <tr>
            <th>Scenario</th>
            <th>Solver</th>
            <th>Makespan (h)</th>
            <th>Tonnage</th>
            <th>Net Value</th>
            <th>Discounted NPV</th>
          </tr>
        </thead>
        <tbody>{rows}</tbody>
      </table>
      <h2>Generated Artifacts</h2>
      <ul>
        <li>Gantt SVG: <code>{escape(artifacts['gantt_svg'])}</code></li>
        <li>Gantt HTML: <code>{escape(artifacts['gantt_html'])}</code></li>
        <li>Scenario comparison CSV: <code>{escape(artifacts['scenario_comparison_csv'])}</code></li>
        <li>Schedule CSV: <code>{escape(artifacts['schedule_csv'])}</code></li>
      </ul>
    </div>
  </body>
</html>
"""
    output_path.write_text(html, encoding="utf-8")
