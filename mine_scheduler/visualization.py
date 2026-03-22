from __future__ import annotations

from collections import defaultdict
from html import escape
from pathlib import Path

from .models import TaskWindow

TASK_COLORS = {
    "drill": "#19647e",
    "blast": "#c75b12",
    "haul": "#0b6e4f",
}


def generate_gantt_svg(
    tasks: list[TaskWindow],
    output_path: Path,
    title: str,
) -> None:
    grouped: dict[str, list[TaskWindow]] = defaultdict(list)
    for task in tasks:
        grouped[task.block_id].append(task)

    blocks = sorted(grouped, key=lambda block_id: min(task.start_hour for task in grouped[block_id]))
    max_end = max((task.end_hour for task in tasks), default=1)
    row_height = 32
    left_margin = 170
    top_margin = 70
    chart_width = 1120
    scale = chart_width / max(max_end, 1)
    svg_width = left_margin + chart_width + 80
    svg_height = top_margin + (len(blocks) * row_height) + 80

    lines = [
        f"<svg xmlns='http://www.w3.org/2000/svg' width='{svg_width}' height='{svg_height}' viewBox='0 0 {svg_width} {svg_height}'>",
        "<style>",
        "text { font-family: 'Segoe UI', sans-serif; fill: #1f1d1a; }",
        ".label { font-size: 12px; font-weight: 600; }",
        ".axis { font-size: 11px; fill: #655f57; }",
        ".grid { stroke: rgba(43,31,10,0.12); stroke-width: 1; }",
        ".frame { fill: #f7f2ea; stroke: rgba(43,31,10,0.14); stroke-width: 1; }",
        "</style>",
        f"<rect x='10' y='10' width='{svg_width - 20}' height='{svg_height - 20}' rx='24' class='frame' />",
        f"<text x='{left_margin}' y='38' font-size='24' font-weight='700'>{escape(title)}</text>",
    ]

    for tick in range(0, max_end + 1, max(1, max_end // 12 or 1)):
        x = left_margin + (tick * scale)
        lines.append(f"<line x1='{x:.2f}' y1='{top_margin - 12}' x2='{x:.2f}' y2='{svg_height - 32}' class='grid' />")
        lines.append(f"<text x='{x:.2f}' y='{top_margin - 20}' text-anchor='middle' class='axis'>{tick}h</text>")

    for row_index, block_id in enumerate(blocks):
        y = top_margin + (row_index * row_height)
        lines.append(f"<text x='24' y='{y + 18}' class='label'>{escape(block_id)}</text>")
        lines.append(
            f"<line x1='{left_margin}' y1='{y + 24}' x2='{left_margin + chart_width}' y2='{y + 24}' class='grid' />"
        )
        for task in sorted(grouped[block_id], key=lambda item: item.start_hour):
            x = left_margin + (task.start_hour * scale)
            width = max(4, (task.end_hour - task.start_hour) * scale)
            color = TASK_COLORS.get(task.task_type, "#5b5f97")
            lines.append(
                f"<rect x='{x:.2f}' y='{y + 6}' width='{width:.2f}' height='16' rx='6' fill='{color}' opacity='0.92' />"
            )
            lines.append(
                f"<text x='{x + 6:.2f}' y='{y + 18}' font-size='10' fill='white'>{escape(task.task_type)}</text>"
            )

    legend_y = svg_height - 34
    legend_x = left_margin
    for task_type, color in TASK_COLORS.items():
        lines.append(f"<rect x='{legend_x}' y='{legend_y - 10}' width='18' height='18' rx='5' fill='{color}' />")
        lines.append(f"<text x='{legend_x + 26}' y='{legend_y + 4}' class='axis'>{escape(task_type.title())}</text>")
        legend_x += 110

    lines.append("</svg>")
    output_path.write_text("\n".join(lines), encoding="utf-8")


def generate_gantt_html(
    svg_path: Path,
    html_path: Path,
    title: str,
) -> None:
    svg_markup = svg_path.read_text(encoding="utf-8")
    html = f"""<!DOCTYPE html>
<html lang="en">
  <head>
    <meta charset="utf-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1" />
    <title>{escape(title)}</title>
    <style>
      * {{
        box-sizing: border-box;
      }}
      body {{
        margin: 0;
        padding: 24px;
        font-family: "Segoe UI", sans-serif;
        background: linear-gradient(180deg, #f6efe2, #eee2cf);
        color: #1f1d1a;
      }}
      .shell {{
        width: 100%;
        max-width: 1480px;
        margin: 0 auto;
      }}
      h1 {{
        margin-bottom: 16px;
      }}
      .frame {{
        background: rgba(255,255,255,0.78);
        border-radius: 24px;
        padding: 20px;
        box-shadow: 0 20px 48px rgba(61, 45, 17, 0.14);
        overflow: auto;
      }}
      svg {{
        max-width: 100%;
        height: auto;
      }}
      @media (max-width: 640px) {{
        body {{
          padding: 12px;
        }}
        .frame {{
          padding: 10px;
          border-radius: 16px;
        }}
        h1 {{
          font-size: 1.25rem;
        }}
      }}
    </style>
  </head>
  <body>
    <div class="shell">
      <h1>{escape(title)}</h1>
      <div class="frame">{svg_markup}</div>
    </div>
  </body>
</html>
"""
    html_path.write_text(html, encoding="utf-8")
