<script>
  import { selectedYear } from "../stores.js";
  import { getConcentration, getSeasonality, getPaymentForms } from "../api.js";
  import LoadingSpinner from "../components/LoadingSpinner.svelte";
  import DataTable from "../components/DataTable.svelte";
  import PlotlyChart from "../components/PlotlyChart.svelte";

  let tab = $state("concentration");
  let scope = $state("specialty");

  const CONC_TOOLTIPS = {
    gini: "Gini coefficient (0–1): higher = payments concentrated in fewer recipients",
    hhi: "Herfindahl-Hirschman Index: sum of squared market shares (0–10,000). >2,500 = highly concentrated",
    cr_5: "Concentration ratio of top 5 recipients — fraction of total payments they receive",
    norm_entropy: "Normalized Shannon entropy: higher = more evenly distributed payments",
    dominant_entity: "Entity receiving the largest share of payments in this group",
    top_entity_share: "Fraction of total payments received by the dominant entity",
  };

  const SCOPE_TIPS = {
    specialty: "Group by physician medical specialty (e.g. Cardiology, Oncology)",
    state: "Group by U.S. state where the physician practices",
    credential: "Group by physician credential (MD, DO, NP, PA, etc.)",
  };

  const YEARS = [2020, 2021, 2022, 2023, 2024];

  // Current-year data for table
  let concPromise = $derived(getConcentration($selectedYear, scope, 50));
  let seasonPromise = $derived(getSeasonality($selectedYear));
  let formsPromise = $derived(getPaymentForms($selectedYear));

  // Multi-year data for heatmap (all 5 years in parallel)
  let multiConcPromise = $derived(
    Promise.all(YEARS.map((y) => getConcentration(y, scope, 30))),
  );
  let multiSeasonPromise = $state(
    Promise.all(YEARS.map((y) => getSeasonality(y))),
  );

  const CONC_COLS = [
    "gini",
    "hhi",
    "cr_5",
    "norm_entropy",
    "dominant_entity",
    "top_entity_share",
  ];
  const SEASON_COLS = ["month", "total_amount", "n_edges"];
  const FORMS_COLS = ["form", "total_amount", "share", "specialty"];

  const MONTH_LABELS = [
    "Jan",
    "Feb",
    "Mar",
    "Apr",
    "May",
    "Jun",
    "Jul",
    "Aug",
    "Sep",
    "Oct",
    "Nov",
    "Dec",
  ];

  // ── Multi-year concentration heatmap (scope × year → gini) ───────────────
  function buildConcHeatmap(allData) {
    // allData[i] = { rows } for YEARS[i], scope as column e.g. "specialty"
    // Build entities × year matrix for gini
    const entityMap = {}; // entity → { year → gini }
    allData.forEach((d, yi) => {
      const yr = YEARS[yi];
      for (const r of d.rows ?? []) {
        const key =
          r[scope] ?? r.specialty ?? r.state ?? r.credential ?? "Unknown";
        if (!entityMap[key]) entityMap[key] = {};
        entityMap[key][yr] = r.gini ?? 0;
      }
    });

    // Rank entities by avg gini, take top 20
    const ranked = Object.entries(entityMap)
      .map(([k, byYear]) => ({
        k,
        avg: Object.values(byYear).reduce((s, v) => s + v, 0) / YEARS.length,
      }))
      .sort((a, b) => b.avg - a.avg)
      .slice(0, 20);

    const zRows = ranked.map(({ k }) =>
      YEARS.map((y) => entityMap[k][y] ?? null),
    );
    const yLabels = ranked.map(({ k }) =>
      k.length > 30 ? k.slice(0, 30) + "…" : k,
    );

    return [
      {
        type: "heatmap",
        x: YEARS,
        y: yLabels,
        z: zRows,
        colorscale: [
          [0, "#4e79a7"],
          [0.4, "#7c6fcd"],
          [0.7, "#f28e2b"],
          [1, "#e15759"],
        ],
        colorbar: {
          title: { text: "Gini", font: { color: "#6b7280", size: 10 } },
          thickness: 12,
          tickfont: { color: "#6b7280", size: 10 },
          bgcolor: "rgba(26,29,39,0)",
          bordercolor: "#2a2d3e",
        },
        hovertemplate:
          "<b>%{y}</b><br>Year %{x}: Gini = %{z:.4f}<extra></extra>",
        xgap: 2,
        ygap: 1,
      },
    ];
  }

  const heatLayout = {
    margin: { t: 10, r: 90, b: 48, l: 240 },
    xaxis: {
      dtick: 1,
      title: { text: "Year", font: { color: "#6b7280", size: 10 } },
    },
    yaxis: { tickfont: { size: 10 } },
  };

  // ── Seasonality calendar heatmap (month × year) ───────────────────────────
  function buildSeasonHeatmap(allSeasons) {
    const z = YEARS.map((_yr, yi) => {
      const rows = allSeasons[yi]?.rows ?? [];
      return MONTH_LABELS.map((_, mi) => {
        const row = rows.find((r) => +r.month === mi + 1);
        return row?.total_amount ?? null;
      });
    });
    return [
      {
        type: "heatmap",
        x: MONTH_LABELS,
        y: YEARS,
        z,
        colorscale: [
          [0, "#1a1d27"],
          [0.3, "#4e79a7"],
          [0.7, "#7c6fcd"],
          [1, "#e15759"],
        ],
        colorbar: {
          title: { text: "USD", font: { color: "#6b7280", size: 10 } },
          thickness: 12,
          tickfont: { color: "#6b7280", size: 10 },
          bgcolor: "rgba(26,29,39,0)",
          bordercolor: "#2a2d3e",
        },
        hovertemplate: "<b>%{y} %{x}</b><br>$%{z:,.0f}<extra></extra>",
        xgap: 2,
        ygap: 2,
      },
    ];
  }

  const seasonHeatLayout = {
    margin: { t: 10, r: 90, b: 48, l: 60 },
    xaxis: { title: { text: "Month", font: { color: "#6b7280", size: 10 } } },
    yaxis: {
      dtick: 1,
      title: { text: "Year", font: { color: "#6b7280", size: 10 } },
    },
  };

  // ── Seasonality bar chart (single year) ───────────────────────────────────
  function buildSeasonBar(rows) {
    return [
      {
        type: "bar",
        x: rows.map((r) => MONTH_LABELS[+r.month - 1] ?? r.month),
        y: rows.map((r) => r.total_amount),
        marker: { color: "#7c6fcd", opacity: 0.85 },
        hovertemplate: "<b>%{x}</b><br>$%{y:,.0f}<extra></extra>",
      },
    ];
  }

  const seasonBarLayout = {
    margin: { t: 10, r: 16, b: 48, l: 80 },
    xaxis: { title: { text: "Month", font: { color: "#6b7280", size: 10 } } },
    yaxis: {
      title: {
        text: "Total Amount (USD)",
        font: { color: "#6b7280", size: 10 },
      },
      tickprefix: "$",
    },
  };

  // ── Payment forms stacked bar (current year by specialty) ─────────────────
  function buildFormsBar(rows) {
    // Aggregate by form across specialties for current year
    const byForm = {};
    for (const r of rows) {
      if (!byForm[r.form]) byForm[r.form] = 0;
      byForm[r.form] += r.total_amount ?? 0;
    }
    const sorted = Object.entries(byForm).sort((a, b) => b[1] - a[1]);
    const palette = [
      "#7c6fcd",
      "#4e79a7",
      "#f28e2b",
      "#e15759",
      "#59a14f",
      "#76b7b2",
      "#edc948",
      "#b07aa1",
    ];
    return sorted.map(([form, val], i) => ({
      type: "bar",
      name: form,
      x: [form.length > 20 ? form.slice(0, 20) + "…" : form],
      y: [val],
      marker: { color: palette[i % palette.length] },
      hovertemplate: `<b>${form}</b><br>$%{y:,.0f}<extra></extra>`,
    }));
  }

  const formsBarLayout = {
    barmode: "group",
    margin: { t: 10, r: 16, b: 100, l: 80 },
    xaxis: { tickangle: -35, tickfont: { size: 10 } },
    yaxis: {
      title: {
        text: "Total Amount (USD)",
        font: { color: "#6b7280", size: 10 },
      },
      tickprefix: "$",
    },
    showlegend: false,
  };

  // ── Lorenz-approximation (Gini trend line) ────────────────────────────────
  function buildGiniTrend(allData) {
    // One line per scope value for top 5 entities
    const top5 = allData[allData.length - 1]?.rows?.slice(0, 5) ?? [];
    const palette = ["#7c6fcd", "#4e79a7", "#f28e2b", "#e15759", "#59a14f"];
    return top5.map((row, i) => {
      const key =
        row[scope] ?? row.specialty ?? row.state ?? row.credential ?? `#${i}`;
      const vals = allData.map((d, yi) => {
        const match = d.rows?.find(
          (r) => (r[scope] ?? r.specialty ?? r.state ?? r.credential) === key,
        );
        return match?.gini ?? null;
      });
      return {
        type: "scatter",
        mode: "lines+markers",
        name: key.length > 24 ? key.slice(0, 24) + "…" : key,
        x: YEARS,
        y: vals,
        connectgaps: true,
        line: { color: palette[i], width: 2 },
        marker: { size: 6, color: palette[i] },
        hovertemplate: `<b>${key}</b><br>%{x}: Gini=%{y:.4f}<extra></extra>`,
      };
    });
  }

  const giniTrendLayout = {
    margin: { t: 12, r: 16, b: 48, l: 72 },
    xaxis: {
      dtick: 1,
      title: { text: "Year", font: { color: "#6b7280", size: 10 } },
    },
    yaxis: {
      title: { text: "Gini coefficient", font: { color: "#6b7280", size: 10 } },
      range: [0, 1],
    },
    legend: { font: { size: 10 } },
  };
</script>

<div class="page-header">
  <h1 class="page-title">Concentration Analysis</h1>
  <div class="tabs">
    <button
      class="btn"
      class:btn-active={tab === "concentration"}
      class:btn-ghost={tab !== "concentration"}
      onclick={() => (tab = "concentration")}
      data-tip="Gini, HHI & entropy concentration metrics by specialty / state / credential"
      >Concentration</button
    >
    <button
      class="btn"
      class:btn-active={tab === "seasonality"}
      class:btn-ghost={tab !== "seasonality"}
      onclick={() => (tab = "seasonality")}
      data-tip="Monthly payment patterns across all years"
      >Seasonality</button
    >
    <button
      class="btn"
      class:btn-active={tab === "forms"}
      class:btn-ghost={tab !== "forms"}
      onclick={() => (tab = "forms")}
      data-tip="Payment type breakdown: cash, stock, in-kind, travel, etc."
      >Payment Forms</button
    >
  </div>
</div>

<!-- ── Concentration tab ──────────────────────────────────────────── -->
{#if tab === "concentration"}
  <div class="scope-row">
    <span class="scope-label">Scope:</span>
    {#each ["specialty", "state", "credential"] as s}
      <button
        class="btn"
        class:btn-active={scope === s}
        class:btn-ghost={scope !== s}
        onclick={() => (scope = s)}
        data-tip={SCOPE_TIPS[s]}>{s}</button
      >
    {/each}
  </div>

  {#await multiConcPromise}
    <LoadingSpinner />
  {:then allData}
    <!-- Multi-year Gini heatmap -->
    <div class="card chart-card">
      <div class="chart-title">
        Gini coefficient heatmap - top 20 {scope}s across 2020–2024
      </div>
      <PlotlyChart
        traces={buildConcHeatmap(allData)}
        layout={heatLayout}
        height={460}
      />
    </div>

    <!-- Gini trend lines for top entities -->
    <div class="card chart-card">
      <div class="chart-title">Gini trend - top 5 {scope}s over time</div>
      <PlotlyChart
        traces={buildGiniTrend(allData)}
        layout={giniTrendLayout}
        height={240}
      />
    </div>
  {:catch err}
    <p class="error-message">{err.message}</p>
  {/await}

  {#await concPromise}
    <LoadingSpinner />
  {:then data}
    <div class="card">
      <DataTable
        columns={[scope, ...CONC_COLS]}
        rows={data.rows}
        pageSize={25}
        tooltips={CONC_TOOLTIPS}
      />
    </div>
  {:catch err}
    <p class="error-message">{err.message}</p>
  {/await}

  <!-- ── Seasonality tab ────────────────────────────────────────────── -->
{:else if tab === "seasonality"}
  <!-- Calendar heatmap: month × year -->
  {#await multiSeasonPromise}
    <LoadingSpinner />
  {:then allSeasons}
    <div class="card chart-card">
      <div class="chart-title">
        Payment calendar - month × year (darker = higher payments)
      </div>
      <PlotlyChart
        traces={buildSeasonHeatmap(allSeasons)}
        layout={seasonHeatLayout}
        height={220}
      />
    </div>
  {:catch err}
    <p class="error-message">{err.message}</p>
  {/await}

  <!-- Bar chart for selected year -->
  {#await seasonPromise}
    <LoadingSpinner />
  {:then data}
    <div class="card chart-card">
      <div class="chart-title">Monthly payments - {$selectedYear}</div>
      <PlotlyChart
        traces={buildSeasonBar(data.rows)}
        layout={seasonBarLayout}
        height={240}
      />
    </div>
    <div class="card">
      <DataTable columns={SEASON_COLS} rows={data.rows} pageSize={12} />
    </div>
  {:catch err}
    <p class="error-message">{err.message}</p>
  {/await}

  <!-- ── Forms tab ──────────────────────────────────────────────────── -->
{:else}
  {#await formsPromise}
    <LoadingSpinner />
  {:then data}
    <div class="card chart-card">
      <div class="chart-title">Payment form breakdown - {$selectedYear}</div>
      <PlotlyChart
        traces={buildFormsBar(data.rows)}
        layout={formsBarLayout}
        height={300}
      />
    </div>
    <div class="card">
      <DataTable columns={FORMS_COLS} rows={data.rows} pageSize={30} />
    </div>
  {:catch err}
    <p class="error-message">{err.message}</p>
  {/await}
{/if}

<style>
  .tabs,
  .scope-row {
    display: flex;
    gap: 6px;
    align-items: center;
    flex-wrap: wrap;
  }
  .scope-label {
    font-size: 12px;
    color: var(--color-muted);
    margin-right: 4px;
  }
  .scope-row {
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
