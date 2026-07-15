<script>
  import {
    getEvolution,
    getEmerging,
    getJumps,
    getPaymentFormTrends,
    getTrajectory,
  } from "../api.js";
  import LoadingSpinner from "../components/LoadingSpinner.svelte";
  import DataTable from "../components/DataTable.svelte";
  import PlotlyChart from "../components/PlotlyChart.svelte";

  let tab = $state("evolution");

  let evolutionPromise = $state(getEvolution());
  let emergingPromise = $state(getEmerging("in_strength", 30));
  let jumpsPromise = $state(getJumps("in_strength", 200));
  let formTrendPromise = $state(getPaymentFormTrends("global"));

  // Entity trajectory on-demand (set when user clicks an emerging entity row)
  let trajectoryId = $state(null);
  let trajectoryName = $state("");
  let trajectoryPromise = $derived(
    trajectoryId
      ? getTrajectory("in_strength", trajectoryId)
      : Promise.resolve(null),
  );

  const EVOLVE_COLS = [
    "year",
    "n_nodes",
    "n_edges",
    "n_physicians",
    "total_payment_usd",
    "cash_share",
    "gini_global",
    "new_edges",
    "churned_edges",
    "persistent_edges",
  ];
  const EMERGE_COLS = [
    "rank",
    "name",
    "node_type",
    "specialty",
    "state",
    "slope",
    "growth_factor",
    "value_first",
    "value_last",
  ];
  const JUMPS_COLS = [
    "name",
    "node_type",
    "specialty",
    "state",
    "year_from",
    "year_to",
    "value_from",
    "value_to",
    "jump_factor",
  ];

  // ── Evolution: multi-line chart ─────────────────────────────────────────
  function buildEvoLines(rows) {
    return [
      {
        type: "scatter",
        mode: "lines+markers",
        name: "Total Payments",
        x: rows.map((r) => r.year),
        y: rows.map((r) => r.total_payment_usd),
        yaxis: "y",
        line: { color: "#59a14f", width: 2.5 },
        marker: { size: 6, color: "#59a14f" },
        hovertemplate: "%{x}: $%{y:,.0f}<extra>Total Payments</extra>",
      },
      {
        type: "scatter",
        mode: "lines+markers",
        name: "Cash Payments",
        x: rows.map((r) => r.year),
        y: rows.map((r) => r.cash_payment_usd),
        yaxis: "y",
        line: { color: "#e15759", width: 1.5, dash: "dot" },
        marker: { size: 5, color: "#e15759" },
        hovertemplate: "%{x}: $%{y:,.0f}<extra>Cash</extra>",
      },
      {
        type: "bar",
        name: "Edge Count",
        x: rows.map((r) => r.year),
        y: rows.map((r) => r.n_edges),
        yaxis: "y2",
        marker: { color: "rgba(78,121,167,0.3)" },
        hovertemplate: "%{x}: %{y:,} edges<extra>Edges</extra>",
      },
    ];
  }

  const evoLayout = {
    margin: { t: 20, r: 70, b: 48, l: 80 },
    xaxis: {
      dtick: 1,
      title: { text: "Year", font: { color: "#6b7280", size: 10 } },
    },
    yaxis: {
      title: { text: "Payments (USD)", font: { color: "#6b7280", size: 10 } },
      tickprefix: "$",
    },
    yaxis2: {
      title: { text: "Edge count", font: { color: "#6b7280", size: 10 } },
      overlaying: "y",
      side: "right",
    },
    legend: { orientation: "h", y: -0.18 },
    barmode: "overlay",
  };

  // ── Edge churn stacked bar ───────────────────────────────────────────────
  function buildChurn(rows) {
    return [
      {
        type: "bar",
        name: "New edges",
        x: rows.map((r) => r.year),
        y: rows.map((r) => r.new_edges),
        marker: { color: "#59a14f" },
        hovertemplate: "%{x}: %{y:,}<extra>New</extra>",
      },
      {
        type: "bar",
        name: "Persistent",
        x: rows.map((r) => r.year),
        y: rows.map((r) => r.persistent_edges),
        marker: { color: "#4e79a7" },
        hovertemplate: "%{x}: %{y:,}<extra>Persistent</extra>",
      },
      {
        type: "bar",
        name: "Churned",
        x: rows.map((r) => r.year),
        y: rows.map((r) => r.churned_edges),
        marker: { color: "#e15759" },
        hovertemplate: "%{x}: %{y:,}<extra>Churned</extra>",
      },
    ];
  }

  const churnLayout = {
    barmode: "stack",
    margin: { t: 12, r: 16, b: 48, l: 72 },
    xaxis: {
      dtick: 1,
      title: { text: "Year", font: { color: "#6b7280", size: 10 } },
    },
    yaxis: {
      title: { text: "Edge count", font: { color: "#6b7280", size: 10 } },
    },
    legend: { orientation: "h", y: -0.22 },
  };

  // ── Gini + HHI trend lines ───────────────────────────────────────────────
  function buildIneqLines(rows) {
    return [
      {
        type: "scatter",
        mode: "lines+markers",
        name: "Gini coefficient",
        x: rows.map((r) => r.year),
        y: rows.map((r) => r.gini_global),
        line: { color: "#f28e2b", width: 2 },
        marker: { size: 6 },
        hovertemplate: "%{x}: %{y:.4f}<extra>Gini</extra>",
      },
    ];
  }

  const ineqLayout = {
    margin: { t: 12, r: 16, b: 48, l: 72 },
    xaxis: {
      dtick: 1,
      title: { text: "Year", font: { color: "#6b7280", size: 10 } },
    },
    yaxis: {
      title: { text: "Gini coefficient", font: { color: "#6b7280", size: 10 } },
      range: [0, 1],
    },
  };

  // ── Payment form stacked area ────────────────────────────────────────────
  function buildFormArea(rows) {
    // Pivot: group by form, collect (year, total_amount)
    const forms = {};
    for (const r of rows) {
      if (!forms[r.form]) forms[r.form] = {};
      forms[r.form][r.year] =
        (forms[r.form][r.year] ?? 0) + (r.total_amount ?? 0);
    }
    const years = [...new Set(rows.map((r) => r.year))].sort();
    const palette = [
      "#7c6fcd",
      "#4e79a7",
      "#f28e2b",
      "#e15759",
      "#59a14f",
      "#76b7b2",
      "#edc948",
      "#b07aa1",
      "#ff9da7",
      "#9c755f",
    ];
    return Object.entries(forms).map(([form, byYear], i) => ({
      type: "scatter",
      mode: "lines",
      name: form,
      x: years,
      y: years.map((y) => byYear[y] ?? 0),
      fill: "tonexty",
      stackgroup: "one",
      line: { width: 0.5 },
      fillcolor: palette[i % palette.length] + "aa",
      marker: { color: palette[i % palette.length] },
      hovertemplate: `<b>${form}</b><br>%{x}: $%{y:,.0f}<extra></extra>`,
    }));
  }

  const formLayout = {
    margin: { t: 12, r: 16, b: 60, l: 80 },
    xaxis: {
      dtick: 1,
      title: { text: "Year", font: { color: "#6b7280", size: 10 } },
    },
    yaxis: {
      title: {
        text: "Total Amount (USD)",
        font: { color: "#6b7280", size: 10 },
      },
      tickprefix: "$",
    },
    legend: { orientation: "h", y: -0.28, font: { size: 10 } },
  };

  // ── Entity trajectory line (on-demand) ──────────────────────────────────
  function buildTrajectory(rows) {
    if (!rows?.length) return [];
    return [
      {
        type: "scatter",
        mode: "lines+markers",
        x: rows.map((r) => r.year),
        y: rows.map((r) => r.in_strength),
        line: { color: "#7c6fcd", width: 2.5 },
        marker: { size: 7, color: "#7c6fcd" },
        hovertemplate: "%{x}: $%{y:,.0f}<extra></extra>",
      },
    ];
  }

  const trajLayout = {
    margin: { t: 12, r: 16, b: 48, l: 80 },
    xaxis: { dtick: 1 },
    yaxis: {
      title: {
        text: "In-Strength (USD)",
        font: { color: "#6b7280", size: 10 },
      },
      tickprefix: "$",
    },
  };

  // ── Jump dot-plot ────────────────────────────────────────────────────────
  function buildJumpPlot(rows) {
    const byType = {};
    for (const r of rows) {
      const t = r.node_type ?? "Unknown";
      if (!byType[t]) byType[t] = [];
      byType[t].push(r);
    }
    const colors = {
      Physician: "#4e79a7",
      Manufacturer: "#f28e2b",
      TeachingHospital: "#e15759",
    };
    return Object.entries(byType).map(([type, pts]) => ({
      type: "scatter",
      mode: "markers",
      name: type,
      x: pts.map((r) => r.year_from + 0.5),
      y: pts.map((r) => r.jump_factor),
      text: pts.map((r) => r.name),
      hovertemplate:
        "<b>%{text}</b><br>Year: %{x:.0f}→<br>Jump: %{y:.1f}×<extra></extra>",
      marker: {
        color: colors[type] ?? "#888",
        size: 7,
        opacity: 0.75,
        line: { color: "rgba(0,0,0,0.25)", width: 0.5 },
      },
    }));
  }

  const jumpLayout = {
    margin: { t: 12, r: 16, b: 48, l: 72 },
    xaxis: {
      dtick: 1,
      title: { text: "Year of jump", font: { color: "#6b7280", size: 10 } },
    },
    yaxis: {
      title: { text: "Jump factor (×)", font: { color: "#6b7280", size: 10 } },
      type: "log",
    },
  };
</script>

<div class="page-header">
  <h1 class="page-title">Temporal Analysis</h1>
  <div class="tabs">
    <button
      class="btn"
      class:btn-active={tab === "evolution"}
      class:btn-ghost={tab !== "evolution"}
      onclick={() => (tab = "evolution")}>Evolution</button
    >
    <button
      class="btn"
      class:btn-active={tab === "forms"}
      class:btn-ghost={tab !== "forms"}
      onclick={() => (tab = "forms")}>Payment Forms</button
    >
    <button
      class="btn"
      class:btn-active={tab === "emerging"}
      class:btn-ghost={tab !== "emerging"}
      onclick={() => (tab = "emerging")}>Emerging</button
    >
    <button
      class="btn"
      class:btn-active={tab === "jumps"}
      class:btn-ghost={tab !== "jumps"}
      onclick={() => (tab = "jumps")}>Sudden Jumps</button
    >
  </div>
</div>

<!-- ── Evolution ─────────────────────────────────────────────────── -->
{#if tab === "evolution"}
  {#await evolutionPromise}
    <LoadingSpinner />
  {:then data}
    <div class="card chart-card">
      <div class="chart-title">Network payments & edge count 2020 – 2024</div>
      <PlotlyChart
        traces={buildEvoLines(data.rows)}
        layout={evoLayout}
        height={300}
      />
    </div>

    <div class="two-col">
      <div class="card chart-card">
        <div class="chart-title">Edge churn - new / persistent / churned</div>
        <PlotlyChart
          traces={buildChurn(data.rows)}
          layout={churnLayout}
          height={240}
        />
      </div>
      <div class="card chart-card">
        <div class="chart-title">Global inequality (Gini coefficient)</div>
        <PlotlyChart
          traces={buildIneqLines(data.rows)}
          layout={ineqLayout}
          height={240}
        />
      </div>
    </div>

    <div class="card">
      <DataTable columns={EVOLVE_COLS} rows={data.rows} pageSize={10} />
    </div>
  {:catch err}
    <p class="error-message">{err.message}</p>
  {/await}

  <!-- ── Payment forms stacked area ─────────────────────────────── -->
{:else if tab === "forms"}
  {#await formTrendPromise}
    <LoadingSpinner />
  {:then data}
    <div class="card chart-card">
      <div class="chart-title">
        Payment composition by form 2020 – 2024 (stacked area)
      </div>
      <PlotlyChart
        traces={buildFormArea(data.rows)}
        layout={formLayout}
        height={380}
      />
    </div>
  {:catch err}
    <p class="error-message">{err.message}</p>
  {/await}

  <!-- ── Emerging entities ──────────────────────────────────────── -->
{:else if tab === "emerging"}
  <div class="two-col-asym">
    <div>
      {#await emergingPromise}
        <LoadingSpinner />
      {:then data}
        <div class="card">
          <div class="chart-title">Click a row to load trajectory →</div>
          <DataTable
            columns={EMERGE_COLS}
            rows={data.rows}
            pageSize={30}
            onRowClick={(row) => {
              if (row.id) {
                trajectoryId = row.id;
                trajectoryName = row.name ?? row.id;
              } else window.location.hash = `node/${row.id}`;
            }}
          />
        </div>
      {:catch err}
        <p class="error-message">{err.message}</p>
      {/await}
    </div>

    <div>
      {#if trajectoryId}
        <div class="card chart-card">
          <div class="chart-title">Trajectory - {trajectoryName}</div>
          {#await trajectoryPromise}
            <LoadingSpinner />
          {:then data}
            {#if data?.rows?.length}
              <PlotlyChart
                traces={buildTrajectory(data.rows)}
                layout={trajLayout}
                height={260}
              />
            {:else}
              <p class="no-data">No trajectory data available.</p>
            {/if}
          {:catch}
            <p class="no-data">Could not load trajectory.</p>
          {/await}
        </div>
      {:else}
        <div class="card hint-card">
          <p class="hint">
            Select an entity in the table to view its 5-year trajectory.
          </p>
        </div>
      {/if}
    </div>
  </div>

  <!-- ── Sudden jumps ───────────────────────────────────────────── -->
{:else}
  {#await jumpsPromise}
    <LoadingSpinner />
  {:then data}
    <div class="card chart-card">
      <div class="chart-title">
        Sudden jump events - year of jump × jump factor (log scale)
      </div>
      <PlotlyChart
        traces={buildJumpPlot(data.rows)}
        layout={jumpLayout}
        height={320}
      />
    </div>
    <div class="card">
      <DataTable
        columns={JUMPS_COLS}
        rows={data.rows}
        pageSize={30}
        onRowClick={(row) => {
          if (row.id) window.location.hash = `node/${row.id}`;
        }}
      />
    </div>
  {:catch err}
    <p class="error-message">{err.message}</p>
  {/await}
{/if}

<style>
  .tabs {
    display: flex;
    gap: 6px;
    flex-wrap: wrap;
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

  .two-col {
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: 16px;
    margin-bottom: 16px;
  }

  .two-col-asym {
    display: grid;
    grid-template-columns: 1fr 380px;
    gap: 16px;
  }

  .hint-card {
    display: flex;
    align-items: center;
    justify-content: center;
    min-height: 200px;
  }
  .hint {
    font-size: 13px;
    color: var(--color-muted);
    font-style: italic;
    text-align: center;
  }
  .no-data {
    font-size: 13px;
    color: var(--color-muted);
    padding: 24px;
    text-align: center;
  }

  @media (max-width: 860px) {
    .two-col,
    .two-col-asym {
      grid-template-columns: 1fr;
    }
  }
</style>
