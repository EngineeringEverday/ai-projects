<script>
  let { columns = [], rows = [], pageSize = 20, onRowClick = null, tooltips = {} } = $props();

  let page = $state(0);
  let sortCol = $state("");
  let sortAsc = $state(true);

  let sorted = $derived.by(() => {
    if (!sortCol) return rows;
    return [...rows].sort((a, b) => {
      const av = a[sortCol],
        bv = b[sortCol];
      if (av == null) return 1;
      if (bv == null) return -1;
      return sortAsc
        ? av < bv
          ? -1
          : av > bv
            ? 1
            : 0
        : av > bv
          ? -1
          : av < bv
            ? 1
            : 0;
    });
  });

  let totalPages = $derived(Math.max(1, Math.ceil(sorted.length / pageSize)));
  let pageRows = $derived(sorted.slice(page * pageSize, (page + 1) * pageSize));

  function toggleSort(col) {
    if (sortCol === col) sortAsc = !sortAsc;
    else {
      sortCol = col;
      sortAsc = false;
    }
    page = 0;
  }

  function fmt(val) {
    if (val == null) return "-";
    if (typeof val === "boolean") return val ? "Yes" : "No";
    if (typeof val === "number") {
      if (Math.abs(val) >= 1_000_000)
        return `$${(val / 1_000_000).toFixed(1)}M`;
      if (Math.abs(val) >= 1_000)
        return val.toLocaleString("en-US", { maximumFractionDigits: 0 });
      if (Math.abs(val) < 1 && val !== 0) return val.toFixed(4);
      return val.toFixed(2);
    }
    if (typeof val === "string" && val.includes("|"))
      return val.split("|").pop();
    return String(val);
  }
</script>

<div class="overflow-x-auto">
  <table class="w-full border-collapse text-[13px]">
    <thead>
      <tr>
        {#each columns as col}
          <th
            class="text-left px-3 py-2 text-muted font-medium border-b border-border
                   whitespace-nowrap cursor-pointer select-none hover:text-text"
            onclick={() => toggleSort(col)}
            title={tooltips[col] ?? undefined}
          >
            {col}{sortCol === col ? (sortAsc ? " ↑" : " ↓") : ""}
          </th>
        {/each}
      </tr>
    </thead>
    <tbody>
      {#each pageRows as row}
        <tr
          class="{onRowClick ? 'cursor-pointer' : ''} hover:[&>td]:bg-hover"
          onclick={() => onRowClick?.(row)}
        >
          {#each columns as col}
            <td
              class="px-3 py-2 border-b border-border whitespace-nowrap
                     max-w-65 overflow-hidden text-ellipsis"
              title={String(row[col] ?? "")}
            >
              {fmt(row[col])}
            </td>
          {/each}
        </tr>
      {/each}
      {#if pageRows.length === 0}
        <tr>
          <td colspan={columns.length} class="text-center text-muted px-3 py-6"
            >No data</td
          >
        </tr>
      {/if}
    </tbody>
  </table>

  <div class="flex items-center gap-2.5 pt-3 pb-1 text-[13px] text-muted">
    {#if totalPages > 1}
      <button class="btn btn-ghost" disabled={page === 0} onclick={() => page--}
        >← Prev</button
      >
      <span>{page + 1} / {totalPages} &nbsp;({sorted.length} rows)</span>
      <button
        class="btn btn-ghost"
        disabled={page >= totalPages - 1}
        onclick={() => page++}>Next →</button
      >
    {:else}
      <span>{rows.length} rows</span>
    {/if}
  </div>
</div>
