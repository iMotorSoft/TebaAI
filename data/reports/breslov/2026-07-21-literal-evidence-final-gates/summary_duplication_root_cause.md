# Causa raíz de síntesis duplicada

`ResearchWorkspace.svelte` renderizaba la síntesis estructurada y, a continuación, `EnrichedMarkdownAnswer` volvía a renderizar `answer_markdown`, cuyo primer bloque era `## Síntesis investigativa`. No había doble montaje del componente.

La corrección deduplica las secciones Markdown ya representadas por UI estructurada (`Síntesis investigativa`, `Evidencia principal`, `Advertencias`) sólo cuando existe el bloque de evidencia estructurada. Las respuestas Markdown-only permanecen intactas. El panel de fuentes es la representación canónica del fragmento completo.
