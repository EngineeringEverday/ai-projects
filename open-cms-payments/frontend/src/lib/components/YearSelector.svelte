<script>
  import { selectedYear } from "../stores.js";

  const YEARS = [2020, 2021, 2022, 2023, 2024];

  const btnClass = (y) =>
    $selectedYear === y
      ? "bg-accent text-white border-accent"
      : "text-muted border-border bg-transparent hover:bg-hover hover:text-text";
</script>

<div class="flex gap-0.5 flex-wrap">
  {#each YEARS as y}
    <button
      class="px-2.5 py-1 rounded border text-[12px] font-medium cursor-pointer
             transition-colors duration-100 font-sans {btnClass(y)}"
      onclick={() => selectedYear.set(y)}
      data-tip="Filter all views to {y} Open Payments data">{y}</button
    >
  {/each}
</div>
