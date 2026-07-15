<script>
  import { selectedYear, riskSection, openNode } from "../stores.js";
  import {
    getAnomalies,
    getCapture,
    getCommunitySummaries,
    getConcentration,
    getCentrality,
    emptyTable,
  } from "../api.js";
  import PlotlyChart from "../components/PlotlyChart.svelte";
  import CommunityViz from "../components/CommunityViz.svelte";
  import { Zap, Gauge, Users, ChevronDown, ChevronUp } from "lucide-svelte";

  // ── Section accordion ─────────────────────────────────────────
  function toggleSection(s) {
    riskSection.update((cur) => (cur === s ? null : s));
  }

  // ── Shared data — lazy: only fetch when accordion section is open ────────
  const YEARS = [2020, 2021, 2022, 2023, 2024];

  let captureInitiated = $state(false);
  let capturePromise = $derived(
    captureInitiated && $riskSection === "capture"
      ? getCapture($selectedYear, 0.5, 100)
      : emptyTable(),
  );
  let communityPromise = $derived(
    $riskSection === "communities" ? getCommunitySummaries($selectedYear) : emptyTable(),
  );
  let concPromise = $derived(
    $riskSection === "concentration"
      ? getConcentration($selectedYear, "specialty", 40)
      : emptyTable(),
  );
  let centralityPromise = $derived(
    $riskSection === "centrality"
      ? getCentrality($selectedYear, "pagerank", 100)
      : emptyTable(),
  );

  // Sequential multi-year fetch — avoids 5 simultaneous requests
  async function fetchMultiConc() {
    const results = [];
    for (const y of YEARS) {
      results.push(await getConcentration(y, "specialty", 20));
    }
    return results;
  }
  let multiConcPromise = $derived(
    $riskSection === "concentration" ? fetchMultiConc() : Promise.resolve([]),
  );

  // ── Anomaly data - $state/$effect to avoid template assignment bug ──
  let anomalyData = $state(null);
  let anomalyLoading = $state(false);
  let anomalyError = $state("");

  $effect(() => {
    const year = $selectedYear;
    anomalyLoading = true;
    anomalyData = null;
    anomalyError = "";
    getAnomalies(year, 0.0, 600)
      .then((d) => {
        anomalyData = d;
        // Update quadrant counts
        const rows = d.rows ?? [];
        highCount = rows.filter(
          (r) =>
            (r.zscore_global ?? 0) > 2 &&
            (r.composite_anomaly_score ?? 0) > 0.5,
        ).length;
        watchCount =
          rows.filter(
            (r) =>
              Math.abs(r.zscore_global ?? 0) > 1.5 ||
              (r.composite_anomaly_score ?? 0) > 0.3,
          ).length - highCount;
        anomalyLoading = false;
      })
      .catch((e) => {
        anomalyError = e.message;
        anomalyLoading = false;
      });
  });

  // ── Formatters ────────────────────────────────────────────────
  function fmtUSD(n) {
    if (!n) return "$0";
    if (n >= 1e6) return `$${(n / 1e6).toFixed(2)}M`;
    if (n >= 1e3) return `$${(n / 1e3).toFixed(1)}K`;
    return `$${(+n).toFixed(0)}`;
  }

  // ── Anomaly scatter (Plotly 2D fallback + detail) ─────────────
  function buildAnomalyScatter(rows) {
    const high = rows.filter(
      (r) =>
        (r.zscore_global ?? 0) > 2 && (r.composite_anomaly_score ?? 0) > 0.5,
    );
    const watch = rows.filter(
      (r) =>
        (Math.abs(r.zscore_global ?? 0) > 1.5 ||
          (r.composite_anomaly_score ?? 0) > 0.3) &&
        !((r.zscore_global ?? 0) > 2 && (r.composite_anomaly_score ?? 0) > 0.5),
    );
    const ok = rows.filter(
      (r) =>
        Math.abs(r.zscore_global ?? 0) <= 1.5 &&
        (r.composite_anomaly_score ?? 0) <= 0.3,
    );
    const mkTrace = (subset, name, color) => ({
      type: "scatter",
      mode: "markers",
      name,
      x: subset.map((r) => r.zscore_global ?? 0),
      y: subset.map((r) => r.composite_anomaly_score ?? 0),
      customdata: subset.map((r) => r.id),
      text: subset.map((r) => r.id ?? ""),
      marker: {
        color,
        size: 6,
        opacity: 0.75,
        line: { color: "rgba(0,0,0,.2)", width: 0.5 },
      },
      hovertemplate:
        "<b>%{text}</b><br>Z-score: %{x:.2f}<br>Composite: %{y:.3f}<extra></extra>",
    });
    return [
      mkTrace(high, "High Risk", "#F85149"),
      mkTrace(watch, "Watchlist", "#D29922"),
      mkTrace(ok, "Normal", "#2F81F7"),
    ];
  }

  const anomalyLayout = {
    margin: { t: 8, r: 20, b: 48, l: 60 },
    xaxis: {
      title: { text: "Z-Score (global)", font: { color: "#7D8590", size: 10 } },
      tickfont: { size: 10, color: "#7D8590" },
      gridcolor: "#30363D",
      zeroline: false,
    },
    yaxis: {
      title: {
        text: "Composite Anomaly Score",
        font: { color: "#7D8590", size: 10 },
      },
      tickfont: { size: 10, color: "#7D8590" },
      gridcolor: "#30363D",
      zeroline: false,
    },
    shapes: [
      {
        type: "line",
        x0: 2,
        x1: 2,
        y0: -0.1,
        y1: 1.1,
        line: { color: "rgba(248,113,113,.4)", width: 1.5, dash: "dot" },
      },
      {
        type: "line",
        x0: -1,
        x1: 10,
        y0: 0.5,
        y1: 0.5,
        line: { color: "rgba(248,113,113,.4)", width: 1.5, dash: "dot" },
      },
    ],
    legend: { font: { size: 10 } },
    paper_bgcolor: "transparent",
    plot_bgcolor: "transparent",
  };

  // ── Community treemap ─────────────────────────────────────────
  function buildCommTreemap(rows) {
    const top = rows.slice(0, 40);
    return [
      {
        type: "treemap",
        ids: top.map((r) => `C${r.community_id}`),
        labels: top.map((r) => `C${r.community_id}`),
        parents: top.map(() => ""),
        values: top.map((r) => r.total_payment_usd ?? r.total_payments ?? 0),
        customdata: top,
        texttemplate: "<b>C%{customdata.community_id}</b><br>%{value:$,.0f}",
        hovertemplate:
          "<b>Community %{customdata.community_id}</b><br>" +
          "Total: $%{value:,.0f}<br>" +
          "Members: %{customdata.size}<br>" +
          "Cash share: %{customdata.cash_share:.1%}<extra></extra>",
        marker: {
          colors: top.map((r) => r.cash_share ?? 0),
          colorscale: [
            [0, "#2F81F7"],
            [0.5, "#8957E5"],
            [1, "#F85149"],
          ],
          colorbar: {
            title: { text: "Cash share", font: { color: "#7D8590", size: 9 } },
            thickness: 10,
            tickfont: { color: "#7D8590", size: 9 },
          },
          line: { color: "#0D1117", width: 1 },
        },
        textfont: { size: 10, color: "#f0f4ff" },
      },
    ];
  }

  const commTreemapLayout = {
    margin: { t: 4, r: 4, b: 4, l: 4 },
    paper_bgcolor: "transparent",
  };

  // ── Concentration heatmap ─────────────────────────────────────
  function buildConcHeatmap(allData) {
    const entityMap = {};
    allData.forEach((d, yi) => {
      const yr = YEARS[yi];
      (d.rows ?? []).forEach((r) => {
        const key = r.specialty ?? r.state ?? r.credential ?? "Unknown";
        if (!entityMap[key]) entityMap[key] = {};
        entityMap[key][yr] = r.gini ?? 0;
      });
    });
    const ranked = Object.entries(entityMap)
      .map(([k, byYear]) => ({
        k,
        avg: YEARS.reduce((s, y) => s + (byYear[y] ?? 0), 0) / YEARS.length,
      }))
      .sort((a, b) => b.avg - a.avg)
      .slice(0, 20);
    const z = ranked.map(({ k }) => YEARS.map((y) => entityMap[k][y] ?? null));
    const yLabels = ranked.map(({ k }) =>
      k.length > 30 ? k.slice(0, 30) + "…" : k,
    );
    return [
      {
        type: "heatmap",
        x: YEARS,
        y: yLabels,
        z,
        colorscale: [
          [0, "#2F81F7"],
          [0.4, "#8957E5"],
          [0.7, "#F0883E"],
          [1, "#F85149"],
        ],
        colorbar: {
          title: { text: "Gini", font: { color: "#7D8590", size: 9 } },
          thickness: 10,
          tickfont: { color: "#7D8590", size: 9 },
        },
        hovertemplate: "<b>%{y}</b><br>%{x}: Gini=%{z:.4f}<extra></extra>",
        xgap: 2,
        ygap: 1,
      },
    ];
  }

  const heatLayout = {
    margin: { t: 8, r: 90, b: 40, l: 220 },
    xaxis: { dtick: 1, tickfont: { size: 10, color: "#7D8590" } },
    yaxis: { tickfont: { size: 10 } },
    paper_bgcolor: "transparent",
    plot_bgcolor: "transparent",
  };

  // ── Violin chart by specialty ─────────────────────────────────
  function buildViolins(rows) {
    const specMap = {};
    rows.forEach((r) => {
      const sp = (r.specialty ?? "Unknown")
        .split("|")
        .pop()
        .trim()
        .slice(0, 24);
      if (!specMap[sp]) specMap[sp] = [];
      specMap[sp].push(r.composite_anomaly_score ?? 0);
    });
    const topSpecs = Object.entries(specMap)
      .sort((a, b) => b[1].length - a[1].length)
      .slice(0, 8);
    const palette = [
      "#8957E5",
      "#2F81F7",
      "#F0883E",
      "#F85149",
      "#3FB950",
      "#58A6FF",
      "#D29922",
      "#BC8CFF",
    ];
    return topSpecs.map(([sp, vals], i) => ({
      type: "violin",
      y: vals,
      name: sp,
      box: { visible: true },
      meanline: { visible: true },
      fillcolor: palette[i % palette.length],
      opacity: 0.6,
      line: { color: palette[i % palette.length], width: 1.5 },
      hovertemplate: `<b>${sp}</b><br>Score: %{y:.3f}<extra></extra>`,
    }));
  }

  const violinLayout = {
    margin: { t: 8, r: 16, b: 80, l: 60 },
    yaxis: {
      title: {
        text: "Composite Anomaly Score",
        font: { color: "#7D8590", size: 10 },
      },
      tickfont: { size: 10, color: "#7D8590" },
      gridcolor: "#30363D",
    },
    xaxis: { tickangle: -35, tickfont: { size: 9 } },
    showlegend: false,
    violingap: 0.05,
    violingroupgap: 0,
    paper_bgcolor: "transparent",
    plot_bgcolor: "transparent",
  };

  // ── Capture scatter ───────────────────────────────────────────
  // API fields: physician_id, physician_name, company_name,
  //             total_physician_payment, company_payment, capture_ratio
  function buildCapture(rows) {
    // Group by capture bucket for color differentiation
    const high = rows.filter((r) => (r.capture_ratio ?? 0) >= 0.8);
    const med = rows.filter(
      (r) => (r.capture_ratio ?? 0) >= 0.5 && (r.capture_ratio ?? 0) < 0.8,
    );

    const mkTrace = (subset, name, col) => ({
      type: "scatter",
      mode: "markers",
      name,
      x: subset.map((r) => r.total_physician_payment ?? 0),
      y: subset.map((r) => r.capture_ratio ?? 0),
      text: subset.map((r) => r.physician_name ?? r.physician_id ?? ""),
      customdata: subset.map((r) => ({
        id: r.physician_id,
        company: r.company_name ?? "",
        state: r.state ?? "-",
        specialty: (r.specialty ?? "").split("|").pop(),
        co_pay: r.company_payment ?? 0,
      })),
      marker: {
        color: col,
        size: subset.map((r) =>
          Math.max(4, Math.min(16, 4 + Math.log1p(r.company_payment ?? 0) / 4)),
        ),
        opacity: 0.78,
        line: { color: "rgba(0,0,0,0.2)", width: 0.5 },
      },
      hovertemplate:
        "<b>%{text}</b><br>" +
        "%{customdata.specialty} · %{customdata.state}<br>" +
        "Total received: $%{x:,.0f}<br>" +
        "Capture ratio: %{y:.1%}<br>" +
        "From %{customdata.company}: $%{customdata.co_pay:,.0f}<extra></extra>",
    });

    return [
      mkTrace(med, "High capture (50–80%)", "#F0883E"),
      mkTrace(high, "Captured (≥ 80%)", "#F85149"),
    ];
  }

  const captureLayout = {
    margin: { t: 8, r: 80, b: 48, l: 80 },
    xaxis: {
      title: {
        text: "Total Payment (USD)",
        font: { color: "#7D8590", size: 10 },
      },
      type: "log",
      tickprefix: "$",
      tickfont: { size: 10, color: "#7D8590" },
      gridcolor: "#30363D",
    },
    yaxis: {
      title: { text: "Capture Ratio", font: { color: "#7D8590", size: 10 } },
      tickformat: ".0%",
      tickfont: { size: 10, color: "#7D8590" },
      gridcolor: "#30363D",
    },
    paper_bgcolor: "transparent",
    plot_bgcolor: "transparent",
  };

  // ── Quadrant summary counts ───────────────────────────────────
  let highCount = $state("-");
  let watchCount = $state("-");
  let commCount = $state("-");
  let concGini = $state("-");

  $effect(() => {
    // commCount and concGini still come from their own promises
    communityPromise
      .then((d) => {
        commCount = d.rows?.length ?? "-";
      })
      .catch(() => {});
    concPromise
      .then((d) => {
        const top = (d.rows ?? []).sort(
          (a, b) => (b.gini ?? 0) - (a.gini ?? 0),
        )[0];
        concGini = top ? top.gini?.toFixed(3) : "-";
      })
      .catch(() => {});
  });
</script>

<!-- ── Risk header ────────────────────────────────────────────────── -->
<div style="margin-bottom:16px">
  <h1
    style="font-size:20px;font-weight:800;color:var(--color-heading);margin:0 0 4px;letter-spacing:-0.5px;font-family:var(--font-display)"
  >
    Risk & Concentration Analysis
  </h1>
  <p
    style="font-size:12px;color:var(--color-muted);margin:0;font-family:var(--font-sans)"
  >
    Anomaly detection · Market concentration · Community structure · {$selectedYear}
  </p>
</div>

<!-- ── Quadrant summary cards ────────────────────────────────────── -->
<div class="quadrant-grid">
  <button
    class="quadrant-card risk-high"
    onclick={() => toggleSection("anomalies")}
  >
    <div style="display:flex;align-items:center;gap:8px;margin-bottom:8px">
      <span class="risk-dot risk-dot-high"></span>
      <span
        style="font-size:10px;font-weight:700;text-transform:uppercase;letter-spacing:.8px;color:var(--color-danger)"
        >High Risk</span
      >
    </div>
    <div class="quadrant-count" style="color:var(--color-danger)">
      {highCount}
    </div>
    <div class="quadrant-label">Anomalous Entities</div>
    <div class="quadrant-desc">
      z-score &gt; 2 AND composite &gt; 0.5 - double-flagged for investigation
    </div>
  </button>

  <button
    class="quadrant-card risk-med"
    onclick={() => toggleSection("anomalies")}
  >
    <div style="display:flex;align-items:center;gap:8px;margin-bottom:8px">
      <span class="risk-dot risk-dot-med"></span>
      <span
        style="font-size:10px;font-weight:700;text-transform:uppercase;letter-spacing:.8px;color:var(--color-warning)"
        >Watchlist</span
      >
    </div>
    <div class="quadrant-count" style="color:var(--color-warning)">
      {watchCount}
    </div>
    <div class="quadrant-label">Single-Flag Entities</div>
    <div class="quadrant-desc">
      Elevated z-score OR composite - merit monitoring
    </div>
  </button>

  <button
    class="quadrant-card risk-info"
    onclick={() => toggleSection("concentration")}
  >
    <div style="display:flex;align-items:center;gap:8px;margin-bottom:8px">
      <span class="risk-dot risk-dot-info"></span>
      <span
        style="font-size:10px;font-weight:700;text-transform:uppercase;letter-spacing:.8px;color:var(--color-info)"
        >Concentration</span
      >
    </div>
    <div class="quadrant-count" style="color:var(--color-info)">{concGini}</div>
    <div class="quadrant-label">Top Gini Coefficient</div>
    <div class="quadrant-desc">
      Payment inequality across specialties - 1.0 = perfect monopoly
    </div>
  </button>

  <button
    class="quadrant-card risk-ok"
    onclick={() => toggleSection("communities")}
  >
    <div style="display:flex;align-items:center;gap:8px;margin-bottom:8px">
      <span class="risk-dot risk-dot-ok"></span>
      <span
        style="font-size:10px;font-weight:700;text-transform:uppercase;letter-spacing:.8px;color:var(--color-success)"
        >Communities</span
      >
    </div>
    <div class="quadrant-count" style="color:var(--color-success)">
      {commCount}
    </div>
    <div class="quadrant-label">Leiden Clusters Found</div>
    <div class="quadrant-desc">
      Dense payment sub-networks detected via community detection
    </div>
  </button>
</div>

<!-- ════════════════════════════════════════════════════════════════ -->
<!-- ANOMALY ACCORDION                                               -->
<!-- ════════════════════════════════════════════════════════════════ -->
<div class="card-flat" style="margin-bottom:12px">
  <button class="accordion-header" onclick={() => toggleSection("anomalies")}>
    <div style="display:flex;align-items:center;gap:10px">
      <span class="risk-dot risk-dot-high"></span>
      <Zap size={14} color="var(--color-danger)" />
      <span
        style="font-weight:700;color:var(--color-heading);font-family:var(--font-display)"
        >Anomaly Detection</span
      >
      <span class="badge badge-danger">{highCount} high risk</span>
    </div>
    {#if $riskSection === "anomalies"}<ChevronUp
        size={16}
        color="var(--color-muted)"
      />{:else}<ChevronDown size={16} color="var(--color-muted)" />{/if}
  </button>

  {#if $riskSection === "anomalies"}
    <div class="accordion-body">
      <div class="insight-block">
        The <strong>z-score</strong> measures how far a physician's payment
        pattern deviates from their specialty's mean. The
        <strong>composite score</strong> combines multiple signals: cash ratio, disputed
        payments, third-party payments, and payment diversity. Entities in the red
        quadrant (z &gt; 2, composite &gt; 0.5) are flagged by both metrics simultaneously.
      </div>

      {#if anomalyLoading}
        <div class="loading-center">
          <div class="spinner"></div>
          <span>Loading anomaly data…</span>
        </div>
      {:else if anomalyError}
        <div class="error-msg">{anomalyError}</div>
      {:else if anomalyData}
        {@const rows = anomalyData.rows ?? []}
        {@const highRows = rows
          .filter((r) => (r.z_score ?? 0) > 2 && (r.composite_score ?? 0) > 0.5)
          .slice(0, 5)}

        <div
          style="display:grid;grid-template-columns:1fr 1fr;gap:14px;margin-bottom:16px"
        >
          <div>
            <div class="section-label" style="margin-bottom:6px">
              2D Quadrant View - Click to open dossier
            </div>
            <PlotlyChart
              traces={buildAnomalyScatter(rows)}
              layout={anomalyLayout}
              height={280}
              onClick={(pt) => {
                if (pt.customdata) openNode(pt.customdata);
              }}
            />
          </div>
          <div>
            <div class="section-label" style="margin-bottom:6px">
              Score Distribution by Specialty
            </div>
            <PlotlyChart
              traces={buildViolins(rows)}
              layout={violinLayout}
              height={280}
            />
          </div>
        </div>

        {#if highRows.length}
          <div class="section-label" style="margin-bottom:8px">
            Top High-Risk Entities
          </div>
          <div class="card-flat">
            {#each highRows as r}
              <button class="entity-row" onclick={() => openNode(r.id)}>
                <span class="risk-dot risk-dot-high" style="flex-shrink:0"
                ></span>
                <div style="flex:1;min-width:0">
                  <div
                    style="font-size:12px;font-weight:600;color:var(--color-heading);overflow:hidden;text-overflow:ellipsis;white-space:nowrap"
                  >
                    {r.id}
                  </div>
                  <div style="font-size:10px;color:var(--color-muted)">
                    z-score={(r.zscore_global ?? 0).toFixed(2)} · composite={(
                      r.composite_anomaly_score ?? 0
                    ).toFixed(3)}
                  </div>
                </div>
                <span style="font-size:11px;color:var(--color-accent)"
                  >Open →</span
                >
              </button>
            {/each}
          </div>
        {/if}
      {/if}

      <!-- Capture bubble -->
      {#if !captureInitiated}
        <div class="load-gate">
          <p class="load-gate-desc">Capture analysis loads ~9MB of payment relationship data.</p>
          <button class="load-gate-btn" onclick={() => (captureInitiated = true)}>
            Load Capture Analysis
          </button>
        </div>
      {:else}
      {#await capturePromise}
        <div class="loading-center" style="margin-top:16px">
          <div class="spinner"></div>
        </div>
      {:then capData}
        <div style="margin-top:16px">
          <div class="section-label" style="margin-bottom:6px">
            Manufacturer Capture - Total Payment vs Capture Ratio (size =
            company contribution)
          </div>
          <div class="insight-block">
            <strong>Capture ratio</strong> measures the fraction of a physician's
            total payments that come from a single manufacturer. High capture (&gt;
            0.7) indicates a concentrated financial relationship - the physician is
            largely "captured" by one company.
          </div>
          <PlotlyChart
            traces={buildCapture(capData.rows ?? [])}
            layout={captureLayout}
            height={300}
            onClick={(pt) => {
              if (pt.customdata?.id) openNode(pt.customdata.id);
            }}
          />
        </div>
      {:catch}
        <!-- capture not available -->
      {/await}
      {/if}
    </div>
  {/if}
</div>

<!-- ════════════════════════════════════════════════════════════════ -->
<!-- CONCENTRATION ACCORDION                                         -->
<!-- ════════════════════════════════════════════════════════════════ -->
<div class="card-flat" style="margin-bottom:12px">
  <button
    class="accordion-header"
    onclick={() => toggleSection("concentration")}
  >
    <div style="display:flex;align-items:center;gap:10px">
      <span class="risk-dot risk-dot-info"></span>
      <Gauge size={14} color="var(--color-info)" />
      <span
        style="font-weight:700;color:var(--color-heading);font-family:var(--font-display)"
        >Market Concentration</span
      >
      <span class="badge badge-info">Gini · HHI · CR-5</span>
    </div>
    {#if $riskSection === "concentration"}<ChevronUp
        size={16}
        color="var(--color-muted)"
      />{:else}<ChevronDown size={16} color="var(--color-muted)" />{/if}
  </button>

  {#if $riskSection === "concentration"}
    <div class="accordion-body">
      <div class="insight-block">
        The <strong>Gini coefficient</strong> measures payment inequality within each
        group (0 = equal distribution, 1 = one entity gets all payments). High Gini
        in a specialty signals that a few physicians dominate the payments in that
        specialty - a possible target for compliance review.
      </div>

      {#await multiConcPromise}
        <div class="loading-center"><div class="spinner"></div></div>
      {:then allData}
        <div class="section-label" style="margin-bottom:6px">
          Gini Coefficient Heatmap - Top 20 Specialties × 2020–2024
        </div>
        <PlotlyChart
          traces={buildConcHeatmap(allData)}
          layout={heatLayout}
          height={460}
        />
      {:catch e}
        <div class="error-msg">{e.message}</div>
      {/await}
    </div>
  {/if}
</div>

<!-- ════════════════════════════════════════════════════════════════ -->
<!-- COMMUNITIES ACCORDION                                           -->
<!-- ════════════════════════════════════════════════════════════════ -->
<div class="card-flat" style="margin-bottom:12px">
  <button class="accordion-header" onclick={() => toggleSection("communities")}>
    <div style="display:flex;align-items:center;gap:10px">
      <span class="risk-dot risk-dot-ok"></span>
      <Users size={14} color="var(--color-success)" />
      <span
        style="font-weight:700;color:var(--color-heading);font-family:var(--font-display)"
        >Community Structure</span
      >
      <span class="badge badge-success">{commCount} communities</span>
    </div>
    {#if $riskSection === "communities"}<ChevronUp
        size={16}
        color="var(--color-muted)"
      />{:else}<ChevronDown size={16} color="var(--color-muted)" />{/if}
  </button>

  {#if $riskSection === "communities"}
    <div class="accordion-body">
      <div class="insight-block">
        Communities are dense sub-networks identified by the <strong
          >Leiden algorithm</strong
        > on the bipartite manufacturer-physician graph. Large communities (treemap
        tiles) with high cash share (red tint) represent concentrated payment ecosystems
        worthy of scrutiny.
      </div>

      {#await communityPromise}
        <div class="loading-center"><div class="spinner"></div></div>
      {:then data}
        <div style="display:grid;grid-template-columns:1fr 1fr;gap:14px">
          <div>
            <div class="section-label" style="margin-bottom:6px">
              Community Treemap - size=payments · colour=cash share
            </div>
            <PlotlyChart
              traces={buildCommTreemap(data.rows ?? [])}
              layout={commTreemapLayout}
              height={380}
            />
          </div>
          <div>
            <div class="section-label" style="margin-bottom:6px">
              Top 15 Communities by Total Payment
            </div>
            <div class="card-flat" style="overflow:auto;max-height:380px">
              <table class="data-table">
                <thead
                  ><tr>
                    <th>ID</th><th>Members</th><th>Total ($)</th><th>Cash %</th>
                  </tr></thead
                >
                <tbody>
                  {#each (data.rows ?? []).slice(0, 15) as r}
                    <tr>
                      <td
                        ><span class="badge badge-info">C{r.community_id}</span
                        ></td
                      >
                      <td>{r.size ?? r.n_nodes ?? "-"}</td>
                      <td>{fmtUSD(r.total_payment_usd ?? r.total_payments)}</td>
                      <td
                        style="color:{(r.cash_share ?? 0) > 0.5
                          ? 'var(--color-danger)'
                          : 'var(--color-text)'}"
                      >
                        {((r.cash_share ?? 0) * 100).toFixed(1)}%
                      </td>
                    </tr>
                  {/each}
                </tbody>
              </table>
            </div>
          </div>
        </div>

        <!-- UMAP / 3D community scatter -->
        <div style="margin-top:18px">
          <div class="section-label" style="margin-bottom:8px">
            Community Embedding Map - UMAP 2D / 3D
          </div>
          <div class="insight-block" style="margin-bottom:10px">
            Each point is a physician, manufacturer, or teaching hospital
            projected by their payment-network metrics using <strong
              >UMAP</strong
            >. Colour by community, entity type, cash-ratio risk, or payment
            volume. Clusters reveal payment sub-ecosystems.
          </div>
          <CommunityViz />
        </div>
      {:catch e}
        <div class="error-msg">{e.message}</div>
      {/await}
    </div>
  {/if}
</div>

<!-- ════════════════════════════════════════════════════════════════ -->
<!-- CENTRALITY ACCORDION                                            -->
<!-- ════════════════════════════════════════════════════════════════ -->
<div class="card-flat" style="margin-bottom:12px">
  <button class="accordion-header" onclick={() => toggleSection("centrality")}>
    <div style="display:flex;align-items:center;gap:10px">
      <span
        class="risk-dot"
        style="background:var(--color-accent);box-shadow:0 0 6px var(--color-accent)"
      ></span>
      <Gauge size={14} color="var(--color-accent)" />
      <span
        style="font-weight:700;color:var(--color-heading);font-family:var(--font-display)"
        >Network Centrality</span
      >
      <span
        class="badge"
        style="background:var(--color-accent-dim);color:var(--color-accent)"
        >PageRank · Betweenness · Authority</span
      >
    </div>
    {#if $riskSection === "centrality"}<ChevronUp
        size={16}
        color="var(--color-muted)"
      />{:else}<ChevronDown size={16} color="var(--color-muted)" />{/if}
  </button>

  {#if $riskSection === "centrality"}
    <div class="accordion-body">
      <div class="insight-block">
        <strong>PageRank</strong> reflects how many important entities pay a
        physician (quality-weighted connections).
        <strong>Betweenness centrality</strong> identifies bridge physicians - those
        sitting between manufacturer clusters - who have unusual influence over information
        and payment flows.
      </div>

      {#await centralityPromise}
        <div class="loading-center"><div class="spinner"></div></div>
      {:then data}
        {@const rows = data.rows ?? []}
        <div style="display:grid;grid-template-columns:1fr 1fr;gap:14px">
          <div>
            <div class="section-label" style="margin-bottom:6px">
              PageRank × In-Strength - Click to open dossier
            </div>
            <PlotlyChart
              traces={[
                {
                  type: "scatter",
                  mode: "markers",
                  x: rows.map((r) => r.pagerank ?? 0),
                  y: rows.map((r) => r.in_strength ?? 0),
                  customdata: rows.map((r) => r.id),
                  text: rows.map((r) => r.name ?? r.id ?? ""),
                  marker: {
                    color: rows.map((r) =>
                      r.node_type === "Manufacturer" ? "#F0883E" : "#2F81F7",
                    ),
                    size: 7,
                    opacity: 0.75,
                  },
                  hovertemplate:
                    "<b>%{text}</b><br>PageRank: %{x:.5f}<br>Received: $%{y:,.0f}<extra></extra>",
                },
              ]}
              layout={{
                margin: { t: 8, r: 20, b: 48, l: 80 },
                xaxis: {
                  title: {
                    text: "PageRank",
                    font: { color: "#7D8590", size: 10 },
                  },
                  tickfont: { size: 10, color: "#7D8590" },
                  gridcolor: "#30363D",
                },
                yaxis: {
                  title: {
                    text: "Total Received ($)",
                    font: { color: "#7D8590", size: 10 },
                  },
                  tickprefix: "$",
                  tickfont: { size: 10, color: "#7D8590" },
                  gridcolor: "#30363D",
                },
                paper_bgcolor: "transparent",
                plot_bgcolor: "transparent",
              }}
              height={300}
              onClick={(pt) => {
                if (pt.customdata) openNode(pt.customdata);
              }}
            />
          </div>
          <div>
            <div class="section-label" style="margin-bottom:6px">
              Top 15 by PageRank
            </div>
            <div class="card-flat" style="overflow:auto;max-height:300px">
              <table class="data-table">
                <thead
                  ><tr
                    ><th>Entity</th><th>Type</th><th>PageRank</th><th
                      >Received</th
                    ></tr
                  ></thead
                >
                <tbody>
                  {#each rows.slice(0, 15) as r}
                    <tr onclick={() => openNode(r.id)} style="cursor:pointer">
                      <td
                        class="truncate"
                        style="max-width:160px;font-weight:500"
                        >{r.name ?? r.id}</td
                      >
                      <td
                        ><span
                          class="badge badge-{(
                            r.node_type ?? ''
                          ).toLowerCase()}"
                          style="font-size:9px">{r.node_type}</span
                        ></td
                      >
                      <td style="font-family:var(--font-mono);font-size:11px"
                        >{(r.pagerank ?? 0).toFixed(5)}</td
                      >
                      <td>{fmtUSD(r.in_strength)}</td>
                    </tr>
                  {/each}
                </tbody>
              </table>
            </div>
          </div>
        </div>
      {:catch e}
        <div class="error-msg">{e.message}</div>
      {/await}
    </div>
  {/if}
</div>

<style>
  .entity-row {
    display: flex;
    align-items: center;
    gap: 10px;
    width: 100%;
    padding: 10px 14px;
    border: none;
    background: transparent;
    cursor: pointer;
    border-bottom: 1px solid var(--color-border);
    transition: background 0.1s;
    font-family: var(--font-sans);
  }
  .entity-row:last-child {
    border-bottom: none;
  }
  .entity-row:hover {
    background: var(--color-hover);
  }
</style>
