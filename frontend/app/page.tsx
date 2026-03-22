"use client";

import { useEffect, useMemo, useState, useTransition } from "react";

type DashboardResponse = {
  counts: Record<string, number>;
  resources: Array<Record<string, string>>;
  previews: Record<string, Array<Record<string, string>>>;
  schedule_metrics: Record<string, number>;
  sources: Record<string, string>;
  artifacts: Record<string, string>;
};

type DatasetResponse = {
  dataset: string;
  rows: Array<Record<string, string>>;
  total_rows: number;
};

type PipelineRunResponse = {
  preparation: Record<string, unknown>;
  schedule: Record<string, unknown>;
  best_scenario: Record<string, unknown>;
  scenario_comparison: Array<Record<string, unknown>>;
  artifacts: Record<string, string>;
};

type ScenarioSummary = {
  name: string;
  solver: string;
  strategy: string;
  makespanHours: number;
  totalTonnage: number;
  netValue: number;
  discountedNpv: number;
};

const DATASET_OPTIONS = [
  { key: "scenario_comparison", label: "Scenario Comparison" },
  { key: "schedule", label: "Best Schedule" },
  { key: "block_model", label: "Block Model" },
  { key: "ore_blocks", label: "Ore Blocks" },
  { key: "tasks", label: "Tasks" },
  { key: "block_precedence", label: "Block Precedence" },
  { key: "task_precedence", label: "Task Precedence" },
  { key: "maintenance", label: "Maintenance" },
] as const;

const API_BASE = (
  process.env.NEXT_PUBLIC_API_URL || 
  process.env.NEXT_PUBLIC_API_BASE_URL || 
  "http://127.0.0.1:8000"
).replace(/\/$/, "");

const compactFormatter = new Intl.NumberFormat("en-US", {
  notation: "compact",
  maximumFractionDigits: 2,
});

const integerFormatter = new Intl.NumberFormat("en-US");

function asNumber(value: unknown): number {
  const numeric = Number(value ?? 0);
  return Number.isFinite(numeric) ? numeric : 0;
}

function formatCompact(value: number): string {
  return compactFormatter.format(value);
}

function formatInteger(value: number): string {
  return integerFormatter.format(value);
}

function getBestScenario(
  comparison: ScenarioSummary[],
  fallbackName: string,
): ScenarioSummary | null {
  if (comparison.length > 0) {
    return comparison[0];
  }
  if (!fallbackName) {
    return null;
  }
  return {
    name: fallbackName,
    solver: "pending",
    strategy: "pending",
    makespanHours: 0,
    totalTonnage: 0,
    netValue: 0,
    discountedNpv: 0,
  };
}

async function getJson<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${API_BASE}${path}`, {
    ...init,
    headers: {
      "Content-Type": "application/json",
      ...(init?.headers ?? {}),
    },
  });

  if (!response.ok) {
    throw new Error(`Request failed with status ${response.status}`);
  }

  return (await response.json()) as T;
}

export default function HomePage() {
  const [dashboard, setDashboard] = useState<DashboardResponse | null>(null);
  const [dataset, setDataset] = useState<DatasetResponse | null>(null);
  const [selectedDataset, setSelectedDataset] = useState<string>("scenario_comparison");
  const [benchHeight, setBenchHeight] = useState<number>(100);
  const [maxBlocks, setMaxBlocks] = useState<number>(60);
  const [spatialNeighbors, setSpatialNeighbors] = useState<number>(2);
  const [spatialRadius, setSpatialRadius] = useState<number>(450);
  const [exactSolverLimit, setExactSolverLimit] = useState<number>(12);
  const [errorMessage, setErrorMessage] = useState<string>("");
  const [statusMessage, setStatusMessage] = useState<string>("Loading current pipeline state...");
  const [lastRun, setLastRun] = useState<PipelineRunResponse | null>(null);
  const [artifactVersion, setArtifactVersion] = useState<number>(0);
  const [selectedArtifact, setSelectedArtifact] = useState<string>("report_html");
  const [previewContent, setPreviewContent] = useState<string>("");
  const [isPending, startTransition] = useTransition();

  useEffect(() => {
    console.log("🔗 MinePlan AI | Connected to API at:", API_BASE);
    void refreshDashboard();
    void refreshDataset("scenario_comparison");
  }, []);

  useEffect(() => {
    const loadPreview = async () => {
      try {
        const response = await fetch(`${API_BASE}/api/artifacts/${selectedArtifact}?ts=${artifactVersion}`);
        if (response.ok) {
          const text = await response.text();
          setPreviewContent(text);
        }
      } catch (err) {
        console.error("Failed to load preview:", err);
      }
    };
    void loadPreview();
  }, [selectedArtifact, artifactVersion]);

  async function refreshDashboard() {
    try {
      const response = await getJson<DashboardResponse>("/api/dashboard");
      setDashboard(response);
      setStatusMessage("Mission control synced with the latest planning state.");
      setErrorMessage("");
      setArtifactVersion(Date.now());
    } catch (error) {
      setErrorMessage(error instanceof Error ? error.message : "Failed to load dashboard.");
    }
  }

  async function refreshDataset(datasetName: string) {
    try {
      const response = await getJson<DatasetResponse>(`/api/datasets/${datasetName}?limit=60`);
      setDataset(response);
      setSelectedDataset(datasetName);
      setErrorMessage("");
    } catch (error) {
      setErrorMessage(error instanceof Error ? error.message : "Failed to load dataset preview.");
    }
  }

  async function runPipeline() {
    setStatusMessage("Rebuilding derived blocks, scenario comparisons, reports, and Gantt artifacts...");
    setErrorMessage("");

    startTransition(async () => {
      try {
        const response = await getJson<PipelineRunResponse>("/api/pipeline/run", {
          method: "POST",
          body: JSON.stringify({
            bench_height: benchHeight,
            max_blocks: maxBlocks,
            spatial_neighbors: spatialNeighbors,
            spatial_radius: spatialRadius,
            exact_solver_limit: exactSolverLimit,
          }),
        });
        setLastRun(response);
        setStatusMessage("Pipeline complete. Optimization leaderboard and exports refreshed.");
        await refreshDashboard();
        await refreshDataset(selectedDataset);
      } catch (error) {
        setErrorMessage(error instanceof Error ? error.message : "Pipeline run failed.");
        setStatusMessage("Pipeline run failed.");
      }
    });
  }

  const selectedLabel = useMemo(
    () => DATASET_OPTIONS.find((item) => item.key === selectedDataset)?.label ?? selectedDataset,
    [selectedDataset],
  );

  const tableColumns = useMemo(() => {
    if (!dataset?.rows.length) {
      return [];
    }
    return Object.keys(dataset.rows[0]);
  }, [dataset]);

  const scenarioComparison = useMemo<ScenarioSummary[]>(() => {
    const sourceRows =
      lastRun?.scenario_comparison ??
      dashboard?.previews.scenario_comparison ??
      [];

    return sourceRows
      .map((row) => ({
        name: String(row.name ?? ""),
        solver: String(row.solver ?? ""),
        strategy: String(row.strategy ?? ""),
        makespanHours: asNumber(row.makespan_hours),
        totalTonnage: asNumber(row.total_tonnage),
        netValue: asNumber(row.net_value),
        discountedNpv: asNumber(row.discounted_npv),
      }))
      .sort((left, right) => right.discountedNpv - left.discountedNpv);
  }, [dashboard, lastRun]);

  const bestScenario = useMemo(
    () =>
      getBestScenario(
        scenarioComparison,
        String(lastRun?.best_scenario.name ?? ""),
      ),
    [lastRun, scenarioComparison],
  );

  const maxNpv = useMemo(
    () => Math.max(...scenarioComparison.map((scenario) => scenario.discountedNpv), 1),
    [scenarioComparison],
  );

  const maxMakespan = useMemo(
    () => Math.max(...scenarioComparison.map((scenario) => scenario.makespanHours), 1),
    [scenarioComparison],
  );

  const metricCards = [
    {
      label: "Ore blocks",
      value: formatInteger(dashboard?.counts.ore_blocks ?? 0),
      tone: "emerald",
      detail: "derived from live web data",
    },
    {
      label: "Task graph",
      value: formatInteger(dashboard?.counts.tasks ?? 0),
      tone: "copper",
      detail: "drill, blast, and haul nodes",
    },
    {
      label: "Best NPV",
      value: formatCompact(bestScenario?.discountedNpv ?? 0),
      tone: "slate",
      detail: "discounted objective score",
    },
    {
      label: "Makespan",
      value: `${formatInteger(bestScenario?.makespanHours ?? 0)}h`,
      tone: "sand",
      detail: "for the leading scenario",
    },
  ];


  return (
    <main className="page-shell">
      <div className="page-grid">
        <section className="hero-shell">
          <div className="hero-main">
            <div className="hero-kicker">MinePlan AI / Command Deck</div>
            <h1>Make the mine planner look like the strongest thing in the room.</h1>
            <p className="hero-copy">
              This interface turns your project from a raw engineering tool into a decision center:
              real-source planning inputs, optimization-aware scheduling, scenario evaluation,
              export-ready reporting, and a visual output surface that actually feels deliberate.
            </p>
            <div className="hero-band">
              <div className="band-card">
                <span>Best scenario</span>
                <strong>{bestScenario?.name ?? "Waiting for run"}</strong>
              </div>
              <div className="band-card">
                <span>Discounted NPV</span>
                <strong>{formatCompact(bestScenario?.discountedNpv ?? 0)}</strong>
              </div>
              <div className="band-card">
                <span>Solver field</span>
                <strong>{bestScenario?.solver ?? "pending"}</strong>
              </div>
            </div>
          </div>

          <div className="hero-side">
            <div className="spotlight-card">
              <p className="eyebrow">Lead Strategy</p>
              <h2>{bestScenario?.name ?? "No scenario yet"}</h2>
              <p className="muted">
                The top performer is selected by discounted NPV after comparing heuristic and
                optimization-assisted schedules on the same derived planning instance.
              </p>
              <div className="spotlight-grid">
                <div>
                  <span>Net Value</span>
                  <strong>{formatCompact(bestScenario?.netValue ?? 0)}</strong>
                </div>
                <div>
                  <span>Makespan</span>
                  <strong>{formatInteger(bestScenario?.makespanHours ?? 0)}h</strong>
                </div>
                <div>
                  <span>Tonnage</span>
                  <strong>{formatCompact(bestScenario?.totalTonnage ?? 0)}</strong>
                </div>
                <div>
                  <span>Method</span>
                  <strong>{bestScenario?.solver ?? "n/a"}</strong>
                </div>
              </div>
            </div>

            <div className="pipeline-rail">
              <div className="rail-stop">
                <strong>Raw inputs</strong>
                <span>GeoMet + OpenMines</span>
              </div>
              <div className="rail-stop">
                <strong>Derived planning</strong>
                <span>blocks, tasks, precedence</span>
              </div>
              <div className="rail-stop">
                <strong>Scenario engine</strong>
                <span>heuristics + branch and bound</span>
              </div>
              <div className="rail-stop">
                <strong>Exports</strong>
                <span>schedule, Gantt, reports</span>
              </div>
            </div>
          </div>
        </section>

        <div className="metric-strip">
          {metricCards.map((metric) => (
            <article key={metric.label} className={`metric-tile tone-${metric.tone}`}>
              <span>{metric.label}</span>
              <strong>{metric.value}</strong>
              <p>{metric.detail}</p>
            </article>
          ))}
        </div>

        <div className="dashboard-grid">
          <div className="stack">
            <section className="panel control-panel">
              <div className="panel-titlebar">
                <div>
                  <p className="eyebrow">Control Room</p>
                  <h2>Shape The Planning Instance</h2>
                </div>
                <div className="panel-badge">Scenario tuning</div>
              </div>

              <div className="control-grid">
                <div className="field-card">
                  <label htmlFor="benchHeight">Bench Height</label>
                  <input
                    id="benchHeight"
                    type="number"
                    min={25}
                    max={200}
                    step={25}
                    value={benchHeight}
                    onChange={(event) => setBenchHeight(Number(event.target.value))}
                  />
                </div>
                <div className="field-card">
                  <label htmlFor="maxBlocks">Max Blocks</label>
                  <input
                    id="maxBlocks"
                    type="number"
                    min={10}
                    max={300}
                    step={10}
                    value={maxBlocks}
                    onChange={(event) => setMaxBlocks(Number(event.target.value))}
                  />
                </div>
                <div className="field-card">
                  <label htmlFor="spatialNeighbors">Spatial Neighbors</label>
                  <input
                    id="spatialNeighbors"
                    type="number"
                    min={1}
                    max={5}
                    value={spatialNeighbors}
                    onChange={(event) => setSpatialNeighbors(Number(event.target.value))}
                  />
                </div>
                <div className="field-card">
                  <label htmlFor="spatialRadius">Spatial Radius</label>
                  <input
                    id="spatialRadius"
                    type="number"
                    min={50}
                    max={2000}
                    step={25}
                    value={spatialRadius}
                    onChange={(event) => setSpatialRadius(Number(event.target.value))}
                  />
                </div>
                <div className="field-card">
                  <label htmlFor="exactSolverLimit">Exact Solver Limit</label>
                  <input
                    id="exactSolverLimit"
                    type="number"
                    min={4}
                    max={20}
                    value={exactSolverLimit}
                    onChange={(event) => setExactSolverLimit(Number(event.target.value))}
                  />
                </div>
                <div className="field-card field-card-accent">
                  <label htmlFor="datasetView">Live Dataset Focus</label>
                  <select
                    id="datasetView"
                    value={selectedDataset}
                    onChange={(event) => void refreshDataset(event.target.value)}
                  >
                    {DATASET_OPTIONS.map((item) => (
                      <option key={item.key} value={item.key}>
                        {item.label}
                      </option>
                    ))}
                  </select>
                </div>
              </div>

              <div className="action-row">
                <button className="button-primary" onClick={() => void runPipeline()} disabled={isPending}>
                  {isPending ? "Running full pipeline..." : "Rebuild + Compare + Export"}
                </button>
                <button
                  className="button-secondary"
                  onClick={() => {
                    void refreshDashboard();
                    void refreshDataset(selectedDataset);
                  }}
                  disabled={isPending}
                >
                  Sync Dashboard
                </button>
              </div>

              <div className="status-ribbon">
                <strong>Status</strong>
                <span>{statusMessage}</span>
              </div>
              {errorMessage ? <div className="error-note">{errorMessage}</div> : null}
            </section>

            <section className="panel">
              <div className="panel-titlebar">
                <div>
                  <p className="eyebrow">Scenario Arena</p>
                  <h2>Method Comparison, But Make It Actually Readable</h2>
                </div>
                <div className="panel-badge">{scenarioComparison.length} contenders</div>
              </div>

              <div className="scenario-grid">
                {scenarioComparison.map((scenario, index) => (
                  <article
                    key={scenario.name}
                    className={`scenario-card ${index === 0 ? "is-best" : ""}`}
                  >
                    <div className="scenario-head">
                      <div>
                        <p className="scenario-rank">#{index + 1}</p>
                        <h3>{scenario.name}</h3>
                      </div>
                      <span className="solver-pill">{scenario.solver}</span>
                    </div>

                    <div className="scenario-kpis">
                      <div>
                        <span>Discounted NPV</span>
                        <strong>{formatCompact(scenario.discountedNpv)}</strong>
                      </div>
                      <div>
                        <span>Makespan</span>
                        <strong>{formatInteger(scenario.makespanHours)}h</strong>
                      </div>
                      <div>
                        <span>Net Value</span>
                        <strong>{formatCompact(scenario.netValue)}</strong>
                      </div>
                    </div>

                    <div className="signal-stack">
                      <div className="signal-row">
                        <span>NPV Strength</span>
                        <div className="signal-track">
                          <div
                            className="signal-fill signal-fill-emerald"
                            style={{ width: `${(scenario.discountedNpv / maxNpv) * 100}%` }}
                          />
                        </div>
                      </div>
                      <div className="signal-row">
                        <span>Schedule Length</span>
                        <div className="signal-track">
                          <div
                            className="signal-fill signal-fill-copper"
                            style={{ width: `${(scenario.makespanHours / maxMakespan) * 100}%` }}
                          />
                        </div>
                      </div>
                    </div>
                  </article>
                ))}
              </div>
            </section>
          </div>

          <div className="stack">
            <section className="panel report-panel">
              <div className="panel-titlebar">
                <div>
                  <p className="eyebrow">Project Synthesis</p>
                  <h2>Live Report Viewer</h2>
                </div>
                <div className="tabs">
                  <button
                    className={`tab ${selectedArtifact === "report_html" ? "is-active" : ""}`}
                    onClick={() => setSelectedArtifact("report_html")}
                  >
                    Main Report
                  </button>
                  <button
                    className={`tab ${selectedArtifact === "gantt_html" ? "is-active" : ""}`}
                    onClick={() => setSelectedArtifact("gantt_html")}
                  >
                    Gantt Timeline
                  </button>
                </div>
              </div>
              <div className="artifact-stage report-stage">
                {previewContent ? (
                  <iframe
                    srcDoc={previewContent}
                    className="preview-iframe"
                    title="Live Report"
                  />
                ) : (
                  <div className="status-note">Preparing report content...</div>
                )}
              </div>
            </section>
          </div>
        </div>

        <section className="panel bottom-observatory">
          <div className="panel-titlebar">
            <div>
              <p className="eyebrow">Data Observatory</p>
              <h2>{selectedLabel}</h2>
            </div>
            <span className="panel-badge">
              {dataset ? `${dataset.total_rows} rows` : "No data"}
            </span>
          </div>

          <div className="tabs">
            {DATASET_OPTIONS.map((item) => (
              <button
                key={item.key}
                type="button"
                className={`tab ${selectedDataset === item.key ? "is-active" : ""}`}
                onClick={() => void refreshDataset(item.key)}
              >
                {item.label}
              </button>
            ))}
          </div>

          <div className="table-wrap" style={{ marginTop: 18 }}>
            <table className="table">
              <thead>
                <tr>
                  {tableColumns.map((column) => (
                    <th key={column}>{column}</th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {dataset?.rows.map((row, rowIndex) => (
                  <tr key={`${selectedDataset}-${rowIndex}`}>
                    {tableColumns.map((column) => (
                      <td key={column}>{row[column]}</td>
                    ))}
                  </tr>
                ))}
                {!dataset?.rows.length ? (
                  <tr>
                    <td colSpan={Math.max(tableColumns.length, 1)}>No preview rows available.</td>
                  </tr>
                ) : null}
              </tbody>
            </table>
          </div>
        </section>

      </div>
    </main>
  );
}
