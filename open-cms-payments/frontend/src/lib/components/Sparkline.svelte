<script>
  import * as d3 from "d3";

  let {
    data = [], // array of numbers [y0, y1, y2, ...]
    width = 80,
    height = 32,
    color = "var(--color-accent)",
  } = $props();

  let el = $state(null);

  $effect(() => {
    if (!el || !data?.length) return;
    const W = width,
      H = height;
    d3.select(el).selectAll("*").remove();

    const svg = d3
      .select(el)
      .attr("viewBox", [0, 0, W, H])
      .attr("width", W)
      .attr("height", H);

    const x = d3
      .scaleLinear()
      .domain([0, data.length - 1])
      .range([2, W - 2]);
    const yMin = d3.min(data) ?? 0;
    const yMax = d3.max(data) ?? 1;
    const y = d3
      .scaleLinear()
      .domain([yMin === yMax ? yMin - 1 : yMin, yMax])
      .range([H - 3, 3]);

    const lineGen = d3
      .line()
      .x((_, i) => x(i))
      .y((d) => y(d))
      .curve(d3.curveMonotoneX);
    const areaGen = d3
      .area()
      .x((_, i) => x(i))
      .y0(H - 2)
      .y1((d) => y(d))
      .curve(d3.curveMonotoneX);

    // Area fill
    svg
      .append("path")
      .datum(data)
      .attr("fill", color)
      .attr("fill-opacity", 0.12)
      .attr("d", areaGen);

    // Line
    svg
      .append("path")
      .datum(data)
      .attr("fill", "none")
      .attr("stroke", color)
      .attr("stroke-width", 1.5)
      .attr("d", lineGen);

    // Terminal dot
    const last = data[data.length - 1];
    svg
      .append("circle")
      .attr("cx", x(data.length - 1))
      .attr("cy", y(last))
      .attr("r", 2.5)
      .attr("fill", color);
  });
</script>

<svg bind:this={el} style="display:block;flex-shrink:0;"></svg>
