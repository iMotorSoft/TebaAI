<script lang="ts">
  import { BRAND, ROUTES } from "../global.js";
  import { getStoredAccessToken, getStoredUser, getMe } from "../auth/authClient.ts";
  import { askRelationQA, type RelationQARequest, type RelationQAResponse } from "./relationQaClient.ts";

  let token = $state<string | null>(getStoredAccessToken());
  let user = $state(getStoredUser());

  let question = $state("");
  let conceptA = $state("");
  let conceptB = $state("");
  let language = $state<"es" | "en" | "he" | "auto">("auto");
  let topK = $state(20);
  let useAi = $state(true);
  let loading = $state(false);
  let error = $state<string | null>(null);
  let response = $state<RelationQAResponse | null>(null);
  let showRawJson = $state(false);

  function evidenceLabel(key: string): string {
    const labels: Record<string, string> = {
      literal_phrase: "Frase literal",
      literal_relation: "Relación literal",
      explicit_reference: "Referencia explícita",
      biblical_citation: "Cita bíblica",
      rabbinic_source: "Fuente rabínica",
      breslov_text: "Texto Breslov",
      editorial_explanation: "Explicación editorial",
      footnote_reference: "Nota al pie",
      marginal_source: "Fuente marginal",
      internal_cross_reference: "Referencia cruzada",
      source_hebrew: "Fuente hebrea",
      cooccurrence_same_chunk: "Coocurrencia mismo fragmento",
      cooccurrence_same_page: "Coocurrencia misma página",
      cooccurrence_same_section: "Coocurrencia misma sección",
      paraphrase: "Paráfrasis",
      thematic_relation: "Relación temática",
      derash_interpretation: "Interpretación deráshica",
      remez_hint: "Indicio (remez)",
      ai_inference: "Inferencia IA",
      ambiguous: "Ambiguo",
      not_found: "No encontrado",
      excluded_false_positive: "Descartado",
    };
    return labels[key] || key;
  }

  function evidenceColor(key: string): string {
    if (key.includes("literal") || key.includes("citation")) return "badge-success";
    if (key.includes("reference") || key.includes("cross")) return "badge-info";
    if (key.includes("thematic") || key.includes("derash") || key.includes("remez")) return "badge-warning";
    if (key.includes("inference") || key.includes("ai")) return "badge-ghost";
    return "badge-outline";
  }

  async function handleSubmit(e: Event) {
    e.preventDefault();
    if (!question.trim() || !token) return;

    loading = true;
    error = null;
    response = null;

    try {
      const req: RelationQARequest = {
        question: question.trim(),
        concept_a: conceptA.trim() || null,
        concept_b: conceptB.trim() || null,
        language,
        top_k: topK,
        use_ai: useAi,
        include_test_candidates: false,
        knowledge_scope_code: "breslov_primary",
        evidence_depth: "standard",
        return_markdown: true,
        debug: false,
      };

      response = await askRelationQA(token, req);
    } catch (err: unknown) {
      if (err instanceof Error) {
        if (err.message.includes("401") || err.message.includes("403")) {
          token = null;
          user = null;
          error = "Sesión expirada. Inicia sesión nuevamente.";
        } else {
          error = err.message;
        }
      } else {
        error = "Error al consultar Relation QA";
      }
    } finally {
      loading = false;
    }
  }

  async function handleVerifySession() {
    const u = await getMe();
    if (u) {
      user = u;
      token = getStoredAccessToken();
    } else {
      token = null;
      user = null;
    }
  }
</script>

<div class="card bg-base-100 w-full max-w-5xl shadow-xl">
  <div class="card-body">
    <h2 class="card-title">Análisis relacional Breslov</h2>
    <p class="text-sm text-base-content/70">
      Consulta relaciones entre conceptos dentro del corpus Breslov.
      El sistema muestra fuentes, tipo de evidencia, advertencias y método de análisis.
    </p>

    {#if !token}
      <div class="alert alert-info mt-4">
        <span>Necesitás iniciar sesión para usar Relation QA.</span>
      </div>
      <div class="card-actions mt-4">
        <a href={ROUTES.login} class="btn btn-primary">Iniciar sesión</a>
      </div>
    {:else}
      <form class="mt-4 space-y-4" onsubmit={handleSubmit}>
        <label class="form-control">
          <span class="label-text">Pregunta</span>
          <textarea
            class="textarea textarea-bordered h-24"
            data-testid="relation-qa-question"
            placeholder="Ej: ¿Dónde aparece la relación entre sangre y habla?"
            bind:value={question}
            disabled={loading}
          ></textarea>
        </label>

        <div class="grid gap-3 md:grid-cols-2">
          <label class="form-control">
            <span class="label-text">Concepto A <span class="text-xs text-base-content/50">(opcional)</span></span>
            <input class="input input-bordered" bind:value={conceptA} disabled={loading} placeholder="sangre" />
          </label>
          <label class="form-control">
            <span class="label-text">Concepto B <span class="text-xs text-base-content/50">(opcional)</span></span>
            <input class="input input-bordered" bind:value={conceptB} disabled={loading} placeholder="habla" />
          </label>
        </div>

        <div class="flex flex-wrap gap-3 items-end">
          <label class="form-control w-32">
            <span class="label-text">Idioma</span>
            <select class="select select-bordered" bind:value={language} disabled={loading}>
              <option value="auto">auto</option>
              <option value="es">es</option>
              <option value="en">en</option>
              <option value="he">he</option>
            </select>
          </label>

          <label class="form-control w-24">
            <span class="label-text">Top K</span>
            <input type="number" class="input input-bordered" min="1" max="50" bind:value={topK} disabled={loading} />
          </label>

          <label class="label cursor-pointer gap-2">
            <span class="label-text">Usar IA</span>
            <input type="checkbox" class="toggle toggle-primary" bind:checked={useAi} disabled={loading} />
          </label>

          <button class="btn btn-primary" type="submit" data-testid="relation-qa-submit" disabled={loading || !question.trim()}>
            {#if loading}
              <span class="loading loading-spinner loading-sm"></span>
            {/if}
            Consultar
          </button>
        </div>
      </form>

      {#if error}
        <div class="alert alert-error mt-4" role="alert">
          <span>{error}</span>
        </div>
      {/if}

      {#if response}
        <div class="mt-6 space-y-6">

          <!-- Resumen de evidencia -->
          <div class="rounded-box border p-4">
            <h3 class="font-semibold text-lg">Resumen de evidencia</h3>
            {#if response.answer?.short_conclusion}
              <p class="mt-2 whitespace-pre-line">{response.answer.short_conclusion}</p>
            {/if}
            <div class="mt-3 flex flex-wrap gap-1.5">
              {#each Object.entries(response.evidence_summary) as [key, count]}
                {#if count > 0}
                  <span class="badge {evidenceColor(key)}">{evidenceLabel(key)}: {count}</span>
                {/if}
              {/each}
            </div>
            {#if response.answer}
              <div class="mt-3 flex flex-wrap gap-2 text-xs">
                <span class="badge badge-outline">{response.language}</span>
                <span class="badge badge-outline">{response.concepts?.concept_a?.label}</span>
                <span class="badge badge-outline">{response.concepts?.concept_b?.label}</span>
                <span class="badge {response.answer.literal_relation_found ? 'badge-success' : 'badge-warning'}">
                  {response.answer.literal_relation_found ? 'conexión literal' : 'conexión inferida'}
                </span>
                <span class="badge badge-outline">certeza: {response.answer.editorial_certainty}</span>
              </div>
            {/if}
          </div>

          <!-- Modo de síntesis -->
          {#if response.method}
            <div class="rounded-box border p-4" data-testid="relation-qa-synthesis-mode">
              <h3 class="font-semibold text-lg">Modo de síntesis</h3>
              <div class="mt-2 flex flex-wrap items-center gap-2">
                {#if response.method.synthesis_mode === "ai"}
                  <span class="badge badge-success" data-testid="relation-qa-synthesis-label">Síntesis IA</span>
                  <span class="badge badge-outline" data-testid="relation-qa-synthesis-status">
                    Estado: {response.method.ai_synthesis_status ?? "ok"}
                  </span>
                  {#if response.method.ai_synthesis_attempts != null}
                    <span class="badge badge-outline" data-testid="relation-qa-synthesis-attempts">
                      Intentos: {response.method.ai_synthesis_attempts}
                    </span>
                  {/if}
                  <p class="mt-2 w-full text-sm text-base-content/70">
                    La conclusión editorial fue generada por el modelo de síntesis usando las fuentes recuperadas.
                  </p>
                {:else if response.method.fallback_used || response.method.synthesis_mode === "deterministic_fallback"}
                  <span class="badge badge-warning" data-testid="relation-qa-synthesis-label">Fallback determinístico</span>
                  <span class="badge badge-outline" data-testid="relation-qa-synthesis-status">
                    Estado IA: {response.method.ai_synthesis_status ?? "failed"}
                  </span>
                  {#if response.method.ai_synthesis_attempts != null}
                    <span class="badge badge-outline" data-testid="relation-qa-synthesis-attempts">
                      Intentos: {response.method.ai_synthesis_attempts}
                    </span>
                  {/if}
                  {#if response.method.fallback_reason}
                    <span class="badge badge-ghost" data-testid="relation-qa-fallback-reason">
                      Motivo: {response.method.fallback_reason}
                    </span>
                  {/if}
                  <div class="alert alert-warning mt-2 p-3 text-sm">
                    La síntesis editorial automática no pudo completarse. Se muestra una síntesis determinística basada en las fuentes recuperadas. Revisar editorialmente antes de citar como conclusión.
                  </div>
                {:else}
                  <span class="badge badge-ghost" data-testid="relation-qa-synthesis-label">
                    Modo de síntesis no informado
                  </span>
                {/if}
              </div>
            </div>
          {/if}

          <!-- Conceptos detectados -->
          {#if response.concepts}
            <div class="rounded-box border p-4">
              <h3 class="font-semibold text-lg">Conceptos detectados</h3>
              <div class="mt-3 grid gap-3 md:grid-cols-2">
                <div>
                  <span class="font-medium text-sm">Concepto A: {response.concepts.concept_a.label}</span>
                  <div class="flex flex-wrap gap-1 mt-1">
                    {#each response.concepts.concept_a.variants as v}
                      <span class="badge badge-ghost text-xs">{v}</span>
                    {/each}
                  </div>
                </div>
                <div>
                  <span class="font-medium text-sm">Concepto B: {response.concepts.concept_b.label}</span>
                  <div class="flex flex-wrap gap-1 mt-1">
                    {#each response.concepts.concept_b.variants as v}
                      <span class="badge badge-ghost text-xs">{v}</span>
                    {/each}
                  </div>
                </div>
              </div>
            </div>
          {/if}

          <!-- Respuesta editorial IA -->
          {#if response.answer?.editorial_answer_markdown}
            <div class="rounded-box border p-4">
              <h3 class="font-semibold text-lg">Respuesta editorial</h3>
              <div class="prose prose-sm mt-2 max-w-none whitespace-pre-line">
                {response.answer.editorial_answer_markdown}
              </div>
            </div>
          {/if}

          <!-- Fuentes / Evidencia -->
          {#if response.sources && response.sources.length > 0}
            <div class="rounded-box border p-4">
              <h3 class="font-semibold text-lg">Fuentes <span class="text-sm font-normal text-base-content/50">({response.sources.length})</span></h3>
              <div class="mt-3 space-y-3">
                {#each response.sources as source}
                  <div class="rounded border p-3 text-sm">
                    <div class="flex flex-wrap items-center gap-2">
                      <span class="font-medium">{source.document_title}</span>
                      {#if source.page_number}
                        <span class="badge badge-outline text-xs">p. {source.page_number}</span>
                      {/if}
                      <span class="badge {evidenceColor(source.evidence_type)} text-xs">
                        {evidenceLabel(source.evidence_type)}
                      </span>
                    </div>
                    {#if source.chapter || source.section}
                      <div class="text-xs text-base-content/60 mt-1">
                        {source.chapter}{source.chapter && source.section ? ' · ' : ''}{source.section}
                      </div>
                    {/if}
                    {#if source.snippet}
                      <div class="mt-2 text-base-content/80 border-l-2 border-base-300 pl-3 italic">
                        {source.snippet}
                      </div>
                    {/if}
                    {#if source.chunk_id || source.score != null}
                      <div class="mt-1 text-xs text-base-content/40 flex flex-wrap gap-2">
                        {#if source.chunk_id}<span>chunk: {source.chunk_id.slice(0, 12)}...</span>{/if}
                        {#if source.score != null}<span>score: {source.score.toFixed(4)}</span>{/if}
                        <span>método: {source.retrieval_method}</span>
                      </div>
                    {/if}
                  </div>
                {/each}
              </div>
            </div>
          {/if}

          <!-- Advertencias editoriales -->
          {#if response.warnings && response.warnings.length > 0}
            <div class="alert alert-warning">
              <div class="font-semibold text-sm">Advertencias metodológicas</div>
              <ul class="list-disc pl-5 mt-1">
                {#each response.warnings as warning}
                  <li>{warning}</li>
                {/each}
              </ul>
            </div>
          {/if}

          <!-- Método de análisis -->
          {#if response.method}
            <details class="rounded-box border p-3 text-xs text-base-content/60">
              <summary class="cursor-pointer font-medium">Método de análisis</summary>
              <div class="mt-2 space-y-1">
                <p>Recuperación: {response.method.retrieval?.join(', ') || '—'}</p>
                <p>Modelo embeddings: {response.method.embedding_model || '—'}</p>
                <p>Modelo LLM: {response.method.llm_model || '—'}</p>
                <p>PG canónico: {response.method.used_pg_as_canonical ? 'sí' : 'no'}</p>
                <p>Milvus: {response.method.used_milvus ? 'sí' : 'no'}</p>
                <p>IA: {response.method.used_ai ? 'sí' : 'no'}</p>
              </div>
            </details>
          {/if}

          <!-- Debug: JSON crudo -->
          <details class="rounded-box border p-3 text-xs">
            <summary class="cursor-pointer text-base-content/50 hover:text-base-content" onclick={() => showRawJson = !showRawJson}>
              Ver JSON crudo de la respuesta
            </summary>
            {#if showRawJson}
              <pre class="mt-2 overflow-auto max-h-96 bg-base-200 p-3 rounded">{JSON.stringify(response, null, 2)}</pre>
            {/if}
          </details>

        </div>
      {/if}
    {/if}
  </div>
</div>
