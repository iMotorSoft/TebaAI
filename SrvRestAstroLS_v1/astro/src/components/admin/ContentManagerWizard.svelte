<script lang="ts">
  /**
   * Content Manager — five-stage upload wizard.
   *
   * 1. Archivo  2. Información  3. Confirmación  4. Procesamiento  5. Resultado
   *
   * Real backend states only: no simulated progress, no invented percentages,
   * no success on HTTP 202 alone. The knowledge scope is a deployment-time
   * constant from the client module — never a selector here.
   */
  import { onMount, onDestroy, tick } from "svelte";
  import {
    uploadFile,
    createJob,
    getJob,
    retryJob,
    cancelJob,
    getDiagnostic,
    isTerminal,
    isCancellable,
    isRetryable,
    DEFAULT_MAX_UPLOAD_MB,
    type UploadResponse,
    type JobResponse,
    type IngestionDiagnostic,
  } from "./contentManagerClient.ts";
  import {
    EDITORIAL_STAGES,
    editorialStageKey,
    STATUS_LABELS,
    ERROR_MESSAGES,
    warningMessage,
    formatBytes,
    LANGUAGE_LABELS,
    DUPLICATE_LABELS,
    contentDirection,
  } from "./contentManagerLabels.ts";

  interface Props {
    onExit: () => void;
    onOpenDetail: (jobId: string) => void;
  }

  let { onExit, onOpenDetail }: Props = $props();

  type WizardStep = 1 | 2 | 3 | 4 | 5;

  // ── Shared wizard state ────────────────────────────────────────────────

  let step = $state<WizardStep>(1);
  let upload = $state<UploadResponse | null>(null);
  let title = $state("");
  let language = $state("auto");
  let workFamily = $state("");
  let adminNotes = $state("");
  let uploadError = $state<{ code: string; message: string } | null>(null);
  let uploading = $state(false);

  // ── Processing state ───────────────────────────────────────────────────

  let currentJob = $state<JobResponse | null>(null);
  let polling = $state(false);
  let pollTimer: ReturnType<typeof setInterval> | null = null;
  let busy = $state(false);
  let actionError = $state<string | null>(null);
  let diagnostic = $state<IngestionDiagnostic | null>(null);
  let loadingDiagnostic = $state(false);

  const STEP_LABELS: Record<WizardStep, string> = {
    1: "Archivo",
    2: "Información",
    3: "Confirmación",
    4: "Procesamiento",
    5: "Resultado",
  };

  // ── Upload helpers ─────────────────────────────────────────────────────

  function resetUpload() {
    upload = null;
    title = "";
    language = "auto";
    workFamily = "";
    adminNotes = "";
    uploadError = null;
  }

  async function sendFile(file: File) {
    uploading = true;
    uploadError = null;
    try {
      const result = await uploadFile(file);
      upload = result;
      // Stay on the file stage so the validation card (name, size, pages,
      // status) is visible before continuing — never jump silently ahead.
      step = 1;
    } catch (err) {
      uploadError = normalizeError(err);
      step = 1;
    } finally {
      uploading = false;
    }
  }

  function normalizeError(err: unknown): { code: string; message: string } {
    if (err && typeof err === "object" && "code" in err) {
      const code = String((err as { code: unknown }).code);
      const known = ERROR_MESSAGES[code as keyof typeof ERROR_MESSAGES];
      if (known) return { code, message: known };
      return { code: "UNKNOWN", message: ERROR_MESSAGES.UNKNOWN };
    }
    return { code: "UNKNOWN", message: ERROR_MESSAGES.UNKNOWN };
  }

  function handleFileInput(ev: Event) {
    const file = (ev.target as HTMLInputElement).files?.[0];
    if (file) void sendFile(file);
  }

  function handleDrop(ev: DragEvent) {
    ev.preventDefault();
    const file = ev.dataTransfer?.files?.[0];
    if (file) void sendFile(file);
  }

  function handleDropKeydown(ev: KeyboardEvent) {
    if (ev.key === "Enter" || ev.key === " ") {
      ev.preventDefault();
      (document.getElementById("cm-file-input") as HTMLInputElement | null)?.click();
    }
  }

  function pickAnother() {
    resetUpload();
    step = 1;
  }

  function maxUploadLabel(): string {
    if (upload?.limits?.max_upload_bytes) {
      return `${Math.round(upload.limits.max_upload_bytes / (1024 * 1024))} MB`;
    }
    return `${DEFAULT_MAX_UPLOAD_MB} MB`;
  }

  // ── Confirmation → processing ──────────────────────────────────────────

  async function startProcessing() {
    if (!upload) return;
    busy = true;
    actionError = null;
    try {
      const job = await createJob({
        upload_id: upload.upload_id,
        title: title.trim() || upload.filename.replace(/\.pdf$/i, ""),
        language,
        work_family: workFamily.trim() || null,
        administrative_notes: adminNotes.trim() || null,
      });
      currentJob = job;
      step = 4;
      startPolling(job.job_id);
    } catch (err) {
      actionError = normalizeError(err).message;
    } finally {
      busy = false;
    }
  }

  function goBackToInfo() {
    step = 2;
  }

  // ── Polling ────────────────────────────────────────────────────────────

  function startPolling(jobId: string) {
    stopPolling();
    polling = true;
    pollTimer = setInterval(() => {
      void refreshJob(jobId);
    }, 2000);
    void refreshJob(jobId);
  }

  function stopPolling() {
    if (pollTimer) {
      clearInterval(pollTimer);
      pollTimer = null;
    }
    polling = false;
  }

  async function refreshJob(jobId: string) {
    try {
      const job = await getJob(jobId);
      currentJob = job;
      if (isTerminal(job.status)) {
        stopPolling();
        step = 5;
        // Load the diagnostic so the result summary shows real counts.
        if (!diagnostic) {
          try {
            diagnostic = await getDiagnostic(jobId);
          } catch {
            diagnostic = null;
          }
        }
        await tick();
      }
    } catch {
      // Transient error: keep polling; session loss is handled by the client.
    }
  }

  // ── Terminal actions ───────────────────────────────────────────────────

  async function handleRetry() {
    if (!currentJob) return;
    busy = true;
    actionError = null;
    try {
      const job = await retryJob(currentJob.job_id);
      currentJob = job;
      step = 4;
      startPolling(job.job_id);
    } catch (err) {
      actionError = normalizeError(err).message;
    } finally {
      busy = false;
    }
  }

  async function handleCancel() {
    if (!currentJob) return;
    busy = true;
    actionError = null;
    try {
      const job = await cancelJob(currentJob.job_id);
      currentJob = job;
      stopPolling();
      onExit();
    } catch (err) {
      actionError = normalizeError(err).message;
    } finally {
      busy = false;
    }
  }

  async function openDiagnostic() {
    if (!currentJob) return;
    if (diagnostic) {
      onOpenDetail(currentJob.job_id);
      return;
    }
    loadingDiagnostic = true;
    try {
      diagnostic = await getDiagnostic(currentJob.job_id);
      onOpenDetail(currentJob.job_id);
    } catch {
      onOpenDetail(currentJob.job_id);
    } finally {
      loadingDiagnostic = false;
    }
  }

  function tryInResearch() {
    window.location.assign("/research");
  }

  // ── Derived presentation ───────────────────────────────────────────────

  let fileDir = $derived(upload ? contentDirection(upload.filename) : null);
  let titleDir = $derived(title ? contentDirection(title) : null);

  let stageRows = $derived(
    EDITORIAL_STAGES.map(({ key, label }) => {
      let state: "pending" | "active" | "done" | "failed" | "warning" = "pending";
      if (currentJob?.progress?.stage_states) {
        const raw = currentJob.progress.stage_states[key];
        if (raw === "done" || raw === "active" || raw === "failed" || raw === "warning") {
          state = raw;
        } else {
          state = "pending";
        }
      }
      // The backend also emits ready_to_ingest/queued/claimed; when the job is
      // in one of those, the first visible stage stays done and none is active.
      if (currentJob) {
        const stageKey = editorialStageKey(currentJob.status);
        if (stageKey === key && state === "pending" && !isTerminal(currentJob.status)) {
          state = "active";
        }
      }
      return { key, label, state };
    }),
  );

  let progressPercent = $derived(
    Math.max(
      0,
      Math.min(100, Math.round(currentJob?.progress?.progress_percent ?? 0)),
    ),
  );

  let statusLabel = $derived(currentJob ? STATUS_LABELS[currentJob.status] || currentJob.status : "");

  let resultWarnings = $derived((currentJob?.warning_codes ?? []).map((code) => warningMessage(code)));

  let canCancel = $derived(currentJob ? isCancellable(currentJob.status) : false);
  let canRetry = $derived(currentJob ? isRetryable(currentJob.status) : false);

  let jobFailed = $derived(currentJob?.status === "failed");

  function formatDuration(seconds: number | null | undefined): string {
    if (seconds === null || seconds === undefined) return "—";
    if (seconds < 60) return `${Math.round(seconds)} s`;
    const m = Math.floor(seconds / 60);
    return `${m} min ${Math.round(seconds % 60)} s`;
  }

  onMount(() => {
    // Keep the file input reachable by keyboard after re-renders.
    void tick();
  });

  onDestroy(() => {
    stopPolling();
  });
</script>

<div class="cm-wizard">
  <!-- Stepper -->
  <ol class="cm-stepper" aria-label="Progreso del flujo de carga">
    {#each [1, 2, 3, 4, 5] as s (s)}
      <li
        class="cm-step"
        data-state={s < step ? "done" : s === step ? "current" : "pending"}
        aria-current={s === step ? "step" : undefined}
      >
        <span class="cm-step-num" aria-hidden="true">{s < step ? "✓" : s}</span>
        <span class="cm-step-label">{STEP_LABELS[s as WizardStep]}</span>
      </li>
      {#if s < 5}
        <li class="cm-step-line" aria-hidden="true"></li>
      {/if}
    {/each}
  </ol>

  {#if step === 1}
    <!-- ── Etapa 1 · Archivo ─────────────────────────────────────────── -->
    <section aria-labelledby="cm-step-file-title">
      <h2 id="cm-step-file-title" class="visually-hidden">Selección del archivo</h2>

      {#if !upload && !uploading}
        <div
          class="cm-dropzone"
          role="button"
          tabindex="0"
          aria-label="Seleccioná una fuente documental. PDF de hasta {maxUploadLabel()}."
          on:click={() => (document.getElementById("cm-file-input") as HTMLInputElement | null)?.click()}
          on:keydown={handleDropKeydown}
          on:dragover={(e) => e.preventDefault()}
          on:drop={handleDrop}
        >
          <input
            id="cm-file-input"
            type="file"
            accept=".pdf,application/pdf"
            on:change={handleFileInput}
            tabindex="-1"
          />
          <div class="cm-drop-icon" aria-hidden="true">✦</div>
          <h3>Seleccioná una fuente documental</h3>
          <p>PDF de hasta {maxUploadLabel()}. El archivo será validado antes de iniciar su procesamiento.</p>
          <p class="cm-drop-hint">Arrastrá el archivo aquí, elegilo con el selector o usá el teclado.</p>
        </div>
      {:else if uploading}
        <div class="cm-card cm-card--flat" role="status" aria-live="polite">
          <div class="cm-card-body">
            <p class="cm-loading" style="padding: 26px 0">Validando archivo…</p>
          </div>
        </div>
      {:else if upload}
        <!-- File card -->
        <div class="cm-card cm-file-card" aria-live="polite">
          <h3 class="cm-file-name" dir={fileDir?.direction} lang={fileDir?.lang}>
            {upload.filename}
          </h3>
          <div class="cm-file-meta">
            <span class="cm-file-badge">{formatBytes(upload.size_bytes)}</span>
            <span class="cm-file-badge">{upload.page_count != null ? `${upload.page_count} páginas` : "páginas —"}</span>
            <span class="cm-file-badge">PDF</span>
            {#if upload.validation_status === "valid"}
              <span class="cm-file-badge cm-file-badge--success">Archivo válido</span>
            {/if}
          </div>
          <div class="cm-file-actions">
            {#if upload.duplicate_status !== "exact_duplicate"}
              <button class="cm-action" on:click={() => (step = 2)}>Continuar</button>
            {/if}
            <button class="cm-action cm-action--ghost" on:click={pickAnother}>Seleccionar otro archivo</button>
          </div>

          {#if upload.duplicate_status === "exact_duplicate"}
            <div class="cm-message cm-message--error" style="grid-column: 1 / -1" role="alert">
              <span class="cm-msg-icon" aria-hidden="true">!</span>
              <div>
                Este mismo archivo ya fue cargado.
                {#if upload.existing_document}
                  <p style="margin: 6px 0 0">Documento existente: <strong>{upload.existing_document.title}</strong></p>
                {/if}
                <p style="margin: 8px 0 0">
                  <button class="cm-link" style="display: inline-flex" on:click={onExit}>Volver al gestor</button>
                </p>
              </div>
            </div>
          {:else if upload.duplicate_status !== "new_document"}
            <div class="cm-message cm-message--warning" style="grid-column: 1 / -1">
              <span class="cm-msg-icon" aria-hidden="true">!</span>
              <div>
                <strong>{DUPLICATE_LABELS[upload.duplicate_status]}</strong> — el documento presenta características similares a una carga previa. Verificá antes de continuar.
              </div>
            </div>
          {/if}

          {#if upload.warnings.length > 0}
            <div class="cm-message cm-message--warning" style="grid-column: 1 / -1">
              <span class="cm-msg-icon" aria-hidden="true">i</span>
              <ul>
                {#each upload.warnings as w}
                  <li>{w}</li>
                {/each}
              </ul>
            </div>
          {/if}

          <details class="cm-details" style="grid-column: 1 / -1">
            <summary>Detalles técnicos</summary>
            <div class="cm-details-body">
              <p style="margin: 0 0 8px; font-size: 0.8rem; color: var(--ink-700)">
                SHA-256: <code class="cm-code">{upload.sha256.slice(0, 16)}…</code>
              </p>
            </div>
          </details>
        </div>
      {/if}

      {#if uploadError}
        <div class="cm-message cm-message--error" role="alert">
          <span class="cm-msg-icon" aria-hidden="true">!</span>
          <div>
            {uploadError.message}
            <span class="cm-msg-code">Código: {uploadError.code}</span>
          </div>
        </div>
      {/if}

      <div style="margin-top: 18px">
        <button class="cm-action cm-action--ghost" on:click={onExit}>← Volver al gestor</button>
      </div>
    </section>

  {:else if step === 2}
    <!-- ── Etapa 2 · Información ─────────────────────────────────────── -->
    <section aria-labelledby="cm-step-info-title">
      <div class="cm-card cm-card--flat">
        <div class="cm-card-head">
          <h2 id="cm-step-info-title">Información de la obra</h2>
          <p style="color: var(--ink-700); font-size: 0.86rem; margin: 6px 0 0">
            Solo los datos editoriales. El resto de la configuración se resuelve automáticamente.
          </p>
        </div>
        <div class="cm-card-body">
          <div class="cm-field">
            <label for="cm-title">Título de la obra</label>
            <input
              id="cm-title"
              type="text"
              bind:value={title}
              placeholder={upload?.filename.replace(/\.pdf$/i, "") || "Título"}
              dir={titleDir?.direction}
              lang={titleDir?.lang}
              maxlength="500"
            />
            <span class="cm-hint">Si lo dejás vacío, se usará el nombre del archivo.</span>
          </div>

          <div class="cm-field">
            <label for="cm-language">Idioma principal</label>
            <select id="cm-language" bind:value={language}>
              <option value="auto">Automático</option>
              <option value="es">Español</option>
              <option value="en">Inglés</option>
              <option value="he">Hebreo</option>
              <option value="mixed">Mixto</option>
              <option value="unknown">Desconocido</option>
            </select>
          </div>

          <div class="cm-field">
            <label for="cm-family">Familia documental <span class="cm-optional">(opcional)</span></label>
            <input
              id="cm-family"
              type="text"
              bind:value={workFamily}
              placeholder="Ej.: Likutey Halajot"
              maxlength="100"
            />
          </div>

          <div class="cm-field">
            <label for="cm-notes">Nota administrativa <span class="cm-optional">(opcional)</span></label>
            <textarea id="cm-notes" bind:value={adminNotes} maxlength="2000"></textarea>
            <span class="cm-hint">Solo para uso interno del equipo.</span>
          </div>

          <div style="display: flex; gap: 10px; flex-wrap: wrap; margin-top: 8px">
            <button class="cm-action" on:click={() => (step = 3)}>Continuar a confirmación</button>
            <button class="cm-action cm-action--ghost" on:click={pickAnother}>Volver al archivo</button>
          </div>
        </div>
      </div>
    </section>

  {:else if step === 3}
    <!-- ── Etapa 3 · Confirmación ────────────────────────────────────── -->
    <section aria-labelledby="cm-step-confirm-title">
      <div class="cm-card cm-card--flat">
        <div class="cm-card-head">
          <h2 id="cm-step-confirm-title">Confirmación</h2>
        </div>
        <div class="cm-card-body cm-sheet">
          <dl>
            <div class="cm-sheet-row">
              <dt>Archivo</dt>
              <dd dir={fileDir?.direction} lang={fileDir?.lang}>{upload?.filename}</dd>
            </div>
            <div class="cm-sheet-row">
              <dt>Título</dt>
              <dd dir={titleDir?.direction} lang={titleDir?.lang}>{title.trim() || upload?.filename.replace(/\.pdf$/i, "")}</dd>
            </div>
            <div class="cm-sheet-row">
              <dt>Idioma</dt>
              <dd>{LANGUAGE_LABELS[language] || language}</dd>
            </div>
            <div class="cm-sheet-row">
              <dt>Páginas</dt>
              <dd>{upload?.page_count ?? "—"}</dd>
            </div>
            <div class="cm-sheet-row">
              <dt>Tamaño</dt>
              <dd>{upload ? formatBytes(upload.size_bytes) : "—"}</dd>
            </div>
            <div class="cm-sheet-row">
              <dt>Familia</dt>
              <dd>{workFamily.trim() || "—"}</dd>
            </div>
            <div class="cm-sheet-row">
              <dt>Duplicados</dt>
              <dd>{upload ? DUPLICATE_LABELS[upload.duplicate_status] : "—"}</dd>
            </div>
            <div class="cm-sheet-row">
              <dt>Proceso propuesto</dt>
              <dd>Ingesta page-first con verificación de consistencia</dd>
            </div>
            <div class="cm-sheet-row">
              <dt>Estado final esperado</dt>
              <dd>Candidato para revisión</dd>
            </div>
          </dl>

          <div class="cm-message cm-message--info">
            <span class="cm-msg-icon" aria-hidden="true">i</span>
            <div>El documento será procesado y quedará como candidato para revisión.</div>
          </div>
          <div class="cm-message cm-message--warning">
            <span class="cm-msg-icon" aria-hidden="true">!</span>
            <div>Esta operación no publica ni aprueba el documento.</div>
          </div>

          <div style="display: flex; gap: 10px; flex-wrap: wrap; margin-top: 22px">
            <button class="cm-action" on:click={startProcessing} disabled={busy}>
              {busy ? "Preparando…" : "Iniciar procesamiento"}
            </button>
            <button class="cm-action cm-action--ghost" on:click={goBackToInfo}>Volver</button>
          </div>

          {#if actionError}
            <div class="cm-message cm-message--error" role="alert">
              <span class="cm-msg-icon" aria-hidden="true">!</span>
              <div>{actionError}</div>
            </div>
          {/if}
        </div>
      </div>
    </section>

  {:else if step === 4}
    <!-- ── Etapa 4 · Procesamiento ───────────────────────────────────── -->
    <section aria-labelledby="cm-step-process-title" aria-live="polite" aria-busy={!isTerminal(currentJob?.status)}>
      <div class="cm-card cm-card--flat">
        <div class="cm-card-head">
          <h2 id="cm-step-process-title">Procesando el documento</h2>
          <p style="color: var(--ink-700); font-size: 0.86rem; margin: 6px 0 0" dir={titleDir?.direction} lang={titleDir?.lang}>
            {title.trim() || currentJob?.title}
          </p>
        </div>
        <div class="cm-card-body">
          <div class="cm-progress-wrap">
            <div class="cm-progress-meta">
              <span>{statusLabel}</span>
              <span>{progressPercent}%</span>
            </div>
            <div class="cm-progress-bar" role="presentation">
              <span style="width: {progressPercent}%"></span>
            </div>
          </div>

          <ul class="cm-stages">
            {#each stageRows as stage (stage.key)}
              <li class="cm-stage" data-state={stage.state}>
                <span class="cm-stage-icon" aria-hidden="true">
                  {stage.state === "done" ? "✓" : stage.state === "failed" ? "✗" : ""}
                </span>
                <span class="cm-stage-name">{stage.label}</span>
                <span class="cm-stage-state">
                  {stage.state === "pending" ? "Pendiente" : stage.state === "active" ? "En curso" : stage.state === "done" ? "Completada" : stage.state === "failed" ? "Fallida" : "Con observaciones"}
                </span>
              </li>
            {/each}
          </ul>

          {#if currentJob?.status === "queued" || currentJob?.status === "claimed"}
            <p style="color: var(--ink-700); font-size: 0.8rem; margin-top: 14px">
              En cola de procesamiento — el archivo fue validado y está esperando al servicio.
            </p>
          {/if}

          <div class="cm-persist-note">
            Podés salir de esta pantalla. El procesamiento continuará y quedará registrado en el historial.
          </div>

          {#if canCancel}
            <div style="display: flex; gap: 10px; margin-top: 18px; flex-wrap: wrap">
              <button class="cm-action cm-action--danger" on:click={handleCancel} disabled={busy}>
                Cancelar
              </button>
            </div>
          {/if}

          {#if actionError}
            <div class="cm-message cm-message--error" role="alert">
              <span class="cm-msg-icon" aria-hidden="true">!</span>
              <div>{actionError}</div>
            </div>
          {/if}
        </div>
      </div>
    </section>

  {:else}
    <!-- ── Etapa 5 · Resultado ───────────────────────────────────────── -->
    <section aria-labelledby="cm-step-result-title" aria-live="polite">
      <div class="cm-card cm-card--flat cm-result">
        <div class="cm-card-body">
          {#if currentJob?.status === "completed"}
            <div class="cm-result-head">
              <span class="cm-result-mark" data-tone="success" aria-hidden="true">✓</span>
              <div>
                <h2 id="cm-step-result-title">Documento procesado</h2>
                <span class="cm-result-status">Candidato para revisión</span>
              </div>
            </div>
            <p style="color: var(--ink-700); line-height: 1.6; max-width: 560px; margin-top: 16px">
              El documento quedó disponible para revisión. Todavía no fue aprobado.
            </p>
          {:else if currentJob?.status === "completed_with_warnings"}
            <div class="cm-result-head">
              <span class="cm-result-mark" data-tone="warning" aria-hidden="true">!</span>
              <div>
                <h2 id="cm-step-result-title">Documento procesado con observaciones</h2>
                <span class="cm-result-status">Candidato para revisión</span>
              </div>
            </div>
            <p style="color: var(--ink-700); line-height: 1.6; max-width: 560px; margin-top: 16px">
              El documento quedó disponible para revisión, pero se detectaron aspectos que conviene verificar.
            </p>
            {#if resultWarnings.length > 0}
              <div class="cm-message cm-message--warning">
                <span class="cm-msg-icon" aria-hidden="true">i</span>
                <ul>
                  {#each resultWarnings as w}
                    <li>{w}</li>
                  {/each}
                </ul>
              </div>
            {/if}
          {:else if jobFailed}
            <div class="cm-result-head">
              <span class="cm-result-mark" data-tone="danger" aria-hidden="true">✗</span>
              <div>
                <h2 id="cm-step-result-title">No se pudo completar el procesamiento</h2>
                <span class="cm-result-status" style="background: #f6e0dc; color: #8b3028">Fallido</span>
              </div>
            </div>
            <div class="cm-message cm-message--error">
              <span class="cm-msg-icon" aria-hidden="true">!</span>
              <div>
                {currentJob?.error_message || "El procesamiento no pudo completarse."}
                {#if currentJob?.error_code}
                  <span class="cm-msg-code">Código: {currentJob.error_code}</span>
                {/if}
              </div>
            </div>
            <p style="color: var(--ink-700); line-height: 1.6; margin-top: 16px">
              El archivo original permanece disponible un tiempo limitado. Podés reintentar el procesamiento.
            </p>
          {:else}
            <div class="cm-result-head">
              <span class="cm-result-mark" data-tone="danger" aria-hidden="true">!</span>
              <div>
                <h2 id="cm-step-result-title">No se pudo completar el procesamiento</h2>
              </div>
            </div>
          {/if}

          {#if currentJob?.status === "completed" || currentJob?.status === "completed_with_warnings"}
            <div class="cm-result-stats">
              <div class="cm-stat">
                <strong>{diagnostic?.pdf_pages ?? currentJob?.progress?.progress_percent ?? "—"}</strong>
                <span>páginas</span>
              </div>
              <div class="cm-stat">
                <strong>{diagnostic?.textual_pages ?? "—"}</strong>
                <span>páginas con contenido</span>
              </div>
              <div class="cm-stat">
                <strong>{diagnostic?.chunks ?? "—"}</strong>
                <span>fragmentos preparados</span>
              </div>
              <div class="cm-stat">
                <strong>{diagnostic?.embeddings ?? "—"}</strong>
                <span>registros de búsqueda</span>
              </div>
            </div>

            {#if diagnostic && diagnostic.duration_seconds != null}
              <p style="color: var(--ink-700); font-size: 0.78rem; margin-top: 14px">
                Procesado en {formatDuration(diagnostic.duration_seconds)}.
              </p>
            {/if}
          {/if}

          <div style="display: flex; gap: 10px; flex-wrap: wrap; margin-top: 24px">
            {#if canRetry}
              <button class="cm-action" on:click={handleRetry} disabled={busy}>
                {busy ? "Reintentando…" : "Reintentar"}
              </button>
            {/if}
            <button class="cm-action" on:click={openDiagnostic} disabled={loadingDiagnostic}>
              {loadingDiagnostic ? "Abriendo…" : "Abrir diagnóstico"}
            </button>
            {#if currentJob?.status === "completed" || currentJob?.status === "completed_with_warnings"}
              <button class="cm-action cm-action--ghost" on:click={tryInResearch}>Probar en Investigación</button>
            {/if}
            <button class="cm-action cm-action--ghost" on:click={onExit}>Volver al gestor</button>
          </div>

          {#if currentJob?.status === "completed" || currentJob?.status === "completed_with_warnings"}
            <p style="color: var(--ink-700); font-size: 0.78rem; margin-top: 16px">
              Este documento todavía no fue aprobado.
            </p>
          {/if}

          {#if actionError}
            <div class="cm-message cm-message--error" role="alert">
              <span class="cm-msg-icon" aria-hidden="true">!</span>
              <div>{actionError}</div>
            </div>
          {/if}
        </div>
      </div>
    </section>
  {/if}
</div>

<style>
  .visually-hidden {
    position: absolute;
    width: 1px;
    height: 1px;
    padding: 0;
    margin: -1px;
    overflow: hidden;
    clip: rect(0 0 0 0);
    white-space: nowrap;
    border: 0;
  }
</style>
