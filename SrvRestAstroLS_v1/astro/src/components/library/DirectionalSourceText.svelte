<script lang="ts">
  import { sourceTextDirection, sourceTextRuns } from "./sourceTextRuns.ts";
  let { text }: { text: string } = $props();
</script>
{#each sourceTextRuns(text) as cell}<bdi dir={sourceTextDirection(cell)}>{cell}</bdi>{/each}
<style>
  /* Equation cells must not split across mobile line boundaries. */
  bdi[dir="ltr"] { white-space: nowrap; }
</style>
