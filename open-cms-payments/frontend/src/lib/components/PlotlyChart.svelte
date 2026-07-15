<script>
  import Plotly from "plotly.js-dist-min";

  let {
    traces = [],
    layout = {},
    config = {},
    height = 320,
    onClick = null,
    onHover = null,
    onUnhover = null,
    style = "",
    class: cls = "",
  } = $props();

  let el = $state(null);

  // Shared dark-theme base - all pages inherit this
  const BASE = {
    paper_bgcolor: "transparent",
    plot_bgcolor: "transparent",
    font: {
      color: "#c8d0e0",
      size: 11,
      family: "Inter, system-ui, sans-serif",
    },
    margin: { t: 20, r: 16, b: 44, l: 60 },
    legend: {
      bgcolor: "rgba(0,0,0,0)",
      bordercolor: "#222538",
      borderwidth: 1,
      font: { color: "#c8d0e0", size: 11 },
    },
    xaxis: {
      gridcolor: "#1e2232",
      zerolinecolor: "#2a2d3e",
      tickcolor: "#3d4258",
      linecolor: "#222538",
      tickfont: { color: "#5e6578", size: 10 },
    },
    yaxis: {
      gridcolor: "#1e2232",
      zerolinecolor: "#2a2d3e",
      tickcolor: "#3d4258",
      linecolor: "#222538",
      tickfont: { color: "#5e6578", size: 10 },
    },
    colorway: [
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
    ],
    hoverlabel: {
      bgcolor: "#12141e",
      bordercolor: "#222538",
      font: {
        color: "#c8d0e0",
        size: 12,
        family: "Inter, system-ui, sans-serif",
      },
    },
    transition: { duration: 300, easing: "cubic-in-out" },
  };

  // Resize observer: keeps Plotly's click map in sync when flex/CSS resizes container
  $effect(() => {
    if (!el) return;
    const ro = new ResizeObserver(() => {
      try {
        Plotly.Plots.resize(el);
      } catch {}
    });
    ro.observe(el);
    return () => ro.disconnect();
  });

  $effect(() => {
    if (!el) return;

    // Register reactive dependencies
    const t = traces;
    const h = height;

    const mergedLayout = {
      ...BASE,
      height: h === 0 ? undefined : h,
      ...layout,
    };

    const plotConfig = {
      responsive: true,
      displayModeBar: false,
      scrollZoom: false,
      ...config,
    };

    try {
      Plotly.react(el, t, mergedLayout, plotConfig);
    } catch (err) {
      // Fallback to newPlot on first render
      try {
        Plotly.newPlot(el, t, mergedLayout, plotConfig);
      } catch {}
    }

    // Click handler - register once; removeAllListeners clears previous registrations
    if (onClick) {
      try {
        el.removeAllListeners("plotly_click");
      } catch {}
      el.on("plotly_click", (d) => {
        if (d.points?.[0]) onClick(d.points[0]);
      });
    }

    // Hover handler (for cross-chart linking)
    if (onHover) {
      try {
        el.removeAllListeners("plotly_hover");
      } catch {}
      el.on("plotly_hover", (d) => {
        if (d.points?.[0]) onHover(d.points[0]);
      });
    }

    if (onUnhover) {
      try {
        el.removeAllListeners("plotly_unhover");
      } catch {}
      el.on("plotly_unhover", () => onUnhover());
    }
  });
</script>

<div
  bind:this={el}
  class={cls}
  style="width:100%;{height > 0
    ? `min-height:${height}px;`
    : 'flex:1;min-height:0;'}{style}"
></div>
