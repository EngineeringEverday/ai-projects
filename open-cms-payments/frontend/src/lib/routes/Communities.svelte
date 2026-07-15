<script>
  import { selectedYear } from "../stores.js";
  import { getCommunitySummaries, getCommunityAssignments } from "../api.js";
  import LoadingSpinner from "../components/LoadingSpinner.svelte";
  import DataTable from "../components/DataTable.svelte";
  import PlotlyChart from "../components/PlotlyChart.svelte";

  let tab = $state("summaries");
  let mode = $state("bipartite");
  let assignmentsInitiated = $state(false);

  const MODE_TIPS = {
    bipartite: "Louvain communities on the full physician–company bipartite graph",
    physician_projection: "Communities within the physician co-payment projection (shared payers)",
    company_projection: "Communities within the company co-payment projection (shared recipients)",
  };

  const SUMMARY_TOOLTIPS = {
    community_id: "Unique cluster ID assigned by the Louvain algorithm",
    size: "Total number of nodes (physicians + companies) in this community",
    n_companies: "Number of pharmaceutical companies in this community",
    n_physicians: "Number of physicians in this community",
    n_hospitals: "Number of teaching hospitals in this community",
    total_payment_usd: "Total payment dollars flowing within this community",
    cash_share: "Fraction of payments made in cash form (vs. stock, in-kind, etc.)",
    top_specialties: "Most common physician specialties in this community",
  };

  let summaryPromise = $derived(getCommunitySummaries($selectedYear));
  // Assignments are a 9MB+ file — only fetch when explicitly initiated
  let assignmentPromise = $derived(
    assignmentsInitiated && tab === "assignments"
      ? getCommunityAssignments($selectedYear, mode)
      : null,
  );

  const SUMMARY_COLS = [
    "community_id",
    "size",
    "n_companies",
    "n_physicians",
    "n_hospitals",
    "total_payment_usd",
    "cash_share",
    "top_specialties",
  ];
  const ASSIGNMENT_COLS = [
    "name",
    "node_type",
    "community_id",
    "specialty",
    "state",
  ];

  // ── Treemap: communities sized by payment, coloured by cash share ──────
  function buildTreemap(rows) {
    // Sort descending by size; take top 60 to keep labels readable
    const top = [...rows]
      .sort((a, b) => (b.total_payment_usd ?? 0) - (a.total_payment_usd ?? 0))
      .slice(0, 60);

    return [
      {
        type: "treemap",
        ids: top.map((r) => `C${r.community_id}`),
        labels: top.map((r) => `C${r.community_id}`),
        parents: top.map(() => ""),
        values: top.map((r) => r.total_payment_usd ?? 0),
        customdata: top,
        texttemplate: "<b>C%{label}</b><br>%{value:$,.0f}",
        hovertemplate:
          "<b>Community %{label}</b><br>" +
          "Total payments: %{value:$,.0f}<br>" +
          "Size: %{customdata.size}<br>" +
          "Companies: %{customdata.n_companies}<br>" +
          "Physicians: %{customdata.n_physicians}<br>" +
          "Cash share: %{customdata.cash_share:.1%}<br>" +
          "<extra></extra>",
        marker: {
          colors: top.map((r) => r.cash_share ?? 0),
          colorscale: [
            [0, "#4e79a7"],
            [0.3, "#7c6fcd"],
            [0.6, "#f28e2b"],
            [1, "#e15759"],
          ],
          colorbar: {
            title: { text: "Cash share", font: { color: "#6b7280", size: 10 } },
            tickformat: ".0%",
            thickness: 12,
            tickfont: { color: "#6b7280", size: 10 },
            bgcolor: "rgba(26,29,39,0)",
            bordercolor: "#2a2d3e",
          },
          line: { color: "#1a1d27", width: 1.5 },
        },
        tiling: { pad: 3 },
        textfont: { size: 11, color: "#f1f5f9" },
      },
    ];
  }

  const treemapLayout = {
    margin: { t: 10, r: 10, b: 10, l: 10 },
  };

  // ── Bubble chart: n_physicians (x) × n_companies (y), size=payment ────
  function buildBubble(rows) {
    return [
      {
        type: "scatter",
        mode: "markers",
        x: rows.map((r) => r.n_physicians),
        y: rows.map((r) => r.n_companies),
        customdata: rows.map((r) => r.community_id),
        text: rows.map(
          (r) =>
            `C${r.community_id}<br>` +
            `${r.top_specialties?.split("|")[0] ?? ""}`,
        ),
        hovertemplate:
          "<b>%{text}</b><br>" +
          "Physicians: %{x}<br>" +
          "Companies: %{y}<br>" +
          "<extra></extra>",
        marker: {
          size: rows.map((r) =>
            Math.max(
              6,
              Math.min(40, 4 + Math.sqrt((r.total_payment_usd ?? 0) / 1e6)),
            ),
          ),
          color: rows.map((r) => r.cash_share ?? 0),
          colorscale: [
            [0, "#4e79a7"],
            [0.5, "#7c6fcd"],
            [1, "#e15759"],
          ],
          opacity: 0.75,
          showscale: true,
          colorbar: {
            title: { text: "Cash share", font: { color: "#6b7280", size: 10 } },
            tickformat: ".0%",
            thickness: 12,
            tickfont: { color: "#6b7280", size: 10 },
            bgcolor: "rgba(26,29,39,0)",
            bordercolor: "#2a2d3e",
          },
          line: { color: "rgba(0,0,0,0.3)", width: 0.5 },
        },
      },
    ];
  }

  const bubbleLayout = {
    margin: { t: 16, r: 70, b: 56, l: 64 },
    xaxis: {
      title: { text: "# Physicians", font: { color: "#6b7280", size: 11 } },
    },
    yaxis: {
      title: { text: "# Companies", font: { color: "#6b7280", size: 11 } },
    },
  };
</script>

<div class="page-header">
  <h1 class="page-title">Communities</h1>
  <div class="tabs">
    <button
      class="btn"
      class:btn-active={tab === "summaries"}
      class:btn-ghost={tab !== "summaries"}
      onclick={() => (tab = "summaries")}
      data-tip="Per-community statistics: size, payment volume, cash share, top specialties"
      >Summaries</button
    >
    <button
      class="btn"
      class:btn-active={tab === "assignments"}
      class:btn-ghost={tab !== "assignments"}
      onclick={() => (tab = "assignments")}
      data-tip="Individual node → community assignments across different graph projections"
      >Assignments</button
    >
  </div>
</div>

<!-- ── Summaries tab ───────────────────────────────────────────── -->
{#if tab === "summaries"}
  {#await summaryPromise}
    <LoadingSpinner />
  {:then data}
    <!-- Treemap -->
    <div class="card chart-card">
      <div class="chart-title">
        Community Treemap - size = total payments · colour = cash share (blue →
        red)
      </div>
      <PlotlyChart
        traces={buildTreemap(data.rows)}
        layout={treemapLayout}
        height={440}
      />
    </div>

    <!-- Bubble: physicians × companies -->
    <div class="card chart-card">
      <div class="chart-title">
        Physician count × Company count - bubble size = total payments · colour
        = cash share
      </div>
      <PlotlyChart
        traces={buildBubble(data.rows)}
        layout={bubbleLayout}
        height={320}
      />
    </div>

    <!-- Table -->
    <div class="card">
      <DataTable columns={SUMMARY_COLS} rows={data.rows} pageSize={20} tooltips={SUMMARY_TOOLTIPS} />
    </div>
  {:catch err}
    <p class="error-message">{err.message}</p>
  {/await}

  <!-- ── Assignments tab ────────────────────────────────────────── -->
{:else}
  <div class="mode-row">
    <span class="mode-label">Projection:</span>
    {#each ["bipartite", "physician_projection", "company_projection"] as m}
      <button
        class="btn"
        class:btn-active={mode === m}
        class:btn-ghost={mode !== m}
        onclick={() => (mode = m)}
        data-tip={MODE_TIPS[m]}>{m}</button
      >
    {/each}
  </div>

  {#if !assignmentsInitiated}
    <div class="load-gate">
      <p class="load-gate-desc">Node assignment data is ~9MB. Load when ready.</p>
      <button class="load-gate-btn" onclick={() => (assignmentsInitiated = true)}>
        Load Assignments
      </button>
    </div>
  {:else}
    {#await assignmentPromise}
      <LoadingSpinner />
    {:then data}
      <div class="card">
        <DataTable
          columns={ASSIGNMENT_COLS}
          rows={data?.rows ?? []}
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
{/if}

<style>
  .tabs,
  .mode-row {
    display: flex;
    gap: 6px;
    align-items: center;
    flex-wrap: wrap;
  }
  .mode-label {
    font-size: 12px;
    color: var(--color-muted);
    margin-right: 4px;
  }
  .mode-row {
    margin-bottom: 16px;
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
</style>
