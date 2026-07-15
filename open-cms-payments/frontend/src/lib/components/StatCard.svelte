<script>
  import Sparkline from "./Sparkline.svelte";

  let {
    label = "",
    value = null,
    sub = "",
    color = "",
    sparkData = null, // number[] - 5-year trend values
    trend = null, // number: >0 good, <0 bad, null neutral
  } = $props();

  const sparkColor = $derived(
    color || (trend > 0 ? "#59a14f" : trend < 0 ? "#e15759" : "#7c6fcd"),
  );
</script>

<div class="card flex flex-col gap-1.5">
  <div class="flex items-start justify-between gap-2">
    <div
      class="text-[10px] font-semibold uppercase tracking-[0.8px] text-muted leading-tight"
    >
      {label}
    </div>
    {#if sparkData?.length}
      <Sparkline data={sparkData} color={sparkColor} width={72} height={28} />
    {/if}
  </div>
  <div
    class="text-[22px] font-bold text-heading leading-tight"
    style={color ? `color:${color}` : ""}
  >
    {value ?? "-"}
  </div>
  {#if sub}
    <div class="text-[11px] text-muted">{sub}</div>
  {/if}
</div>
