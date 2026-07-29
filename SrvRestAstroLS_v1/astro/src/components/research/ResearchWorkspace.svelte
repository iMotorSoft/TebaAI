<script lang="ts">
  import { onMount, tick } from "svelte";
  import { getMe, getStoredAccessToken, logout } from "../auth/authClient.ts";
  import EnrichedMarkdownAnswer from "./EnrichedMarkdownAnswer.svelte";
  import SourcePanel from "./SourcePanel.svelte";
  import {
    WORKS,
    analyzeConfirmedQuery,
    askInvestigativeQa,
    interpretInvestigativeQuery,
    makeAnalyzeRequest,
    makeInterpretRequest,
    makeRequest,
    normalizeInterpretationResponse,
    selectInitialEvidence,
    type Hit,
    type InterpretationResponse,
    type Language,
    type ResearchResponse,
  } from "./investigativeQaClient.ts";
  import {
    relevanceLabels,
    strengthLabel,
    warningLabel,
  } from "./researchLabels.ts";
  import {
    composerDirection,
    isHebrewText,
    languageAttribute,
    normalizeDisplayText,
    safeSnippet,
    textDirection,
  } from "./textDirection.ts";

  const labels: Record<string, string> = {
    kitzur: "Kitzur Likutey Moharán",
    lmi: "Likutey Moharán I — edición española",
    lmii: "Likutey Moharán II",
    lh: "Likutey Halajot",
    lm_xv: "Likutey Moharán XV",
    potencia_plegaria: "La Potencia de la Plegaria",
  };
  const PENDING_KEY = "tebaai_research_pending_interpretation_v1";

  type TurnState =
    | "interpreting"
    | "awaiting_interpretation_confirmation"
    | "editing_interpretation"
    | "analyzing"
    | "ok"
    | "partial"
    | "no_evidence"
    | "error";
  type Turn = {
    id: string;
    question: string;
    interpretation: InterpretationResponse | null;
    response: ResearchResponse | null;
    state: TurnState;
    editText: string;
  };

  let ready = $state(false);
  let inputText = $state("");
  let isSubmitting = $state(false);
  let requestError = $state<string | null>(null);
  let activeTurnId = $state("");
  let selectedHitId = $state<string | null>(null);
  let conversationId = $state("");
  let restoredState = $state(false);
  let filters = $state({
    works: [...WORKS] as string[],
    languages: ["es", "he", "en"] as Language[],
    thematic: true,
    maxHits: 10,
  });
  let turns = $state<Turn[]>([]);
  let mobilePanel = $state<"sources" | "filters" | "history" | null>(null);
  let composer = $state<HTMLTextAreaElement>();
  let panelTrigger: HTMLElement | null = null;
  let requestController: AbortController | null = null;

  const activeTurn = $derived(turns.find((turn) => turn.id === activeTurnId) ?? turns.at(-1));
  const direction = $derived(composerDirection(inputText));
  const blocksNewQuestion = $derived(
    !!activeTurn
      && ["interpreting", "awaiting_interpretation_confirmation", "editing_interpretation", "analyzing"].includes(activeTurn.state),
  );
  const hitText = (hit: Hit) =>
    normalizeDisplayText(hit.display_snippet || hit.paragraph_text || hit.snippet);
  const additionalHits = $derived(
    activeTurn?.response?.hits.filter((hit) =>
      ["single_term_literal", "unrelated_literal_noise"].includes(hit.relation_relevance)
    ) ?? [],
  );
  const groupedHits = $derived.by(() => {
    const groups = new Map<string, Hit[]>();
    for (const hit of activeTurn?.response?.hits ?? []) {
      groups.set(hit.work_code, [...(groups.get(hit.work_code) ?? []), hit]);
    }
    return [...groups.entries()];
  });

  onMount(() => {
    const rawFilters = sessionStorage.getItem("tebaai_research_filters");
    if (rawFilters) {
      try {
        filters = { ...filters, ...JSON.parse(rawFilters) };
      } catch {
        sessionStorage.removeItem("tebaai_research_filters");
      }
    }
    const rawPending = sessionStorage.getItem(PENDING_KEY);
    if (rawPending) {
      try {
        const saved = JSON.parse(rawPending) as { id: string; interpretation: unknown };
        const interpretation = normalizeInterpretationResponse(saved.interpretation);
        turns = [{
          id: saved.id,
          question: interpretation.original_query,
          interpretation,
          response: null,
          state: "awaiting_interpretation_confirmation",
          editText: interpretation.original_query,
        }];
        activeTurnId = saved.id;
        conversationId = interpretation.conversation_id;
      } catch {
        sessionStorage.removeItem(PENDING_KEY);
      }
    }
    conversationId ||= crypto.randomUUID();
    restoredState = true;
    void verify();
  });

  $effect(() => {
    if (!restoredState) return;
    sessionStorage.setItem("tebaai_research_filters", JSON.stringify(filters));
    const pending = turns.find((turn) =>
      turn.interpretation
      && ["awaiting_interpretation_confirmation", "editing_interpretation", "analyzing"].includes(turn.state)
    );
    if (pending?.interpretation) {
      sessionStorage.setItem(PENDING_KEY, JSON.stringify({
        id: pending.id,
        interpretation: pending.interpretation,
      }));
    } else {
      sessionStorage.removeItem(PENDING_KEY);
    }
  });

  function historyBefore(turnId?: string) {
    return turns
      .filter((turn) => turn.id !== turnId && turn.response)
      .map((turn) => ({ question: turn.question }));
  }

  async function submitInterpretation(
    question: string,
    turnId?: string,
    supersedes?: string,
  ) {
    const clean = question.trim();
    const token = getStoredAccessToken();
    if (!clean || !token || isSubmitting) return;
    const id = turnId ?? crypto.randomUUID();
    const next: Turn = {
      id,
      question: clean,
      interpretation: null,
      response: null,
      state: "interpreting",
      editText: clean,
    };
    turns = turnId
      ? turns.map((turn) => turn.id === id ? next : turn)
      : [...turns, next];
    activeTurnId = id;
    if (!turnId) inputText = "";
    isSubmitting = true;
    requestError = null;
    const controller = new AbortController();
    requestController = controller;
    try {
      const interpretation = await interpretInvestigativeQuery(
        token,
        makeInterpretRequest(
          clean,
          filters,
          historyBefore(id),
          conversationId,
          supersedes,
        ),
        controller.signal,
      );
      conversationId = interpretation.conversation_id;
      turns = turns.map((turn) => turn.id === id ? {
        ...turn,
        question: interpretation.original_query,
        interpretation,
        state: "awaiting_interpretation_confirmation",
        editText: interpretation.original_query,
      } : turn);
      await tick();
      document.querySelector<HTMLElement>('[data-testid="interpretation-analyze"]')?.focus();
    } catch (error) {
      if (error instanceof DOMException && error.name === "AbortError") return;
      requestError = error instanceof Error ? error.message : "No se pudo interpretar la consulta.";
      turns = turns.map((turn) => turn.id === id ? { ...turn, state: "error" } : turn);
    } finally {
      if (requestController === controller) {
        requestController = null;
        isSubmitting = false;
      }
    }
  }

  async function submit() {
    if (blocksNewQuestion) return;
    const clean = inputText.trim();
    const token = getStoredAccessToken();
    if (!clean || !token || isSubmitting) return;
    const id = crypto.randomUUID();
    turns = [...turns, {
      id,
      question: clean,
      interpretation: null,
      response: null,
      state: "analyzing",
      editText: clean,
    }];
    activeTurnId = id;
    inputText = "";
    isSubmitting = true;
    requestError = null;
    const controller = new AbortController();
    requestController = controller;
    try {
      const response = await askInvestigativeQa(
        token,
        makeRequest(clean, filters, historyBefore(id), conversationId, id),
        controller.signal,
      );
      selectedHitId = selectInitialEvidence(response);
      turns = turns.map((turn) => turn.id === id ? {
        ...turn,
        question: response.original_query || clean,
        response,
        state: response.status,
      } : turn);
      await tick();
      document.querySelector<HTMLElement>('[data-testid="research-result-heading"]')?.focus();
    } catch (error) {
      if (error instanceof DOMException && error.name === "AbortError") return;
      requestError = error instanceof Error ? error.message : "No se pudo completar la investigación.";
      turns = turns.map((turn) => turn.id === id ? { ...turn, state: "error" } : turn);
    } finally {
      if (requestController === controller) {
        requestController = null;
        isSubmitting = false;
      }
    }
  }

  async function analyze(turn: Turn) {
    const token = getStoredAccessToken();
    if (!token || !turn.interpretation || turn.state !== "awaiting_interpretation_confirmation" || isSubmitting) return;
    isSubmitting = true;
    requestError = null;
    turns = turns.map((item) => item.id === turn.id ? { ...item, state: "analyzing" } : item);
    const controller = new AbortController();
    requestController = controller;
    try {
      const response = await analyzeConfirmedQuery(
        token,
        makeAnalyzeRequest(turn.interpretation, filters, historyBefore(turn.id)),
        controller.signal,
      );
      selectedHitId = selectInitialEvidence(response);
      turns = turns.map((item) => item.id === turn.id ? {
        ...item,
        response,
        state: response.status,
      } : item);
      await tick();
      document.querySelector<HTMLElement>('[data-testid="research-result-heading"]')?.focus();
    } catch (error) {
      if (error instanceof DOMException && error.name === "AbortError") return;
      requestError = error instanceof Error ? error.message : "No se pudo completar el análisis.";
      turns = turns.map((item) => item.id === turn.id ? {
        ...item,
        state: "awaiting_interpretation_confirmation",
      } : item);
    } finally {
      if (requestController === controller) {
        requestController = null;
        isSubmitting = false;
      }
    }
  }

  async function modify(turn: Turn) {
    if (!turn.interpretation || isSubmitting) return;
    if (turn.state === "awaiting_interpretation_confirmation") {
      turns = turns.map((item) => item.id === turn.id ? {
        ...item,
        state: "editing_interpretation",
      } : item);
      await tick();
      document.querySelector<HTMLTextAreaElement>('[data-testid="interpretation-editor"]')?.focus();
      return;
    }
    if (turn.state === "editing_interpretation") {
      await submitInterpretation(
        turn.editText,
        turn.id,
        turn.interpretation.interpretation_id,
      );
    }
  }

  async function verify() {
    if (!(await getMe())) {
      location.assign("/login");
      return;
    }
    ready = true;
    await tick();
    if (!activeTurn) composer?.focus();
  }

  async function signOut() {
    requestController?.abort();
    await logout();
    location.assign("/login");
  }

  async function newConversation() {
    requestController?.abort();
    requestController = null;
    isSubmitting = false;
    turns = [];
    activeTurnId = "";
    selectedHitId = null;
    requestError = null;
    inputText = "";
    conversationId = crypto.randomUUID();
    mobilePanel = null;
    sessionStorage.removeItem(PENDING_KEY);
    await tick();
    composer?.focus();
  }

  function toggleWork(work: string) {
    const next = filters.works.includes(work)
      ? filters.works.filter((item) => item !== work)
      : [...filters.works, work];
    if (next.length) filters.works = next;
  }
  function toggleLanguage(language: Language) {
    const next = filters.languages.includes(language)
      ? filters.languages.filter((item) => item !== language)
      : [...filters.languages, language];
    if (next.length) filters.languages = next;
  }
  async function selectEvidence(evidenceId: string, event?: MouseEvent) {
    selectedHitId = evidenceId;
    if (typeof window !== "undefined" && window.innerWidth <= 1100) {
      panelTrigger = event?.currentTarget as HTMLElement ?? panelTrigger;
      mobilePanel = "sources";
      await tick();
      activePanel()?.querySelector<HTMLElement>(
        `[data-evidence-id="${CSS.escape(evidenceId)}"]`,
      )?.focus();
    }
  }
  async function openPanel(panel: typeof mobilePanel, event: MouseEvent) {
    panelTrigger = event.currentTarget as HTMLElement;
    mobilePanel = panel;
    await tick();
    activePanel()?.querySelector<HTMLElement>(
      'button, input, select, textarea, a[href], [tabindex]:not([tabindex="-1"])',
    )?.focus();
  }
  function closePanel() {
    mobilePanel = null;
    tick().then(() => panelTrigger?.focus());
  }
  function activePanel() {
    if (mobilePanel === "filters") return document.querySelector<HTMLElement>(".filter-sheet");
    if (mobilePanel === "sources") return document.querySelector<HTMLElement>(".sources.open");
    if (mobilePanel === "history") return document.querySelector<HTMLElement>(".history.open");
    return null;
  }
  function handleKey(event: KeyboardEvent) {
    if (event.key === "Escape" && mobilePanel) {
      event.preventDefault();
      closePanel();
      return;
    }
    if (event.key === "Tab" && mobilePanel) {
      const panel = activePanel();
      const focusable = panel
        ? Array.from(panel.querySelectorAll<HTMLElement>(
          'button:not(:disabled), input:not(:disabled), select:not(:disabled), textarea:not(:disabled), a[href], [tabindex]:not([tabindex="-1"])',
        )).filter((element) => element.getClientRects().length > 0)
        : [];
      if (focusable.length) {
        const first = focusable[0];
        const last = focusable[focusable.length - 1];
        if (event.shiftKey && document.activeElement === first) {
          event.preventDefault();
          last.focus();
        } else if (!event.shiftKey && document.activeElement === last) {
          event.preventDefault();
          first.focus();
        }
      }
      return;
    }
    if (
      event.key === "Enter"
      && !event.shiftKey
      && !event.isComposing
      && event.target === composer
    ) {
      event.preventDefault();
      void submit();
    }
  }
  function handleEditorKey(event: KeyboardEvent, turn: Turn) {
    if (event.key === "Enter" && !event.shiftKey && !event.isComposing) {
      event.preventDefault();
      void modify(turn);
    }
  }
  function resize(event: Event) {
    const element = event.currentTarget as HTMLTextAreaElement;
    element.style.height = "auto";
    element.style.height = `${Math.min(element.scrollHeight, 160)}px`;
  }
  function noEvidenceText(response: ResearchResponse) {
    if (!response.named_topic) return "No se encontró evidencia suficiente en el corpus consultado.";
    return `No encontré referencias verificables a «${response.named_topic.canonical_label}» en el corpus consultado.`;
  }
  const visibleWarnings = (response: ResearchResponse) =>
    response.warnings.filter((warning) =>
      !warning.startsWith("ai_interpretation_fallback:")
      && !warning.startsWith("suggestion_autoapplied:")
      && !warning.startsWith("evidence_snippet_sanitized:")
    );
  const interpretationWarningLabel = (warning: string) =>
    warning.startsWith("ai_interpretation_fallback:")
      ? "La interpretación IA no estuvo disponible; se aplicó el analizador determinístico."
      : warning;
</script>

<svelte:window onkeydown={handleKey} />

{#if ready}
  <main class="research" aria-label="Investigación Breslov" aria-busy={isSubmitting}>
    <header class="research-header">
      <a href="/" class="research-brand"><span lang="he" dir="rtl">רבי נחמן</span><small>REBE NAJMÁN · BRESLOV RESEARCH</small></a>
      <h1>Investigación</h1>
      <span class="service">● Disponible</span>
      <nav class="mobile-actions" aria-label="Paneles">
        <button onclick={(event) => openPanel("history", event)}>Conversación</button>
        <button onclick={(event) => openPanel("filters", event)}>Filtros</button>
        <button onclick={(event) => openPanel("sources", event)}>Fuentes</button>
      </nav>
      <button class="desktop-action" onclick={(event) => openPanel("filters", event)}>Filtros</button>
      <button class="desktop-action" onclick={newConversation}>Nueva investigación</button>
      <button class="desktop-action" onclick={signOut}>Cerrar sesión</button>
    </header>

    <aside class:open={mobilePanel === "history"} class="history" aria-label="Conversación de la sesión">
      <div class="aside-head"><h2>Conversación</h2><button class="panel-close" aria-label="Cerrar conversación" onclick={closePanel}>×</button></div>
      <button class="new-research" onclick={newConversation}>＋ Nueva investigación</button>
      {#if !turns.length}<p>Los turnos de esta sesión aparecerán aquí.</p>{/if}
      {#each turns as turn, index}
        <button class:active={turn.id === activeTurnId} onclick={() => {
          activeTurnId = turn.id;
          selectedHitId = turn.response ? selectInitialEvidence(turn.response) : null;
          closePanel();
        }}><small>Turno {index + 1}</small>{turn.question}</button>
      {/each}
      <a class="aside-link" href="/">Volver al inicio</a>
      <button class="aside-link" onclick={signOut}>Cerrar sesión</button>
    </aside>

    <section class="research-main" aria-live="polite">
      {#if !turns.length}<div class="empty research-empty"><h2>¿Qué desea investigar?</h2></div>{/if}
      {#if activeTurn}
        <article class="turn">
          <div class="user-turn">
            <p class="speaker">Investigador</p>
            <h2 lang={languageAttribute(activeTurn.question)} dir={textDirection(activeTurn.question)} class:research-hebrew-text={isHebrewText(activeTurn.question)}>{activeTurn.question}</h2>
          </div>

          {#if activeTurn.state === "interpreting"}
            <p class="loading" role="status">Interpretando la consulta…</p>
          {:else if activeTurn.state === "error"}
            <div class="error" role="alert"><p>{requestError}</p><button onclick={() => submitInterpretation(activeTurn.question, activeTurn.id)}>Reintentar</button></div>
          {/if}

          {#if activeTurn.interpretation}
            <section class="interpretation-card" data-testid="interpretation-card" aria-live="polite">
              <h3 tabindex="-1">Interpretación</h3>
              <p lang={languageAttribute(activeTurn.interpretation.display_interpretation)} dir="auto">{activeTurn.interpretation.display_interpretation}</p>
              {#if activeTurn.state === "editing_interpretation"}
                <label for={`interpretation-editor-${activeTurn.id}`}>Modificar interpretación</label>
                <textarea
                  id={`interpretation-editor-${activeTurn.id}`}
                  data-testid="interpretation-editor"
                  bind:value={activeTurn.editText}
                  dir={composerDirection(activeTurn.editText)}
                  lang={languageAttribute(activeTurn.editText)}
                  onkeydown={(event) => handleEditorKey(event, activeTurn)}
                  maxlength="1000"
                ></textarea>
              {/if}
              {#if ["awaiting_interpretation_confirmation", "editing_interpretation"].includes(activeTurn.state)}
                <div class="interpretation-actions" data-testid="interpretation-actions">
                  <button
                    data-testid="interpretation-analyze"
                    onclick={() => analyze(activeTurn)}
                    disabled={activeTurn.state !== "awaiting_interpretation_confirmation" || isSubmitting}
                  >Analizar</button>
                  <button
                    data-testid="interpretation-modify"
                    onclick={() => modify(activeTurn)}
                    disabled={isSubmitting || (activeTurn.state === "editing_interpretation" && !activeTurn.editText.trim())}
                  >Modificar</button>
                </div>
              {:else if activeTurn.state === "analyzing"}
                <p class="loading" role="status">Analizando…</p>
              {/if}
              {#if requestError && activeTurn.state === "awaiting_interpretation_confirmation"}
                <p class="interpretation-error" role="alert">{requestError}</p>
              {/if}
              {#if activeTurn.interpretation.warnings.length && !activeTurn.response}
                <details class="interpretation-diagnostics">
                  <summary>Detalles de la interpretación</summary>
                  {#each activeTurn.interpretation.warnings as warning}
                    <p>{interpretationWarningLabel(warning)}</p>
                  {/each}
                </details>
              {/if}
            </section>
          {/if}

          {#if activeTurn.response}
            <p class="speaker">Breslov Research</p>
            {#if activeTurn.response.research_status === "complete"}
              <p class="partial" data-research-status="complete">Resultado completo</p>
            {:else if activeTurn.response.research_status === "partial"}
              <p class="partial" data-research-status="partial">Resultado parcial: las fuentes no alcanzan para responder completamente.</p>
            {:else if activeTurn.response.research_status === "degraded"}
              <p class="partial" data-research-status="degraded">Resultado degradado: una capa no estuvo disponible y se utilizó una alternativa.</p>
            {/if}
            {#if activeTurn.state === "no_evidence"}
              <p class="no-evidence" role="status">{noEvidenceText(activeTurn.response)}</p>
            {:else}
              <section class="synthesis">
                <h3 data-testid="research-result-heading" tabindex="-1">Respuesta</h3>
                <p lang={languageAttribute(activeTurn.response.summary)} dir={textDirection(activeTurn.response.summary)} class:research-hebrew-text={isHebrewText(activeTurn.response.summary)}>{activeTurn.response.summary}</p>
                {#if activeTurn.response.claims.length}
                  <ol class="claim-list">
                    {#each activeTurn.response.claims as claim}
                      <li>
                        <p lang={languageAttribute(claim.text)} dir={textDirection(claim.text)} class:research-hebrew-text={isHebrewText(claim.text)}>{claim.text}</p>
                        <span>{strengthLabel(claim.strength)}</span>
                        <button aria-label={`Ver fuente de: ${claim.text}`} onclick={(event) => selectEvidence(claim.primary_evidence_id, event)}>Ver fuente</button>
                      </li>
                    {/each}
                  </ol>
                {/if}
              </section>
              <EnrichedMarkdownAnswer markdown={activeTurn.response.answer_markdown} />
            {/if}

            {#if activeTurn.response.hits.length}
              <section class="works-results">
                <h3>Resultados por obra</h3>
                {#each groupedHits as [work, hits]}
                  <details>
                    <summary><strong>{labels[work] ?? work}</strong><span>{hits.length} resultados</span></summary>
                    {#each hits.slice(0, 5) as hit}
                      <button onclick={(event) => selectEvidence(hit.hit_id, event)}>
                        <span class="evidence-meta" dir="ltr">{hit.pdf_page === null ? "Página no disponible" : `PDF p. ${hit.pdf_page}`} · {relevanceLabels[hit.relation_relevance]}</span>
                        <span class:research-hebrew-text={isHebrewText(hitText(hit))} lang={languageAttribute(hitText(hit))} dir={textDirection(hitText(hit))}>{safeSnippet(hitText(hit), 140)}</span>
                      </button>
                    {/each}
                  </details>
                {/each}
              </section>
            {/if}
            {#if additionalHits.length}
              <details class="additional-results"><summary>Otras coincidencias literales ({additionalHits.length})</summary><p>Contienen sólo parte de la consulta y no respaldan por sí mismas la relación preguntada.</p></details>
            {/if}
            {#if activeTurn.response.evidence_matrix.length}
              <details class="matrix">
                <summary>Matriz de evidencia</summary>
                <div class="matrix-table" role="table">
                  <div class="matrix-row matrix-head" role="row"><span>Obra</span><span>Principales</span><span>Contextuales</span><span>Adicionales</span><span>Total</span></div>
                  {#each activeTurn.response.evidence_matrix as row}
                    <div class="matrix-row" role="row"><span>{labels[row.work_code] ?? row.work_code}</span><span>{row.primary_hits ?? 0}</span><span>{row.contextual_hits ?? 0}</span><span>{row.additional_literal_hits ?? 0}</span><span>{row.hits}</span></div>
                  {/each}
                </div>
              </details>
            {/if}
            {#if visibleWarnings(activeTurn.response).length}
              <section class="research-warnings"><h3>Límites de la respuesta</h3>{#each visibleWarnings(activeTurn.response) as warning}<p>{warningLabel(warning)}</p>{/each}</section>
            {/if}
            <details class="matrix">
              <summary>Detalles de la consulta</summary>
              <p>Duración: {activeTurn.response.execution.duration_ms ?? "—"} ms</p>
              {#each activeTurn.interpretation?.warnings ?? [] as warning}
                <p>{interpretationWarningLabel(warning)}</p>
              {/each}
            </details>
          {/if}
        </article>
      {/if}
    </section>

    <aside class:open={mobilePanel === "sources"} class="sources" aria-label="Fuentes del turno">
      <SourcePanel
        response={activeTurn?.response ?? null}
        selectedId={selectedHitId}
        pendingAnalysis={Boolean(activeTurn && ["interpreting", "awaiting_interpretation_confirmation", "editing_interpretation", "analyzing"].includes(activeTurn.state))}
        onselect={(hit) => selectedHitId = hit.hit_id}
        onclose={closePanel}
      />
    </aside>

    <form class="composer" onsubmit={(event) => { event.preventDefault(); void submit(); }}>
      <label for="research-question">Nueva pregunta</label>
      <textarea
        bind:this={composer}
        id="research-question"
        data-testid="research-question"
        bind:value={inputText}
        dir={direction}
        lang={languageAttribute(inputText)}
        class:research-hebrew-text={direction === "rtl"}
        oninput={resize}
        maxlength="1000"
        placeholder="Escriba una pregunta de investigación…"
        disabled={isSubmitting || blocksNewQuestion}
      ></textarea>
      {#if inputText.length > 850}<small>{inputText.length}/1000</small>{/if}
      <button data-testid="research-submit" type="submit" disabled={isSubmitting || blocksNewQuestion || !inputText.trim()}>Enviar</button>
    </form>

    {#if mobilePanel === "filters"}
      <div class="panel-backdrop" role="presentation" onclick={closePanel}></div>
      <div class="filter-sheet" role="dialog" aria-modal="true" aria-label="Filtros de investigación">
        <header><h2>Filtros</h2><button aria-label="Cerrar filtros" onclick={closePanel}>×</button></header>
        <fieldset><legend>Obras</legend>{#each WORKS as work}<label><input type="checkbox" checked={filters.works.includes(work)} onchange={() => toggleWork(work)} /> {labels[work]}</label>{/each}</fieldset>
        <fieldset><legend>Idiomas</legend>{#each [["es", "Español"], ["he", "Hebreo"], ["en", "Inglés"]] as language}<label><input type="checkbox" checked={filters.languages.includes(language[0] as Language)} onchange={() => toggleLanguage(language[0] as Language)} /> {language[1]}</label>{/each}</fieldset>
        <label><input type="checkbox" checked={filters.thematic} onchange={(event) => filters.thematic = event.currentTarget.checked} /> Incluir paralelos temáticos</label>
        <label>Resultados <select bind:value={filters.maxHits}><option value={5}>5</option><option value={10}>10</option><option value={20}>20</option></select></label>
        <button class="apply-filters" onclick={closePanel}>Aplicar filtros</button>
      </div>
    {/if}
    {#if mobilePanel && mobilePanel !== "filters"}<button class="panel-backdrop" aria-label="Cerrar panel" onclick={closePanel}></button>{/if}
  </main>
{:else}
  <main class="research research--checking" aria-live="polite"><p>Verificando acceso…</p></main>
{/if}
