<script>
  import { selectedYear } from "../stores.js";
  import { getAnomalies, getCapture } from "../api.js";
  import LoadingSpinner from "../components/LoadingSpinner.svelte";
  import DataTable from "../components/DataTable.svelte";
  import PlotlyChart from "../components/PlotlyChart.svelte";

  let tab = $state("anomalies");
  let minScore = $state(0.3);
  let minRatio = $state(0.7);

  const ANOMALY_TOOLTIPS = {
    composite_anomaly_score: "Weighted blend of z-score, structural, and temporal anomaly signals (0–1)",
    zscore_global: "Standard deviations above the mean payment amount across all physicians",
    zscore_within_specialty: "Standard deviations above the mean payment within the same specialty",
    capture_ratio: "Fraction of total payments from a single company — 1.0 = fully captured",
  };

  const CAPTURE_TOOLTIPS = {
    capture_ratio: "Fraction of total payments from a single company — 1.0 = fully captured",
    company_payment: "Total payment amount from this specific company",
    total_physician_payment: "Total payment amount this physician received across all companies",
  };

  // Fetch at lower threshold so charts have enough data; table filters further
  let anomalyPromise = $derived(getAnomalies($selectedYear, 0.0, 500));
  let capturePromise = $derived(getCapture($selectedYear, minRatio, 300));

  const ANOMALY_COLS = [
    "name",
    "specialty",
    "state",
    "composite_anomaly_score",
    "zscore_global",
    "zscore_within_specialty",
    "capture_ratio",
  ];
  const CAPTURE_COLS = [
    "physician_name",
    "company_name",
    "specialty",
    "state",
    "capture_ratio",
    "company_payment",
    "total_physician_payment",
  ];

  // ── 4-Quadrant scatter: z-score vs composite score ───────────
  function buildQuadrantScatter(rows, minScore) {
    const filtered = rows.filter((r) => r.composite_anomaly_score != null);

    // colour by structural_anomaly flag then fall back to capture_ratio
    const colors = filtered.map((r) => {
      const s = r.composite_anomaly_score ?? 0;
      if (s >= 0.7) return "#e15759";
      if (s >= 0.5) return "#f28e2b";
      return "#4e79a7";
    });

    const trace = {
      type: "scatter",
      mode: "markers",
      name: "Physicians",
      x: filtered.map((r) => r.zscore_global),
      y: filtered.map((r) => r.composite_anomaly_score),
      customdata: filtered.map((r) => r.id),
      text: filtered.map(
        (r) => `${r.name ?? r.id}<br>${r.specialty ?? ""} · ${r.state ?? ""}`,
      ),
      hovertemplate:
        "<b>%{text}</b><br>" +
        "Z-score: %{x:.2f}<br>" +
        "Anomaly score: %{y:.3f}<br>" +
        "<extra></extra>",
      marker: {
        color: colors,
        size: filtered.map((r) =>
          Math.max(4, Math.min(14, 4 + (r.capture_ratio ?? 0) * 10)),
        ),
        opacity: 0.75,
        line: { color: "rgba(0,0,0,0.25)", width: 0.5 },
      },
    };

    // Quadrant reference lines
    const hLine = {
      type: "scatter",
      mode: "lines",
      name: "Score threshold",
      x: [-10, 30],
      y: [0.5, 0.5],
      line: { color: "#f28e2b", width: 1, dash: "dash" },
      showlegend: false,
    };
    const vLine = {
      type: "scatter",
      mode: "lines",
      name: "Z threshold",
      x: [2, 2],
      y: [0, 1.05],
      line: { color: "#f28e2b", width: 1, dash: "dash" },
      showlegend: false,
    };
    return [trace, hLine, vLine];
  }

  const quadLayout = {
    margin: { t: 28, r: 16, b: 56, l: 72 },
    xaxis: {
      title: {
        text: "Global Z-Score (financial outlier)",
        font: { color: "#6b7280", size: 11 },
      },
    },
    yaxis: {
      title: {
        text: "Composite Anomaly Score",
        font: { color: "#6b7280", size: 11 },
      },
      range: [0, 1.05],
    },
    annotations: [
      {
        x: 14,
        y: 0.78,
        text: "⚠ High financial<br>+ High structural",
        showarrow: false,
        font: { color: "#e15759", size: 10 },
        align: "center",
      },
      {
        x: -3,
        y: 0.78,
        text: "Low financial<br>+ High structural",
        showarrow: false,
        font: { color: "#f28e2b", size: 10 },
        align: "center",
      },
      {
        x: 14,
        y: 0.2,
        text: "High financial<br>+ Low structural",
        showarrow: false,
        font: { color: "#6b7280", size: 10 },
        align: "center",
      },
    ],
  };

  // ── Anomaly score distribution - violin by specialty ─────────
  function buildViolin(rows) {
    // top 8 specialties by record count
    const counts = {};
    for (const r of rows) {
      const sp = (r.specialty ?? "Unknown").split("|").pop();
      counts[sp] = (counts[sp] ?? 0) + 1;
    }
    const topSp = Object.entries(counts)
      .sort((a, b) => b[1] - a[1])
      .slice(0, 8)
      .map(([sp]) => sp);

    return topSp.map((sp) => {
      const pts = rows.filter(
        (r) => (r.specialty ?? "").split("|").pop() === sp,
      );
      return {
        type: "violin",
        name: sp.length > 22 ? sp.slice(0, 22) + "…" : sp,
        y: pts.map((r) => r.composite_anomaly_score),
        box: { visible: true },
        meanline: { visible: true },
        opacity: 0.8,
        hoverinfo: "y+name",
      };
    });
  }

  const violinLayout = {
    margin: { t: 16, r: 16, b: 120, l: 64 },
    xaxis: { tickangle: -35, tickfont: { size: 10 } },
    yaxis: {
      title: {
        text: "Composite Anomaly Score",
        font: { color: "#6b7280", size: 11 },
      },
      range: [0, 1.05],
    },
    violinmode: "overlay",
    showlegend: false,
  };

  // ── Capture bubble: total payment × capture ratio ─────────────
  function buildCaptureBubble(rows) {
    const bySpec = {};
    for (const r of rows) {
      const sp = (r.specialty ?? "Other").split("|").pop();
      if (!bySpec[sp]) bySpec[sp] = [];
      bySpec[sp].push(r);
    }
    const topSp = Object.entries(bySpec)
      .sort((a, b) => b[1].length - a[1].length)
      .slice(0, 6);

    return topSp.map(([sp, pts]) => ({
      type: "scatter",
      mode: "markers",
      name: sp.length > 22 ? sp.slice(0, 22) + "…" : sp,
      x: pts.map((r) => r.total_physician_payment),
      y: pts.map((r) => r.capture_ratio),
      customdata: pts.map((r) => r.physician_name),
      text: pts.map((r) => r.physician_name),
      hovertemplate:
        "<b>%{text}</b><br>" +
        "Total payments: $%{x:,.0f}<br>" +
        "Capture ratio: %{y:.2f}<br>" +
        "<extra></extra>",
      marker: {
        size: pts.map((r) =>
          Math.max(
            5,
            Math.min(20, 4 + Math.log1p(r.company_payment || 0) * 1.2),
          ),
        ),
        opacity: 0.75,
        line: { color: "rgba(0,0,0,0.25)", width: 0.5 },
      },
    }));
  }

  const captureLayout = {
    margin: { t: 16, r: 16, b: 56, l: 80 },
    xaxis: {
      title: {
        text: "Total Physician Payments (USD)",
        font: { color: "#6b7280", size: 11 },
      },
      type: "log",
      tickprefix: "$",
    },
    yaxis: {
      title: {
        text: "Single-Payer Capture Ratio",
        font: { color: "#6b7280", size: 11 },
      },
      range: [0, 1.05],
    },
  };
</script>

<div class="page-header">
  <h1 class="page-title">Anomaly Explorer</h1>
  <div class="tabs">
    <button
      class="btn"
      class:btn-active={tab === "anomalies"}
      class:btn-ghost={tab !== "anomalies"}
      onclick={() => (tab = "anomalies")}
      data-tip="Physicians flagged as statistical outliers by z-score and composite anomaly scoring"
      >Anomaly Scores</button
    >
    <button
      class="btn"
      class:btn-active={tab === "capture"}
      class:btn-ghost={tab !== "capture"}
      onclick={() => (tab = "capture")}
      data-tip="Physicians where one company dominates their total payments (capture ratio)"
      >Capture Ratio</button
    >
  </div>
</div>

<!-- ── Anomaly tab ─────────────────────────────────────────────── -->
{#if tab === "anomalies"}
  {#await anomalyPromise}
    <LoadingSpinner />
  {:then data}
    <!-- 4-Quadrant scatter -->
    <div class="card chart-card">
      <div class="chart-title">
        Risk Quadrant - Z-score (x) vs Composite Score (y) · size ∝ capture
        ratio · click to explore
      </div>
      <PlotlyChart
        traces={buildQuadrantScatter(data.rows, minScore)}
        layout={quadLayout}
        height={400}
        onClick={(pt) => {
          if (pt.customdata) window.location.hash = `node/${pt.customdata}`;
        }}
      />
    </div>

    <!-- Violin by specialty -->
    <div class="card chart-card">
      <div class="chart-title">
        Anomaly Score Distribution by Specialty (top 8)
      </div>
      <PlotlyChart
        traces={buildViolin(data.rows)}
        layout={violinLayout}
        height={300}
      />
    </div>

    <!-- Filtered table -->
    <div class="filter-row">
      <label
        class="range-label"
        data-tip="Composite anomaly score threshold — weighted blend of z-score, structural, and temporal signals (0–1)"
        >Min anomaly score: <strong>{minScore.toFixed(2)}</strong>
        <input type="range" min="0" max="1" step="0.05" bind:value={minScore} />
      </label>
    </div>
    {@const filtered = data.rows.filter(
      (r) => (r.composite_anomaly_score ?? 0) >= minScore,
    )}
    <div class="card">
      <div class="result-count">
        {filtered.length} anomalous nodes (score ≥ {minScore.toFixed(2)})
      </div>
      <DataTable
        columns={ANOMALY_COLS}
        rows={filtered}
        pageSize={25}
        tooltips={ANOMALY_TOOLTIPS}
        onRowClick={(row) => {
          if (row.id) window.location.hash = `node/${row.id}`;
        }}
      />
    </div>
  {:catch err}
    <p class="error-message">{err.message}</p>
  {/await}

  <!-- ── Capture tab ─────────────────────────────────────────────── -->
{:else}
  <div class="filter-row">
    <label
      class="range-label"
      data-tip="Capture ratio = fraction of physician's total payments from a single company. 1.0 = fully captured by one payer"
      >Min capture ratio: <strong>{minRatio.toFixed(2)}</strong>
      <input type="range" min="0.5" max="1" step="0.05" bind:value={minRatio} />
    </label>
  </div>

  {#await capturePromise}
    <LoadingSpinner />
  {:then data}
    <div class="card chart-card">
      <div class="chart-title">
        Captured Physicians - total payments (x) vs capture ratio (y) · size ∝
        single-company payment
      </div>
      <PlotlyChart
        traces={buildCaptureBubble(data.rows)}
        layout={captureLayout}
        height={360}
      />
    </div>

    <div class="card">
      <div class="result-count">
        {data.rows.length} pairs with capture ratio ≥ {minRatio.toFixed(2)}
      </div>
      <DataTable columns={CAPTURE_COLS} rows={data.rows} pageSize={25} tooltips={CAPTURE_TOOLTIPS} />
    </div>
  {:catch err}
    <p class="error-message">{err.message}</p>
  {/await}
{/if}

<style>
  .tabs {
    display: flex;
    gap: 6px;
  }

  .filter-row {
    display: flex;
    align-items: center;
    gap: 12px;
    margin-bottom: 16px;
    font-size: 13px;
    color: var(--color-muted);
  }
  .filter-row input {
    width: 160px;
  }

  .chart-card {
    margin-bottom: 16px;
  }

  .chart-title {
    font-size: 11px;
    font-weight: 600;
    text-transform: uppercase;
    letter-spacing: 0.6px;
    color: var(--color-muted);
    margin-bottom: 4px;
  }

  .result-count {
    font-size: 12px;
    color: var(--color-muted);
    margin-bottom: 10px;
  }
</style>
