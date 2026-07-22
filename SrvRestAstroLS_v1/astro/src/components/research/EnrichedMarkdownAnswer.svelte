<script lang="ts">
  import { deduplicateStructuredMarkdown, renderSafeMarkdown } from "./markdownRenderer.ts";
  let { markdown }: { markdown: string } = $props();
  const html = $derived(renderSafeMarkdown(deduplicateStructuredMarkdown(markdown)));
</script>
<div class="markdown enriched-markdown" data-testid="enriched-markdown">{@html html}</div>
