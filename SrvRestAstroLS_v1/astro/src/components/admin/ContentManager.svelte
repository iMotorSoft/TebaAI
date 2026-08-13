<script lang="ts">
  /**
   * Content Manager — premium editorial surface.
   *
   * Three levels: editorial heading + compact operational summary + recent
   * loads (light editorial table on desktop, cards on mobile). Detail view
   * shows summary, timeline, warnings, attempts and a collapsible technical
   * diagnostic. No generic admin shell: same identity as /research.
   */
  import { onMount, onDestroy } from "svelte";
  import { fetchMe, logout, type UserInfo } from "../auth/authClient.ts";
  import { listJobs, getJob, getDiagnostic, retryJob, cancelJob, isTerminal, isRetryable, type JobListItem, type JobResponse, type IngestionDiagnostic, listContentDocuments, getContentSummary, type DocumentListItem, type DocumentListResponse, type ContentSummary } from "./contentManagerClient.ts";
  import {
    STATUS_LABELS,
    STATUS_TONE,
    warningMessage,
    formatDate,
    formatDateTime,
    formatBytes,
    formatDuration,
    LANGUAGE_LABELS,
    contentDirection,
  } from "./contentManagerLabels.ts";
  import ContentManagerWizard from "./ContentManagerWizard.svelte";

  let user = $state<UserInfo | null>(null);
  let accessState = $state<"checking" | "ok" | "denied" | "error">("checking");
  let documents = $state<DocumentListItem[]>([]);
  let summary = $state<ContentSummary | null>(null);
  let loading = $state(false);
  let error = $state("");
  let showTestData = $state(false);

  // View routing
  let view = $state<"list" | "wizard" | "detail">("list");
  let detailJob = $state<JobResponse | null>(null);
  let detailDiagnostic = $state<IngestionDiagnostic | null>(null);
  let loadingDetail = $state(false);
  let detailError = $state("");
  let detailBusy = $state(false);
  let detailPollTimer: ReturnType<typeof setInterval> | null = null;

  // ── Detail polling: resume live status while the job is not terminal ──

  function stopDetailPolling() {
    if (detailPollTimer) {
      clearInterval(detailPollTimer);
      detailPollTimer = null;
    }
  }

  function startDetailPolling(jobId: string) {
    stopDetailPolling();
    detailPollTimer = setInterval(() => {
      void refreshDetailJob(jobId);
    }, 2000);
  }

  async function refreshDetailJob(jobId: string) {
    try {
      const job = await getJob(jobId);
      detailJob = job;
      if (isTerminal(job.status)) {
        stopDetailPolling();
        if (!detailDiagnostic) {
          detailDiagnostic = await getDiagnostic(jobId).catch(() => null);
        }
      }
    } catch {
      // Transient error; session loss handled by the client. Keep polling.
    }
  }

  // ── Auth gate ──────────────────────────────────────────────────────────

  onMount(async () => {
    const me = await fetchMe();
    if (me.status === "ok") {
      if (me.user.role !== "admin" && me.user.role !== "editor") {
        accessState = "denied";
        return;
      }
      user = me.user;
      accessState = "ok";
      await loadDocuments();
    } else if (me.status === "unauthorized") {
      window.location.assign("/login");
    } else {
      accessState = "error";
    }
  });

  async function signOut() {
    await logout();
    window.location.assign("/login");
  }

  async function loadDocuments() {
    loading = true;
    error = "";
    try {
      const data = await listContentDocuments({ includeTestData: showTestData });
      documents = data.documents || [];
      summary = data.summary;
    } catch (err) {
      error = err instanceof Error ? err.message : "No se pudieron cargar los documentos.";
    } finally {
      loading = false;
    }
  }

  function openWizard() {
    error = "";
    view = "wizard";
  }

  function exitWizard() {
    view = "list";
    void loadDocuments();
  }

  // ── Detail ─────────────────────────────────────────────────────────────

  async function openDetail(jobId: string) {
    if (!jobId) return;
    loadingDetail = true;
    detailError = "";
    detailJob = null;
    detailDiagnostic = null;
    view = "detail";
    try {
      const [job, diag] = await Promise.all([
        getJob(jobId),
        getDiagnostic(jobId).catch(() => null),
      ]);
      detailJob = job;
      detailDiagnostic = diag;
      if (!isTerminal(job.status)) {
        startDetailPolling(job.job_id);
      }
    } catch (err) {
      detailError = err instanceof Error ? err.message : "No se pudo abrir el detalle.";
    } finally {
      loadingDetail = false;
    }
  }

  function backToList() {
    view = "list";
    stopDetailPolling();
    detailJob = null;
    detailDiagnostic = null;
    void loadDocuments();
  }

  async function handleDetailRetry() {
    if (!detailJob) return;
    detailBusy = true;
    detailError = "";
    try {
      const job = await retryJob(detailJob.job_id);
      detailJob = job;
      detailDiagnostic = null;
      detailError = "";
      startDetailPolling(job.job_id);
    } catch (err) {
      detailError = err instanceof Error ? err.message : "No se pudo reintentar.";
    } finally {
      detailBusy = false;
    }
  }

  async function handleDetailCancel() {
    if (!detailJob) return;
    detailBusy = true;
    detailError = "";
    try {
      const job = await cancelJob(detailJob.job_id);
      detailJob = job;
    } catch (err) {
      detailError = err instanceof Error ? err.message : "No se pudo cancelar.";
    } finally {
      detailBusy = false;
    }
  }
  // ── Display helpers ──────────────────────────────────────────────────

  function jobDir(text: string | null | undefined): { direction: "ltr" | "rtl"; lang: string } {
    if (!text) return { direction: "ltr", lang: "es" };
    return contentDirection(text);
  }

  function jobTone(status: string): string {
    return STATUS_TONE[status] || "neutral";
  }

  // ── Timeline derivation ───────────────────────────────────────────────

  let timeline = $derived(
    detailJob
      ? [
          { label: "Carga registrada", at: detailJob.created_at },
          { label: "Procesamiento iniciado", at: detailJob.started_at },
          { label: "Procesamiento finalizado", at: detailJob.finished_at },
        ].filter((entry) => entry.at)
      : [],
  );

  // ── Summary from backend ────────────────────────────────────────────────

  let totalDocuments = $derived(summary?.total_documents ?? 0);
  let readyCount = $derived(summary?.ready ?? 0);
  let candidateCount = $derived(summary?.test_candidate ?? 0);
  let processingCount = $derived(summary?.processing ?? 0);
  let warningsCount = $derived(summary?.with_warnings ?? 0);
  let failedCount = $derived(summary?.failed ?? 0);

  function operationalTone(state: string): string {
    if (state === "processing") return "active";
    if (state === "failed") return "danger";
    if (state === "needs_review") return "review";
    if (state === "cancelled") return "muted";
    return "neutral";
  }

  function operationalLabel(doc: DocumentListItem): string {
    if (doc.operational_state === "processing") return "En procesamiento";
    if (doc.operational_state === "failed") return "Fallido";
    if (doc.operational_state === "cancelled") return "Cancelado";
    if (doc.is_test_data) return "Prueba";
    if (doc.has_warnings) return "Con observaciones";
    if (doc.document_status === "test_candidate") return "Candidato para revisión";
    if (doc.document_status === "ready") return "Listo";
    return doc.operational_state === "idle" ? "Listo" : (doc.latest_job_status || "—");
  }
</script>

{#if accessState === "checking"}
  <div class="cm-main" role="status">
    <p class="cm-loading">Verificando acceso…</p>
  </div>
{:else if accessState === "denied"}
  <main class="cm-main">
    <div class="cm-message cm-message--error" role="alert">
      <span class="cm-msg-icon" aria-hidden="true">!</span>
      <div>No tenés permiso para acceder al Gestor de Contenidos.</div>
    </div>
    <p style="margin-top: 16px"><a class="cm-link" href="/research">Volver al espacio de investigación</a></p>
  </main>
{:else if accessState === "error"}
  <main class="cm-main">
    <div class="cm-message cm-message--error" role="alert">
      <span class="cm-msg-icon" aria-hidden="true">!</span>
      <div>
        No se pudo verificar la sesión.
        <button class="cm-link" style="display: inline-flex" on:click={() => window.location.reload()}>Reintentar</button>
      </div>
    </div>
  </main>
{:else}
  <div class="content-manager">
    <!-- Header: continuation of /research header -->
    <header class="cm-header">
      <a href="/" class="cm-brand" aria-label="Breslov Research, inicio">
        <span lang="he" dir="rtl" style="font-size: 1.05rem; line-height: 1">רבי נחמן</span>
        <small>REBE NAJMÁN · BRESLOV RESEARCH</small>
      </a>
      <div class="cm-header-context">
        <a href="/research">Investigación</a>
        {#if user}
          <span>{user.username || user.email}</span>
        {/if}
        <button class="cm-signout" on:click={signOut}>Cerrar sesión</button>
      </div>
    </header>

    <main class="cm-main" id="main-content">
      {#if view === "list"}
        <div class="cm-heading">
          <div class="cm-heading-row">
            <div>
              <p class="cm-kicker">Documentación</p>
              <h1>Gestor de Contenidos</h1>
              <p class="cm-sub">Carga, procesamiento y validación de fuentes documentales</p>
            </div>
            <button class="cm-action" on:click={openWizard}>＋ Nueva carga</button>
          </div>
        </div>

        {#if error}
          <div class="cm-message cm-message--error" role="alert">
            <span class="cm-msg-icon" aria-hidden="true">!</span>
            <div>{error}</div>
          </div>
        {/if}

        {#if loading}
          <p class="cm-loading">Cargando biblioteca…</p>
        {:else if documents.length === 0 && !showTestData}
          <div class="cm-empty">
            <div class="cm-empty-mark" aria-hidden="true">✦</div>
            <h2>Todavía no hay contenidos incorporados</h2>
            <p>Las nuevas fuentes documentales aparecerán aquí junto con su estado de procesamiento.</p>
            <button class="cm-action" on:click={openWizard}>Cargar primer documento</button>
          </div>
        {:else}
          <!-- Summary indicators -->
          <div class="cm-summary" aria-label="Indicadores de la biblioteca">
            <div class="cm-summary-item">
              <strong>{totalDocuments}</strong>
              <span>Documentos</span>
            </div>
            <div class="cm-summary-item" data-tone="review">
              <strong>{readyCount}</strong>
              <span>Listos</span>
            </div>
            <div class="cm-summary-item" data-tone="review">
              <strong>{candidateCount}</strong>
              <span>Candidatos para revisión</span>
            </div>
            <div class="cm-summary-item" data-tone="active">
              <strong>{processingCount}</strong>
              <span>En procesamiento</span>
            </div>
            <div class="cm-summary-item" data-tone="warning">
              <strong>{warningsCount}</strong>
              <span>Con observaciones</span>
            </div>
            <div class="cm-summary-item" data-tone="danger">
              <strong>{failedCount}</strong>
              <span>Fallidos</span>
            </div>
          </div>

          <!-- Test data toggle -->
          <div class="cm-filters-bar">
            <label class="cm-toggle">
              <input type="checkbox" bind:checked={showTestData} on:change={() => loadDocuments()} />
              <span>Mostrar datos de prueba</span>
            </label>
          </div>

          <!-- Document library · desktop table -->
          <h2 class="cm-section-title">Biblioteca</h2>
          <div class="cm-table-wrap">
            <table class="cm-table">
              <thead>
                <tr>
                  <th scope="col">Título</th>
                  <th scope="col">Familia</th>
                  <th scope="col">Idioma</th>
                  <th scope="col">Páginas</th>
                  <th scope="col">Estado</th>
                  <th scope="col">Última actividad</th>
                  <th scope="col" style="text-align: right">Acciones</th>
                </tr>
              </thead>
              <tbody>
                {#each documents as doc (doc.document_id || doc.latest_job_id || '')}
                  <tr
                    class="cm-row-actionable"
                    tabindex="0"
                    on:click={() => doc.latest_job_id && openDetail(doc.latest_job_id)}
                    on:keydown={(e) => { if (e.key === "Enter" && doc.latest_job_id) openDetail(doc.latest_job_id); }}
                    aria-label={`Ver detalle de ${doc.title}`}
                  >
                    <td>
                      <span class="cm-doc-title" dir={jobDir(doc.title).direction} lang={jobDir(doc.title).lang}>
                        {#if doc.is_test_data}
                          <span class="cm-badge cm-badge--test">E2E</span>
                        {/if}
                        {doc.title}
                        {#if doc.filename}
                          <small dir={jobDir(doc.filename).direction} lang={jobDir(doc.filename).lang}>{doc.filename}</small>
                        {/if}
                      </span>
                    </td>
                    <td><span class="cm-meta">{doc.work_family || "—"}</span></td>
                    <td><span class="cm-meta">{LANGUAGE_LABELS[doc.language] || doc.language}</span></td>
                    <td><span class="cm-meta">{doc.page_count ?? "—"}</span></td>
                    <td>
                      <span class="cm-status" data-tone={operationalTone(doc.operational_state)}>
                        {operationalLabel(doc)}
                      </span>
                    </td>
                    <td><span class="cm-meta">{formatDate(doc.last_activity_at)}</span></td>
                    <td style="text-align: right">
                      {#if doc.latest_job_id}
                        <button
                          class="cm-link"
                          on:click={(e) => { e.stopPropagation(); openDetail(doc.latest_job_id!); }}
                        >Abrir</button>
                      {/if}
                    </td>
                  </tr>
                {/each}
              </tbody>
            </table>
          </div>

          <!-- Document library · mobile cards -->
          <h2 class="cm-section-title" style="display: none" data-mobile-title>Biblioteca</h2>
          <div class="cm-mobile-cards" aria-label="Biblioteca">
            {#each documents as doc (doc.document_id || doc.latest_job_id || '')}
              <article class="cm-mobile-card">
                <div class="cm-mc-top">
                  <h3 class="cm-mc-title" dir={jobDir(doc.title).direction} lang={jobDir(doc.title).lang}>
                    {#if doc.is_test_data}
                      <span class="cm-badge cm-badge--test">E2E</span>
                    {/if}
                    {doc.title}
                  </h3>
                  <span class="cm-status" data-tone={operationalTone(doc.operational_state)}>
                    {operationalLabel(doc)}
                  </span>
                </div>
                <div class="cm-mc-meta">
                  <span>{doc.work_family || "Sin familia"}</span>
                  <span>{LANGUAGE_LABELS[doc.language] || doc.language}</span>
                  {#if doc.page_count}
                    <span>{doc.page_count} págs.</span>
                  {/if}
                  <span>{formatDate(doc.last_activity_at)}</span>
                </div>
                <div class="cm-mc-actions">
                  {#if doc.latest_job_id}
                    <button class="cm-link" on:click={() => openDetail(doc.latest_job_id!)}>Abrir</button>
                  {/if}
                </div>
              </article>
            {/each}
          </div>
        {/if}

      {:else if view === "wizard"}
        <ContentManagerWizard onExit={exitWizard} onOpenDetail={(jobId) => openDetail(jobId)} />

      {:else if view === "detail"}
        <!-- ── Document detail ───────────────────────────────────────── -->
        <button class="cm-action cm-action--ghost" style="margin-bottom: 22px" on:click={backToList}>← Volver al gestor</button>

        {#if loadingDetail}
          <p class="cm-loading">Abriendo el detalle…</p>
        {:else if detailError}
          <div class="cm-message cm-message--error" role="alert">
            <span class="cm-msg-icon" aria-hidden="true">!</span>
            <div>{detailError}</div>
          </div>
        {:else if detailJob}
          {@const d = detailJob}
          {@const dir = jobDir(d.title)}
          <div class="cm-detail-head">
            <div>
              <p class="cm-kicker">Detalle del documento</p>
              <h1 dir={dir.direction} lang={dir.lang}>{d.title}</h1>
              <p class="cm-sub">
                {LANGUAGE_LABELS[d.language] || d.language} · intento {d.attempt_number}
                {#if d.created_at} · cargado {formatDate(d.created_at)}{/if}
              </p>
            </div>
            <span class="cm-status" data-tone={jobTone(d.status)}>{STATUS_LABELS[d.status] || d.status}</span>
          </div>

          <div class="cm-card cm-card--flat" style="margin-bottom: 18px">
            <div class="cm-card-body">
              <h2 style="margin: 0 0 4px; color: var(--navy-950); font: 500 1.2rem var(--serif)">Resumen</h2>
              <p style="margin: 0; color: var(--ink-700); line-height: 1.6; font-size: 0.9rem">
                {#if d.status === "completed"}
                  El documento fue procesado y quedó como candidato para revisión.
                {:else if d.status === "completed_with_warnings"}
                  El documento quedó disponible para revisión, pero se detectaron aspectos que conviene verificar.
                {:else if d.status === "failed"}
                  El procesamiento no pudo completarse.
                {:else if d.status === "cancelled"}
                  El procesamiento fue cancelado antes de iniciar las escrituras.
                {:else}
                  El documento está en procesamiento. Podés salir de esta pantalla y volver más tarde.
                {/if}
              </p>

              {#if d.warning_codes && d.warning_codes.length > 0}
                <div class="cm-message cm-message--warning" style="margin-top: 14px">
                  <span class="cm-msg-icon" aria-hidden="true">i</span>
                  <ul>
                    {#each d.warning_codes as code}
                      <li>{warningMessage(code)}</li>
                    {/each}
                  </ul>
                </div>
              {/if}

              {#if d.error_message && d.status === "failed"}
                <div class="cm-message cm-message--error" style="margin-top: 14px" role="alert">
                  <span class="cm-msg-icon" aria-hidden="true">!</span>
                  <div>
                    {d.error_message}
                    {#if d.error_code}
                      <span class="cm-msg-code">Código: {d.error_code}</span>
                    {/if}
                  </div>
                </div>
              {/if}

              {#if isRetryable(d.status)}
                <div class="cm-message cm-message--info" style="margin-top: 14px">
                  <span class="cm-msg-icon" aria-hidden="true">i</span>
                  <div>
                    Este documento puede reintentarse. El archivo original permanece disponible durante el tiempo de retención.
                  </div>
                </div>
              {/if}
            </div>
          </div>

          <div class="cm-card cm-card--flat" style="margin-bottom: 18px">
            <div class="cm-card-body">
              <h2 style="margin: 0 0 6px; color: var(--navy-950); font: 500 1.2rem var(--serif)">Línea de tiempo</h2>
              <ol class="cm-timeline">
                {#each timeline as entry (entry.label)}
                  <li>
                    <strong>{entry.label}</strong>
                    <span>{formatDateTime(entry.at)}</span>
                  </li>
                {/each}
              </ol>

              <h2 style="margin: 22px 0 6px; color: var(--navy-950); font: 500 1.2rem var(--serif)">Auditoría</h2>
              <dl class="cm-kv cm-sheet">
                <div class="cm-sheet-row">
                  <dt>Intentos</dt>
                  <dd>{d.attempt_number}</dd>
                </div>
                <div class="cm-sheet-row">
                  <dt>Recuperación</dt>
                  <dd>{d.recovery_status || "—"}</dd>
                </div>
                <div class="cm-sheet-row">
                  <dt>Limpieza</dt>
                  <dd>{d.cleanup_status || "—"}</dd>
                </div>
                <div class="cm-sheet-row">
                  <dt>Estado del documento</dt>
                  <dd>{detailDiagnostic?.document_status || "—"}</dd>
                </div>
              </dl>
            </div>
          </div>

          {#if isRetryable(d.status)}
            <div style="display: flex; gap: 10px; flex-wrap: wrap; margin-bottom: 18px">
              <button class="cm-action" on:click={handleDetailRetry} disabled={detailBusy}>
                {detailBusy ? "Reintentando…" : "Reintentar"}
              </button>
              {#if d.status === "uploaded" || d.status === "ready_to_ingest" || d.status === "queued"}
                <button class="cm-action cm-action--danger" on:click={handleDetailCancel} disabled={detailBusy}>
                  {detailBusy ? "Cancelando…" : "Cancelar"}
                </button>
              {/if}
            </div>
          {/if}

          {#if detailError}
            <div class="cm-message cm-message--error" role="alert">
              <span class="cm-msg-icon" aria-hidden="true">!</span>
              <div>{detailError}</div>
            </div>
          {/if}

          <!-- ── Collapsible technical diagnostic ─────────────────────── -->
          <details class="cm-details">
            <summary>Diagnóstico técnico</summary>
            <div class="cm-details-body">
              {#if detailDiagnostic}
                {@const diag = detailDiagnostic}
                <dl class="cm-sheet">
                  <div class="cm-sheet-row">
                    <dt>Páginas PDF</dt>
                    <dd>{diag.pdf_pages ?? "—"}</dd>
                  </div>
                  <div class="cm-sheet-row">
                    <dt>Páginas canónicas</dt>
                    <dd>{diag.canonical_pages ?? "—"}</dd>
                  </div>
                  <div class="cm-sheet-row">
                    <dt>Páginas con contenido</dt>
                    <dd>{diag.textual_pages ?? "—"}</dd>
                  </div>
                  <div class="cm-sheet-row">
                    <dt>Páginas vacías</dt>
                    <dd>{diag.empty_pages ?? "—"}</dd>
                  </div>
                  <div class="cm-sheet-row">
                    <dt>Encabezados</dt>
                    <dd>{diag.headings ?? "—"}</dd>
                  </div>
                  <div class="cm-sheet-row">
                    <dt>Notas</dt>
                    <dd>{diag.footnotes ?? "—"}</dd>
                  </div>
                  <div class="cm-sheet-row">
                    <dt>Referencias impresas</dt>
                    <dd>{diag.printed_references ?? "—"}</dd>
                  </div>
                  <div class="cm-sheet-row">
                    <dt>Fragmentos</dt>
                    <dd>{diag.chunks ?? "—"}</dd>
                  </div>
                  <div class="cm-sheet-row">
                    <dt>Registros de búsqueda</dt>
                    <dd>{diag.embeddings ?? "—"}</dd>
                  </div>
                  <div class="cm-sheet-row">
                    <dt>Vectores Milvus</dt>
                    <dd>{diag.milvus_entity_count ?? "—"}</dd>
                  </div>
                  <div class="cm-sheet-row">
                    <dt>PG ↔ Milvus</dt>
                    <dd>
                      {diag.pg_missing != null ? `faltantes ${diag.pg_missing} · ` : ""}
                      {diag.milvus_missing != null ? `milvus ${diag.milvus_missing} · ` : ""}
                      {diag.milvus_orphan != null ? `huérfanos ${diag.milvus_orphan} · ` : ""}
                      {diag.duplicates != null ? `duplicados ${diag.duplicates}` : ""}
                      {diag.duplicates == null && diag.pg_missing == null ? "—" : ""}
                    </dd>
                  </div>
                  <div class="cm-sheet-row">
                    <dt>Integridad de páginas</dt>
                    <dd>{diag.page_integrity || "—"}</dd>
                  </div>
                  <div class="cm-sheet-row">
                    <dt>Duración</dt>
                    <dd>{formatDuration(diag.duration_seconds)}</dd>
                  </div>
                  <div class="cm-sheet-row">
                    <dt>Limpieza</dt>
                    <dd>{diag.cleanup_result || "—"}</dd>
                  </div>
                  <div class="cm-sheet-row">
                    <dt>Job</dt>
                    <dd><code class="cm-code">{diag.job_id}</code></dd>
                  </div>
                  <div class="cm-sheet-row">
                    <dt>Intento</dt>
                    <dd>{diag.attempt_number}</dd>
                  </div>
                  <div class="cm-sheet-row">
                    <dt>Documento</dt>
                    <dd>
                      {#if diag.document_id}
                        <code class="cm-code">{diag.document_id}</code>
                      {:else}
                        —
                      {/if}
                    </dd>
                  </div>
                  <div class="cm-sheet-row">
                    <dt>Pipeline</dt>
                    <dd>{diag.pipeline_version || "—"}</dd>
                  </div>
                  <div class="cm-sheet-row">
                    <dt>Alcance</dt>
                    <dd>{diag.scope || "—"}</dd>
                  </div>
                  <div class="cm-sheet-row">
                    <dt>Colección</dt>
                    <dd>{diag.collection_code || "—"}</dd>
                  </div>
                </dl>

                {#if diag.warnings.length > 0}
                  <p style="margin: 16px 0 6px; color: var(--navy-900); font-weight: 700; font-size: 0.8rem">Advertencias</p>
                  <ul style="margin: 0; padding-left: 18px; font-size: 0.8rem; color: var(--ink-700)">
                    {#each diag.warnings as w}
                      <li>{w}</li>
                    {/each}
                  </ul>
                {/if}
                {#if diag.errors.length > 0}
                  <p style="margin: 16px 0 6px; color: #8b3028; font-weight: 700; font-size: 0.8rem">Errores</p>
                  <ul style="margin: 0; padding-left: 18px; font-size: 0.8rem; color: #8b3028">
                    {#each diag.errors as e}
                      <li>{e}</li>
                    {/each}
                  </ul>
                {/if}
              {:else}
                <p style="margin: 0; color: var(--ink-700); font-size: 0.84rem">
                  El diagnóstico todavía no está disponible.
                </p>
              {/if}
            </div>
          </details>
        {/if}
      {/if}
    </main>
  </div>
{/if}
