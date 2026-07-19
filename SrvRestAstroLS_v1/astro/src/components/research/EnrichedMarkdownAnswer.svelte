<script lang="ts">
  import { renderSafeMarkdown } from "./markdownRenderer.ts";
  let { markdown }: { markdown: string } = $props();
  const html = $derived(renderSafeMarkdown(markdown));
</script>
<div class="markdown enriched-markdown" data-testid="enriched-markdown">{@html html}</div>
