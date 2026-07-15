<script>
  import { selectedYear } from "../stores.js";
  import {
    getDashboardOverview,
    getEvolution,
    getConcentration,
  } from "../api.js";
  import LoadingSpinner from "../components/LoadingSpinner.svelte";
  import StatCard from "../components/StatCard.svelte";
  import DataTable from "../components/DataTable.svelte";
  import PlotlyChart from "../components/PlotlyChart.svelte";

  // ── Helpers ───────────────────────────────────────────────────
  function fmtUSD(n) {
    if (!n) return "$0";
    if (n >= 1e9) return `$${(n / 1e9).toFixed(2)}B`;
    if (n >= 1e6) return `$${(n / 1e6).toFixed(1)}M`;
    if (n >= 1e3) return `$${(n / 1e3).toFixed(1)}K`;
    return `$${n.toFixed(0)}`;
  }

  // ── Data fetches ──────────────────────────────────────────────
  let overviewPromise = $derived(getDashboardOverview($selectedYear, 10));
  let evolutionPromise = $state(getEvolution());
  let statePromise = $derived(getConcentration($selectedYear, "state", 60));

  // US state name → 2-letter code
  const STATE_ABB = {
    Alabama: "AL",
    Alaska: "AK",
    Arizona: "AZ",
    Arkansas: "AR",
    California: "CA",
    Colorado: "CO",
    Connecticut: "CT",
    Delaware: "DE",
    Florida: "FL",
    Georgia: "GA",
    Hawaii: "HI",
    Idaho: "ID",
    Illinois: "IL",
    Indiana: "IN",
    Iowa: "IA",
    Kansas: "KS",
    Kentucky: "KY",
    Louisiana: "LA",
    Maine: "ME",
    Maryland: "MD",
    Massachusetts: "MA",
    Michigan: "MI",
    Minnesota: "MN",
    Mississippi: "MS",
    Missouri: "MO",
    Montana: "MT",
    Nebraska: "NE",
    Nevada: "NV",
    "New Hampshire": "NH",
    "New Jersey": "NJ",
    "New Mexico": "NM",
    "New York": "NY",
    "North Carolina": "NC",
    "North Dakota": "ND",
    Ohio: "OH",
    Oklahoma: "OK",
    Oregon: "OR",
    Pennsylvania: "PA",
    "Rhode Island": "RI",
    "South Carolina": "SC",
    "South Dakota": "SD",
    Tennessee: "TN",
    Texas: "TX",
    Utah: "UT",
    Vermont: "VT",
    Virginia: "VA",
    Washington: "WA",
    "West Virginia": "WV",
    Wisconsin: "WI",
    Wyoming: "WY",
    "District of Columbia": "DC",
    // pass-through if already abbreviated
    AL: "AL",
    AK: "AK",
    AZ: "AZ",
    AR: "AR",
    CA: "CA",
    CO: "CO",
    CT: "CT",
    DE: "DE",
    FL: "FL",
    GA: "GA",
    HI: "HI",
    ID: "ID",
    IL: "IL",
    IN: "IN",
    IA: "IA",
    KS: "KS",
    KY: "KY",
    LA: "LA",
    ME: "ME",
    MD: "MD",
    MA: "MA",
    MI: "MI",
    MN: "MN",
    MS: "MS",
    MO: "MO",
    MT: "MT",
    NE: "NE",
    NV: "NV",
    NH: "NH",
    NJ: "NJ",
    NM: "NM",
    NY: "NY",
    NC: "NC",
    ND: "ND",
    OH: "OH",
    OK: "OK",
    OR: "OR",
    PA: "PA",
    RI: "RI",
    SC: "SC",
    SD: "SD",
    TN: "TN",
    TX: "TX",
    UT: "UT",
    VT: "VT",
    VA: "VA",
    WA: "WA",
    WV: "WV",
    WI: "WI",
    WY: "WY",
    DC: "DC",
  };

  // ── Build choropleth traces ───────────────────────────────────
  function choroplethTraces(rows) {
    const locs = [],
      vals = [],
      texts = [];
    for (const r of rows) {
      const code = STATE_ABB[r.state] ?? r.state;
      if (!code || code.length !== 2) continue;
      locs.push(code);
      vals.push(r.total_payment ?? 0);
      texts.push(
        `<b>${r.state}</b><br>` +
          `Total: ${fmtUSD(r.total_payment)}<br>` +
          `Gini: ${(r.gini ?? 0).toFixed(3)}<br>` +
          `HHI: ${(r.hhi ?? 0).toFixed(0)}`,
      );
    }
    return [
      {
        type: "choropleth",
        locationmode: "USA-states",
        locations: locs,
        z: vals,
        text: texts,
        hovertemplate: "%{text}<extra></extra>",
        colorscale: [
          [0, "rgba(78,121,167,0.15)"],
          [0.25, "rgba(78,121,167,0.4)"],
          [0.5, "rgba(124,111,205,0.6)"],
          [0.75, "rgba(225,87,89,0.65)"],
          [1, "rgba(225,87,89,0.9)"],
        ],
        colorbar: {
          thickness: 12,
          len: 0.7,
          title: { text: "USD", font: { color: "#6b7280", size: 10 } },
          tickfont: { color: "#6b7280", size: 10 },
          bgcolor: "rgba(26,29,39,0)",
          bordercolor: "#2a2d3e",
        },
        marker: { line: { color: "#2a2d3e", width: 0.5 } },
      },
    ];
  }

  const choroLayout = {
    geo: {
      scope: "usa",
      bgcolor: "#1a1d27",
      lakecolor: "#1a1d27",
      landcolor: "#12141f",
      subunitcolor: "#2a2d3e",
      showlakes: true,
      showland: true,
    },
    margin: { t: 10, r: 10, b: 10, l: 10 },
  };

  // ── Build edge-churn stacked bar ──────────────────────────────
  function churnTraces(rows) {
    const years = rows.map((r) => r.year);
    return [
      {
        type: "bar",
        name: "New",
        x: years,
        y: rows.map((r) => r.new_edges),
        marker: { color: "#59a14f" },
        hovertemplate: "New: %{y:,}<extra></extra>",
      },
      {
        type: "bar",
        name: "Persistent",
        x: years,
        y: rows.map((r) => r.persistent_edges),
        marker: { color: "#4e79a7" },
        hovertemplate: "Persistent: %{y:,}<extra></extra>",
      },
      {
        type: "bar",
        name: "Churned",
        x: years,
        y: rows.map((r) => r.churned_edges),
        marker: { color: "#e15759" },
        hovertemplate: "Churned: %{y:,}<extra></extra>",
      },
    ];
  }

  const churnLayout = {
    barmode: "stack",
    margin: { t: 10, r: 16, b: 36, l: 56 },
    xaxis: {
      title: { text: "Year", font: { color: "#6b7280", size: 10 } },
      dtick: 1,
    },
    yaxis: {
      title: { text: "Edge count", font: { color: "#6b7280", size: 10 } },
    },
    legend: { orientation: "h", y: -0.15 },
  };
</script>

<div class="page-header">
  <h1 class="page-title">Dashboard</h1>
  <span class="year-badge">{$selectedYear}</span>
</div>

<!-- Evolution data drives sparklines -->
{#await evolutionPromise then evo}
  {@const eRows = evo.rows ?? []}

  {#await overviewPromise}
    <LoadingSpinner />
  {:then data}
    {@const s = data.summary}

    <!-- KPI cards with sparklines -->
    <div class="stat-grid">
      <StatCard
        label="Total Nodes"
        value={s.nodes?.toLocaleString()}
        sparkData={eRows.map((r) => r.n_nodes)}
        trend={1}
      />
      <StatCard
        label="Total Edges"
        value={s.edges?.toLocaleString()}
        sparkData={eRows.map((r) => r.n_edges)}
        trend={1}
      />
      <StatCard
        label="Total Payments"
        value={fmtUSD(s.total_payment_usd)}
        color="var(--color-success)"
        sparkData={eRows.map((r) => r.total_payment_usd)}
        trend={1}
      />
      <StatCard
        label="Cash Payments"
        value={fmtUSD(s.cash_payment_usd)}
        sparkData={eRows.map((r) => r.cash_payment_usd)}
      />
      <StatCard
        label="Avg Payment"
        value={fmtUSD(s.avg_edge_weight_usd)}
        sparkData={eRows.map((r) => r.avg_payment_usd)}
      />
      <StatCard
        label="Gini (inequality)"
        value={(
          eRows.find((r) => r.year === $selectedYear)?.gini_global ?? 0
        ).toFixed(3)}
        color="var(--color-warning)"
        sparkData={eRows.map((r) => r.gini_global)}
        trend={-1}
      />
    </div>

    <!-- Node type + credential breakdown -->
    <div class="meta-grid">
      <div class="card">
        <div class="card-header">Node Types</div>
        {#each Object.entries(s.node_types ?? {}) as [type, count]}
          <div class="meta-row">
            <span class="badge badge-{type.toLowerCase()}">{type}</span>
            <strong>{count.toLocaleString()}</strong>
          </div>
        {/each}
      </div>

      <div class="card">
        <div class="card-header">Credential Types</div>
        {#each Object.entries(s.credential_types ?? {}).slice(0, 6) as [cred, count]}
          <div class="meta-row">
            <span class="cred">{cred}</span>
            <strong>{count.toLocaleString()}</strong>
          </div>
        {/each}
      </div>
    </div>

    <!-- US Payment Choropleth -->
    {#await statePromise then stateData}
      {#if stateData.rows?.length}
        <div class="card chart-section">
          <div class="card-header">
            Payment Volume by State - {$selectedYear}
          </div>
          <PlotlyChart
            traces={choroplethTraces(stateData.rows)}
            layout={choroLayout}
            height={340}
          />
        </div>
      {/if}
    {/await}

    <!-- Edge churn chart -->
    {#if eRows.length}
      <div class="card chart-section">
        <div class="card-header">Network Edge Dynamics 2020 – 2024</div>
        <PlotlyChart
          traces={churnTraces(eRows)}
          layout={churnLayout}
          height={220}
        />
      </div>
    {/if}

    <!-- Dashboard sections -->
    {#each data.sections as section}
      <div class="card section-block">
        <div class="card-header">{section.title}</div>
        <DataTable
          columns={section.table.columns.slice(0, 8)}
          rows={section.table.rows}
          pageSize={8}
          onRowClick={(row) => {
            if (row.id) window.location.hash = `node/${row.id}`;
          }}
        />
      </div>
    {/each}
  {:catch err}
    <p class="error-message">Failed to load: {err.message}</p>
  {/await}
{:catch}
  <!-- evolution failed - render without sparklines -->
  {#await overviewPromise}
    <LoadingSpinner />
  {:then data}
    {@const s = data.summary}
    <div class="stat-grid">
      <StatCard label="Total Nodes" value={s.nodes?.toLocaleString()} />
      <StatCard label="Total Edges" value={s.edges?.toLocaleString()} />
      <StatCard
        label="Total Payments"
        value={fmtUSD(s.total_payment_usd)}
        color="var(--color-success)"
      />
      <StatCard label="Cash Payments" value={fmtUSD(s.cash_payment_usd)} />
      <StatCard label="Avg Payment" value={fmtUSD(s.avg_edge_weight_usd)} />
    </div>
    {#each data.sections as section}
      <div class="card section-block">
        <div class="card-header">{section.title}</div>
        <DataTable
          columns={section.table.columns.slice(0, 8)}
          rows={section.table.rows}
          pageSize={8}
          onRowClick={(row) => {
            if (row.id) window.location.hash = `node/${row.id}`;
          }}
        />
      </div>
    {/each}
  {/await}
{/await}

<style>
  .year-badge {
    font-size: 13px;
    font-weight: 600;
    color: var(--color-accent);
    background: rgba(124, 111, 205, 0.12);
    padding: 3px 12px;
    border-radius: 9999px;
  }

  .meta-grid {
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: 14px;
    margin-bottom: 20px;
  }

  .card-header {
    font-size: 12px;
    font-weight: 600;
    text-transform: uppercase;
    letter-spacing: 0.7px;
    color: var(--color-muted);
    margin-bottom: 12px;
  }

  .meta-row {
    display: flex;
    align-items: center;
    justify-content: space-between;
    padding: 5px 0;
    border-bottom: 1px solid var(--color-border);
    font-size: 13px;
  }
  .meta-row:last-child {
    border-bottom: none;
  }
  .cred {
    color: var(--color-text);
  }

  .chart-section {
    margin-bottom: 20px;
  }
  .section-block {
    margin-bottom: 20px;
  }
</style>
