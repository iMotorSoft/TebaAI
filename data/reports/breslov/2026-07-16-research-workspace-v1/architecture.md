# Arquitectura

`ResearchWorkspace` mantiene estado local Svelte 5. `makeRequest` aplica allowlists y límite de 15 turnos. `normalizeResearchResponse` valida el shape. `EnrichedMarkdownAnswer` procesa narrativa con Marked y DOMPurify. `SourcePanel` consume exclusivamente hits estructurados. Ninguna página, evidencia o relación se deriva del Markdown.

La restauración de preferencias ocurre una vez en `onMount`; la persistencia comienza después. Esto evita el ciclo reactivo que bloqueaba la hidratación.
