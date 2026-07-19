<script lang="ts">
  import type { Hit, ResearchResponse } from "./investigativeQaClient.ts";
  import { evidenceLabels, literalKindLabel, relevanceLabels, sourceLayerConfidenceLabels, sourceLayerLabels, warningLabel } from "./researchLabels.ts";
  import { isHebrewText, languageAttribute, normalizeDisplayText, textDirection } from "./textDirection.ts";

  let { response, selectedId, onselect, onclose }: { response: ResearchResponse | null; selectedId: string | null; onselect: (hit: Hit) => void; onclose?: () => void } = $props();
  const primary = $derived(response?.primary_evidence_ids.map((id) => response.hits.find((hit) => hit.hit_id === id)).filter((hit): hit is Hit => Boolean(hit)) ?? []);
  const contextual = $derived(response?.hits.filter((hit) => !response.primary_evidence_ids.includes(hit.hit_id) && !["single_term_literal", "unrelated_literal_noise"].includes(hit.relation_relevance)) ?? []);
  const additional = $derived(response?.hits.filter((hit) => ["single_term_literal", "unrelated_literal_noise"].includes(hit.relation_relevance)) ?? []);
  const active = $derived(response?.hits.find((hit) => hit.hit_id === selectedId) ?? primary[0] ?? contextual[0] ?? additional[0] ?? null);
  const activeText = $derived(normalizeDisplayText(active?.paragraph_text ?? active?.display_snippet ?? active?.snippet ?? ""));
  const activeIsHebrew = $derived(isHebrewText(activeText));
</script>

<section class="source-panel" aria-label="Fuentes del turno">
  <header><div><p class="kicker">EVIDENCIA VERIFICABLE</p><h2>Fuentes del turno</h2></div>{#if onclose}<button class="panel-close" aria-label="Cerrar fuentes" onclick={onclose}>×</button>{/if}</header>
  {#if response}
    <div class="source-stats" aria-label="Resumen de evidencia"><span>{response.evidence_counts.primary} principales</span><span>{response.evidence_counts.contextual} contextuales</span><span>{response.evidence_counts.additional_literal} coincidencias adicionales</span></div>
    {#if active}
      <article class="source-detail" tabindex="-1" aria-live="polite" data-evidence-id={active.hit_id}>
        <p class="source-category">{active.is_primary ? "EVIDENCIA PRINCIPAL" : additional.includes(active) ? "COINCIDENCIA ADICIONAL" : "EVIDENCIA CONTEXTUAL"}</p>
        <strong lang={languageAttribute(active.work_title)} dir={textDirection(active.work_title)}>{active.work_title}</strong>
        <div class="evidence-meta" dir="ltr">{active.physical_pdf_page === null ? "Página no disponible en el registro fuente" : `PDF p. ${active.physical_pdf_page}${active.printed_page !== null ? ` · Página impresa ${active.printed_page}` : ""}${active.section ? ` · ${active.section}` : ""}`}</div>
        {#if active.physical_file_name}<div class="evidence-meta" dir="ltr">Documento físico: {active.physical_file_name}</div>{/if}
        <h3>{activeIsHebrew ? "Texto original en hebreo" : "Fragmento recuperado"}</h3>
        <blockquote class:research-hebrew-text={activeIsHebrew} lang={active.language} dir={active.direction} data-display-normalization={active.display_normalization ?? undefined}>{activeText}</blockquote>
        <h3>Naturaleza del fragmento</h3>
        <p>{sourceLayerLabels[active.source_layer]} <small>(confianza {sourceLayerConfidenceLabels[active.source_layer_confidence]})</small></p>
        <dl>
          <div><dt>Relevancia</dt><dd>{relevanceLabels[active.relation_relevance]}</dd></div>
          <div><dt>Fuerza para esta consulta</dt><dd>{active.evidence_strength === "strong" ? "Fuerte" : active.evidence_strength === "medium" ? "Media" : active.evidence_strength === "weak" ? "Débil" : "Contextual"}</dd></div>
          <div><dt>Tipo de coincidencia</dt><dd>{literalKindLabel(active.literal_match_kind) || "Coincidencia contextual"}</dd></div>
          <div><dt>Tipo</dt><dd>{evidenceLabels[active.evidence_type] ?? "Evidencia investigativa"}</dd></div>
          <div><dt>Idioma</dt><dd>{active.language.toUpperCase()}</dd></div>
          <div><dt>ID de evidencia</dt><dd dir="ltr">{active.evidence_id ?? active.hit_id}</dd></div>
        </dl>
        {#if active.parallel_texts.length}
          <section class="parallel-texts" aria-label="Traducción o ampliación">
            <h3>Traducción / ampliación</h3>
            {#each active.parallel_texts as parallel}
              <p class="source-text-label">{sourceLayerLabels[parallel.source_layer]} · {parallel.language.toUpperCase()}</p>
              <blockquote lang={parallel.language} dir="ltr">{parallel.text}</blockquote>
              <p class="evidence-meta" dir="ltr">PDF p. {parallel.physical_pdf_page ?? "—"}{parallel.printed_page !== null ? ` · Página impresa ${parallel.printed_page}` : ""}</p>
            {/each}
          </section>
        {:else if active.language === "he"}
          <p class="warning">No hay un bloque español vinculado contractualmente como traducción exacta de este fragmento.</p>
        {/if}
        {#each active.warnings as warning}<p class="warning">{warningLabel(warning)}</p>{/each}
      </article>
    {/if}
    {#if primary.length}<section class="source-group"><h3>Evidencias principales</h3><div class="source-list" aria-label="Evidencias principales">{#each primary as hit, index}<button data-evidence-id={hit.hit_id} class:active={hit.hit_id === active?.hit_id} aria-pressed={hit.hit_id === active?.hit_id} onclick={() => onselect(hit)}><span>{index + 1}</span><strong>{hit.work_title}</strong><small>{hit.pdf_page === null ? "Página no disponible" : `PDF p. ${hit.pdf_page}`}</small></button>{/each}</div></section>{/if}
    {#if contextual.length}<details class="source-group"><summary>Relaciones contextuales ({contextual.length})</summary><div class="source-list">{#each contextual as hit}<button data-evidence-id={hit.hit_id} class:active={hit.hit_id === active?.hit_id} aria-pressed={hit.hit_id === active?.hit_id} onclick={() => onselect(hit)}><strong>{hit.work_title}</strong><small>{relevanceLabels[hit.relation_relevance]}</small></button>{/each}</div></details>{/if}
    {#if additional.length}<details class="source-group additional-matches"><summary>Otras coincidencias literales ({additional.length})</summary><p>Estos fragmentos contienen sólo parte de la consulta y no respaldan por sí mismos la relación.</p><div class="source-list">{#each additional as hit}<button data-evidence-id={hit.hit_id} class:active={hit.hit_id === active?.hit_id} aria-pressed={hit.hit_id === active?.hit_id} onclick={() => onselect(hit)}><strong>{hit.work_title}</strong><small>{hit.matched_concepts.join(" · ")}</small></button>{/each}</div></details>{/if}
  {:else}<p class="source-placeholder">Seleccioná un turno para revisar sus fuentes y páginas.</p>{/if}
</section>
