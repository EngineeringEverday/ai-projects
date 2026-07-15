<script>
  import { selectedYear } from "../stores.js";
  import { getTopProducts, getProductDiversity } from "../api.js";
  import LoadingSpinner from "../components/LoadingSpinner.svelte";
  import DataTable from "../components/DataTable.svelte";
  import PlotlyChart from "../components/PlotlyChart.svelte";

  let tab = $state("top");
  let productType = $state("drug");

  let topPromise = $derived(getTopProducts($selectedYear, productType, 80));
  let diversityPromise = $derived(getProductDiversity($selectedYear, 0, 200));

  const TOP_COLS = ["product_name", "n_records", "n_years"];
  const DIV_COLS = [
    "dst_id",
    "total_payment",
    "distinct_products",
    "product_diversity_score",
  ];

  // ── Treemap: top products by record count ──────────────────────────────────
  function buildTreemap(rows) {
    const top = rows.slice(0, 50);
    return [
      {
        type: "treemap",
        ids: top.map((r) => r.product_name),
        labels: top.map((r) => r.product_name),
        parents: top.map(() => ""),
        values: top.map((r) => r.n_records ?? 0),
        customdata: top,
        texttemplate: "<b>%{label}</b>",
        hovertemplate:
          "<b>%{label}</b><br>" +
          "Records: %{value:,}<br>" +
          "Years active: %{customdata.n_years}<br>" +
          "<extra></extra>",
        marker: {
          colors: top.map((r) => r.n_years ?? 0),
          colorscale: [
            [0, "#1a1d27"],
            [0.3, "#4e79a7"],
            [0.7, "#7c6fcd"],
            [1, "#59a14f"],
          ],
          colorbar: {
            title: {
              text: "Years active",
              font: { color: "#6b7280", size: 10 },
            },
            thickness: 12,
            tickfont: { color: "#6b7280", size: 10 },
            bgcolor: "rgba(26,29,39,0)",
            bordercolor: "#2a2d3e",
          },
          line: { color: "#1a1d27", width: 1.5 },
        },
        tiling: { pad: 3 },
        textfont: { size: 10, color: "#f1f5f9" },
      },
    ];
  }

  const treemapLayout = { margin: { t: 10, r: 10, b: 10, l: 10 } };

  // ── Top-20 horizontal bar chart ────────────────────────────────────────────
  function buildTopBar(rows) {
    const top = rows.slice(0, 20).reverse(); // reverse so largest is at top
    return [
      {
        type: "bar",
        orientation: "h",
        x: top.map((r) => r.n_records ?? 0),
        y: top.map((r) =>
          r.product_name?.length > 30
            ? r.product_name.slice(0, 30) + "…"
            : r.product_name,
        ),
        marker: {
          color: top.map((r) => r.n_years ?? 0),
          colorscale: [
            [0, "#4e79a7"],
            [0.5, "#7c6fcd"],
            [1, "#59a14f"],
          ],
          showscale: true,
          colorbar: {
            title: { text: "Years", font: { color: "#6b7280", size: 10 } },
            thickness: 10,
            tickfont: { color: "#6b7280", size: 10 },
            bgcolor: "rgba(26,29,39,0)",
            bordercolor: "#2a2d3e",
          },
        },
        hovertemplate: "<b>%{y}</b><br>Records: %{x:,}<extra></extra>",
      },
    ];
  }

  const barLayout = {
    margin: { t: 10, r: 80, b: 40, l: 220 },
    xaxis: {
      title: { text: "Payment records", font: { color: "#6b7280", size: 10 } },
    },
    yaxis: { tickfont: { size: 10 } },
  };

  // ── Diversity scatter: distinct products × total payment ───────────────────
  function buildDiversityScatter(rows) {
    return [
      {
        type: "scatter",
        mode: "markers",
        x: rows.map((r) => r.distinct_products),
        y: rows.map((r) => r.total_payment),
        customdata: rows.map((r) => r.dst_id),
        text: rows.map((r) => r.dst_id),
        hovertemplate:
          "<b>%{text}</b><br>" +
          "Products: %{x}<br>" +
          "Total payments: $%{y:,.0f}<br>" +
          "<extra></extra>",
        marker: {
          color: rows.map((r) => r.product_diversity_score ?? 0),
          colorscale: [
            [0, "#4e79a7"],
            [0.5, "#7c6fcd"],
            [1, "#e15759"],
          ],
          size: 6,
          opacity: 0.72,
          showscale: true,
          colorbar: {
            title: {
              text: "Diversity score",
              font: { color: "#6b7280", size: 10 },
            },
            thickness: 12,
            tickfont: { color: "#6b7280", size: 10 },
            bgcolor: "rgba(26,29,39,0)",
            bordercolor: "#2a2d3e",
          },
          line: { color: "rgba(0,0,0,0.25)", width: 0.5 },
        },
      },
    ];
  }

  const scatterLayout = {
    margin: { t: 16, r: 80, b: 56, l: 80 },
    xaxis: {
      title: {
        text: "Distinct products associated",
        font: { color: "#6b7280", size: 11 },
      },
    },
    yaxis: {
      title: {
        text: "Total payments received (USD)",
        font: { color: "#6b7280", size: 11 },
      },
      type: "log",
      tickprefix: "$",
    },
  };
</script>

<div class="page-header">
  <h1 class="page-title">Products</h1>
  <div class="tabs">
    <button
      class="btn"
      class:btn-active={tab === "top"}
      class:btn-ghost={tab !== "top"}
      onclick={() => (tab = "top")}>Top Products</button
    >
    <button
      class="btn"
      class:btn-active={tab === "diversity"}
      class:btn-ghost={tab !== "diversity"}
      onclick={() => (tab = "diversity")}>Product Diversity</button
    >
  </div>
</div>

<!-- ── Top Products ──────────────────────────────────────────────── -->
{#if tab === "top"}
  <div class="type-row">
    <button
      class="btn"
      class:btn-active={productType === "drug"}
      class:btn-ghost={productType !== "drug"}
      onclick={() => (productType = "drug")}>Drugs</button
    >
    <button
      class="btn"
      class:btn-active={productType === "device"}
      class:btn-ghost={productType !== "device"}
      onclick={() => (productType = "device")}>Devices</button
    >
  </div>

  {#await topPromise}
    <LoadingSpinner />
  {:then data}
    <!-- Treemap -->
    <div class="card chart-card">
      <div class="chart-title">
        Top {productType}s - size = records · colour = years active (green =
        longer-lived)
      </div>
      <PlotlyChart
        traces={buildTreemap(data.rows)}
        layout={treemapLayout}
        height={400}
      />
    </div>

    <!-- Top-20 bar -->
    <div class="card chart-card">
      <div class="chart-title">Top 20 by payment record count</div>
      <PlotlyChart
        traces={buildTopBar(data.rows)}
        layout={barLayout}
        height={360}
      />
    </div>

    <div class="card">
      <DataTable columns={TOP_COLS} rows={data.rows} pageSize={25} />
    </div>
  {:catch err}
    <p class="error-message">{err.message}</p>
  {/await}

  <!-- ── Product Diversity ─────────────────────────────────────────── -->
{:else}
  {#await diversityPromise}
    <LoadingSpinner />
  {:then data}
    <div class="card chart-card">
      <div class="chart-title">
        Physician product diversity - distinct products (x) × total payments (y,
        log) · colour = diversity score
      </div>
      <PlotlyChart
        traces={buildDiversityScatter(data.rows)}
        layout={scatterLayout}
        height={400}
        onClick={(pt) => {
          if (pt.customdata) window.location.hash = `node/${pt.customdata}`;
        }}
      />
    </div>
    <p class="hint">Click any point to open Node Detail.</p>

    <div class="card">
      <DataTable
        columns={DIV_COLS}
        rows={data.rows}
        pageSize={25}
        onRowClick={(row) => {
          if (row.dst_id) window.location.hash = `node/${row.dst_id}`;
        }}
      />
    </div>
  {:catch err}
    <p class="error-message">{err.message}</p>
  {/await}
{/if}

<style>
  .tabs,
  .type-row {
    display: flex;
    gap: 6px;
  }
  .type-row {
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
  .hint {
    font-size: 11px;
    color: var(--color-muted);
    margin-bottom: 16px;
    font-style: italic;
  }
</style>
