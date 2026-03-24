# MinePlan AI

Open-pit mine production planning system developed for the **Artificial Intelligence: Foundations and Applications** course project.

This project models open-pit mining as a **classical AI planning and scheduling problem**. It takes real web-sourced mining data, derives planning artifacts such as block models, task graphs, precedence relations, and maintenance windows, and then produces a feasible production schedule for **drilling**, **blasting**, and **hauling** under operational constraints.

## Course Context

- **Course:** Artificial Intelligence: Foundations and Applications
- **Project Theme:** Mining Engineering and Classical Artificial Intelligence
- **Problem Domain:** Open-pit mine production planning
- **Core AI Focus:** Constraint-based planning, heuristic scheduling, precedence reasoning, and resource allocation

## Problem Statement

Open-pit mine production planning is a constrained decision problem. Mining activities must be executed in the correct order, must respect equipment limits, and must remain operationally safe.

The project addresses the following challenge:

- how to schedule `drill -> blast -> haul` operations for mining blocks
- while respecting block precedence
- while working with limited resources
- while accounting for maintenance downtime
- while preserving safety constraints such as post-blast waiting and bench re-entry gaps

## Project Objectives

This system is designed to:

- use real public mining-related datasets rather than only toy inputs
- convert raw mining data into planning-ready artifacts
- apply classical AI ideas to generate a feasible schedule
- provide both a command-line workflow and a user-friendly web interface
- make the intermediate reasoning artifacts visible for inspection

## Why This Is An AI Project

This project is intentionally framed as a **classical AI** system rather than a machine learning system.

The AI elements are:

- **Constraint satisfaction**
  Scheduling must obey precedence, capacities, and maintenance constraints.
- **Heuristic search / list scheduling**
  Ready blocks are ranked and placed using a greedy heuristic.
- **Knowledge-based task derivation**
  Drill, blast, and haul tasks are derived from engineering rules.
- **Rule-based reasoning**
  Maintenance and precedence relations are generated using explicit rules.
- **Planning under constraints**
  The system constructs a valid sequence of actions that satisfies operational requirements.

This project does **not** rely on deep learning or neural models. Its AI foundation is based on logic, heuristics, scheduling, and constrained planning.

## Key Features

- real web-sourced input data
- derived block model and ore block extraction
- explicit block precedence graph
- explicit task graph for drilling, blasting, and hauling
- maintenance window generation
- constrained scheduling engine
- optimization-assisted solver using branch-and-bound search
- economic objective evaluation using revenue, cost, net value, and discounted NPV
- scenario comparison across heuristic and optimization methods
- Gantt chart export
- Markdown and HTML report export
- FastAPI backend
- Next.js interactive dashboard
- dataset preview and schedule inspection through the UI

## Data Sources

The project uses two public web-sourced datasets:

### 1. GeoMet drillhole dataset

- **Local file:** `external_data/geomet_drillholes.csv`
- **Source:** [Zenodo GeoMet dataset](https://zenodo.org/records/7051975)
- **Role in project:** geology-style raw input for deriving block-like mining units

This dataset provides drillhole sample records with spatial coordinates and mineral measurements. In this project, it is used to derive:

- block model rows
- ore grades
- tonnage estimates
- block-level drill/blast/haul durations

### 2. OpenMines North Pit configuration

- **Local file:** `external_data/openmines-main/openmines/src/conf/north_pit_mine.json`
- **Source:** [OpenMines repository](https://github.com/370025263/openmines)
- **Role in project:** real haulage and site-capacity input

This configuration provides:

- truck fleet counts
- truck capacities
- working faces / load sites
- shovel layout
- dump site structure

## Important Data Note

The raw public sources do **not** directly contain a complete open-pit production scheduling benchmark in the exact format required by this project.

Therefore, the system explicitly **derives** the missing planning artifacts:

- block model
- ore blocks
- task definitions
- precedence graph
- maintenance schedule

This is an important academic point:

- the raw web data is real
- the planning representation is derived from that real data using documented assumptions

## Engineering Assumptions Used

The following assumptions are currently used in the preprocessing stage:

- drillhole samples are aggregated by `HOLEID` and bench height to form block-like units
- default bench height is `15`
- each sample contributes to an approximate tonnage estimate
- ore grade is derived from `Cu ppm`
- blocks with ore grade greater than or equal to `0.8% Cu` are treated as ore blocks
- drilling, blasting, and hauling durations are derived from sample count and tonnage
- drilling and blasting resource counts are inferred from the OpenMines site layout
- haulage resource count comes from the actual OpenMines truck fleet count
- maintenance windows are generated deterministically using periodic service rules

These assumptions are transparent in code and can be modified for experimentation.

## System Architecture

The system has four major stages:

1. **Raw data ingestion**
   Read the GeoMet drillhole CSV and the OpenMines North Pit JSON file.

2. **Planning artifact generation**
   Convert raw data into planning-ready CSV files such as block model, ore blocks, precedence, tasks, and maintenance.

3. **Constraint-based scheduling**
   Use a heuristic scheduler to place drill, blast, and haul tasks under capacity and safety constraints.

4. **Presentation layer**
   Expose results through a FastAPI backend and a Next.js dashboard.

## End-To-End Pipeline

The main pipeline is:

```text
Real web data
-> derived planning artifacts
-> constrained scheduler
-> final production schedule
-> interactive dashboard
```

## Repository Structure

```text
AIFA/
├── backend/                  # FastAPI backend
├── data/                     # Scheduler input/output data
│   └── web_derived/          # Derived planning artifacts and final schedule
├── external_data/            # Downloaded public source data
├── frontend/                 # Next.js dashboard
├── mine_scheduler/           # Core Python pipeline and scheduler
└── README.md
```

## Core Python Modules

### `mine_scheduler/prepare_web_data.py`

Builds planning artifacts from the public web datasets.

Outputs:

- `block_model.csv`
- `ore_blocks.csv`
- `block_precedence.csv`
- `tasks.csv`
- `task_precedence.csv`
- `maintenance.csv`
- `resources.csv`
- scheduler-ready `blocks.csv` and `precedence.csv`

### `mine_scheduler/scheduler.py`

Implements the constrained scheduling logic.

Main concepts:

- resource capacity calendar
- precedence-aware block release
- earliest feasible placement
- safety gaps after blasting
- maintenance-aware resource availability

### `mine_scheduler/optimizer.py`

Implements the optimization layer used to improve block ordering with branch-and-bound search over a reduced high-value subset.

### `mine_scheduler/pipeline.py`

Provides a reusable end-to-end pipeline function:

- `run_web_pipeline()`

This is the main programmatic entrypoint for the backend and automation.

### `backend/app/main.py`

FastAPI service exposing:

- pipeline execution
- dashboard snapshot
- dataset preview endpoints

### `frontend/app/page.tsx`

Next.js dashboard that allows the user to:

- run the pipeline from the browser
- change pipeline parameters
- inspect derived datasets
- inspect the generated schedule

## Planning Artifacts Produced

After preprocessing, the project generates the following files inside `data/web_derived/`:

### `block_model.csv`

Derived block model containing:

- block id
- hole id
- bench
- centroid coordinates
- sample count
- tonnage
- ore grade
- material type
- task durations
- priority signal

### `ore_blocks.csv`

Ore-only subset of the derived block model.

### `block_precedence.csv`

Block-to-block precedence arcs derived from bench ordering within the same drillhole.

### `tasks.csv`

Explicit task list with:

- `drill`
- `blast`
- `haul`

### `task_precedence.csv`

Task-level precedence edges covering:

- within-block sequence
- cross-block dependencies

### `maintenance.csv`

Maintenance windows for:

- `DRILL`
- `BLAST`
- `HAUL`

### `schedule_output.csv`

The final scheduled task list produced by the scheduler.

### `scenario_comparison.csv`

Method comparison table for course evaluation.

### `gantt_chart.svg` and `gantt_chart.html`

Exported Gantt visualization for the best schedule.

### `project_report.md` and `project_report.html`

Exportable project reports summarizing the best scenario and method comparison.

## Scheduling Method

The project now combines **heuristic scheduling** with an **optimization-assisted scenario comparison workflow**.

### Heuristic scheduling logic

1. release blocks whose predecessors are complete
2. rank ready blocks by priority, ore grade, and tonnage
3. schedule `drill`
4. schedule `blast`
5. enforce bench re-entry delay
6. schedule `haul`
7. update resource calendars and continue until all blocks are placed

### Optimization-assisted logic

1. rank high-value candidate blocks
2. run branch-and-bound search on the candidate ordering
3. optimize a discounted economic surrogate objective
4. feed the optimized ordering into the final scheduler
5. compare the optimized result against multiple heuristic baselines

## Constraints Modeled

The scheduler currently handles:

- block precedence constraints
- limited drill resources
- limited blast resources
- limited haul resources
- maintenance downtime
- post-blast wait before hauling
- bench re-entry gap after blasting

## Objective Functions

The project now computes:

- revenue
- cost
- net value
- discounted NPV

These metrics are used to compare scenarios and select the best schedule.

## Technology Stack

### Backend / AI pipeline

- Python
- FastAPI
- Uvicorn

### Frontend

- Next.js
- React
- TypeScript

## How To Run

All commands below assume you are in the project root:

```powershell
cd C:\Users\Srinjoy\OneDrive\Desktop\AIFA
```

### A. Run only the data pipeline and scheduler

Generate the planning artifacts from the real web data:

```powershell
.\.venv\Scripts\python.exe -m mine_scheduler.prepare_web_data
```

Run the scheduler on the generated planning instance:

```powershell
.\.venv\Scripts\python.exe -m mine_scheduler.cli --blocks data/web_derived/blocks.csv --precedence data/web_derived/precedence.csv --resources data/web_derived/resources.csv --maintenance data/web_derived/maintenance.csv --output data/web_derived/schedule_output.csv
```

### B. Run the full Python pipeline in one command

```powershell
.\.venv\Scripts\python.exe -m mine_scheduler.run_pipeline
```

### C. Run the FastAPI backend

Install backend dependencies:

```powershell
& 'C:\Program Files (x86)\Google\Cloud SDK\google-cloud-sdk\platform\bundledpython\python.exe' -m pip install -r backend\requirements.txt
```

Start the API:

```powershell
& 'C:\Program Files (x86)\Google\Cloud SDK\google-cloud-sdk\platform\bundledpython\python.exe' -m uvicorn backend.app.main:app --reload --host 127.0.0.1 --port 8000
```

FastAPI docs will be available at:

- `http://127.0.0.1:8000/docs`

### D. Run the Next.js frontend

Open a second PowerShell window:

```powershell
cd C:\Users\Srinjoy\OneDrive\Desktop\AIFA\frontend
npm install
$env:NEXT_PUBLIC_API_BASE_URL='http://127.0.0.1:8000'
npm run dev
```

Frontend will be available at:

- `http://localhost:3000`

## Backend API Endpoints

The backend exposes these main endpoints:

- `GET /api/health`
- `GET /api/dashboard`
- `GET /api/datasets/{dataset_name}`
- `POST /api/pipeline/run`
- `GET /api/files`
- `GET /api/artifacts/{artifact_name}`

## User Interface Overview

The web interface allows the user to:

- run the pipeline interactively
- change `bench_height`
- change `max_blocks`
- change spatial precedence settings
- change optimization subset size
- inspect counts for block model rows, tasks, maintenance windows, and schedule rows
- compare multiple heuristic methods and the optimization-assisted scenario
- preview the generated datasets directly in the browser
- open the exported Gantt chart and reports
- inspect resource capacities and source file locations

## Example Outputs

With the current default settings, the pipeline has produced outputs such as:

- block model rows
- ore blocks
- block precedence arcs
- task rows
- maintenance windows
- final schedule with makespan in hours

These values change when `bench_height` or `max_blocks` are changed.

## Academic Value Of The Project

This project demonstrates how foundational AI concepts can be applied to a realistic industrial problem.

It shows:

- how to formulate a real-world planning problem
- how to convert raw domain data into AI-ready representations
- how to apply constraint-based reasoning, heuristic scheduling, and optimization-assisted search
- how to expose AI results through a usable interactive system

## Current Limitations

- the block model is derived, not provided directly as a production-ready mine block model
- maintenance windows are generated by explicit rules rather than extracted from a real equipment maintenance system
- the optimization solver currently searches a reduced high-value subset rather than the full block set
- economics are simplified and intended for comparative analysis, not production finance
- no stochastic uncertainty model is included yet

## Future Improvements

- replace reduced-set branch-and-bound with a full MIP or CP-based optimizer
- incorporate richer mining economics such as blending and cut-off policies
- add uncertainty-aware scheduling
- support scenario persistence and saved experiments in the web UI
- add richer visualization and presentation-ready exports

## Suggested Report Positioning

For the course report or presentation, this project can be described as:

> A classical AI-based decision support system for open-pit mine production planning that derives scheduling artifacts from real public mining datasets and generates feasible drill, blast, and haul schedules under resource, precedence, safety, and maintenance constraints.

## Authors

Add the team member names, roll numbers, and instructor details here before final submission.
