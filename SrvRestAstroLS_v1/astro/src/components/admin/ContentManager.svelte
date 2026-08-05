<script lang="ts">
  import { onMount, tick } from "svelte";

  type UploadState = {
    upload_id: string;
    filename: string;
    size_bytes: number;
    sha256: string;
    validation_status: string;
    duplicate_status: string;
    warnings: string[];
    page_count: number | null;
    limits: { max_upload_bytes: number; max_pdf_pages: number };
  } | null;

  type JobItem = {
    job_id: string;
    title: string;
    language: string;
    status: string;
    current_stage: string | null;
    created_at: string | null;
    filename: string | null;
    sha256_short: string | null;
  };

  type JobDetail = JobItem & {
    upload_id?: string;
    page_count?: number;
    textual_pages?: number | null;
    chunk_count?: number;
    embedding_count?: number;
    error_message?: string | null;
    warning_codes?: string[];
    progress?: { progress_percent: number; stage_display: string; stage_states: Record<string,string>; is_terminal: boolean };
    attempts?: Array<{ attempt_number: number; status: string; started_at: string; error_message?: string | null }>;
    reconciliation?: Record<string,unknown>;
  };

  let accessToken = "";
  let view: "list" | "upload" | "confirm" | "progress" | "result" | "detail" = "list";
  let jobs: JobItem[] = [];
  let summary: Record<string, number> = {};
  let error = "";
  let loading = false;

  // Upload
  let upload: UploadState = null;
  let title = "";
  let language = "auto";
  let workFamily = "";
  let adminNotes = "";
  let uploadError = "";
  let uploading = false;

  // Progress
  let currentJobId = "";
  let jobStatus = "";
  let progressPercent = 0;
  let stageDisplay = "";
  let stageStates: Record<string, string> = {};
  let jobError = "";
  let jobWarnings: string[] = [];
  let pollTimer: ReturnType<typeof setInterval> | null = null;

  // Detail
  let detailJob: JobDetail | null = null;
  let detailLoading = false;

  const STAGE_LABELS: Record<string, string> = {
    uploaded: "Archivo recibido",
    validating: "Validando el archivo",
    validation_failed: "Validación fallida",
    ready_to_ingest: "Listo para procesar",
    queued: "En cola de procesamiento",
    extracting: "Extrayendo las páginas",
    normalizing: "Normalizando el contenido",
    persisting_pages: "Organizando las secciones",
    building_chunks: "Preparando la búsqueda",
    embedding: "Generando el índice",
    indexing: "Indexando el contenido",
    validating_result: "Verificando el resultado",
    completed: "Documento procesado",
    completed_with_warnings: "Documento procesado con observaciones",
    failed: "No se pudo completar el procesamiento",
    cancelled: "Procesamiento cancelado",
  };

  const ERROR_TRANSLATIONS: Record<string, string> = {
    INVALID_PDF: "El archivo no es un PDF válido o está dañado.",
    PDF_ENCRYPTED: "El PDF está protegido y no puede procesarse.",
    EXACT_DUPLICATE: "Este mismo archivo ya fue cargado.",
    FILE_TOO_LARGE: "El archivo supera el tamaño permitido.",
    PAGE_LIMIT_EXCEEDED: "El documento excede el límite de páginas.",
    INGESTION_FAILED: "El procesamiento no pudo completarse.",
    NEEDS_PIPELINE_REVIEW: "El documento necesita una revisión técnica antes de procesarse.",
    REUPLOAD_REQUIRED: "El archivo original ya no está disponible. Volvé a cargarlo para intentar nuevamente.",
  };

  function translateError(code: string): string {
    return ERROR_TRANSLATIONS[code] || code;
  }

  $: pendingCount = summary["validating"] || 0;
  $: processingCount = (summary["queued"] || 0) + (summary["extracting"] || 0) + (summary["normalizing"] || 0) + (summary["persisting_pages"] || 0) + (summary["building_chunks"] || 0) + (summary["embedding"] || 0) + (summary["indexing"] || 0) + (summary["validating_result"] || 0);
  $: reviewCount = (summary["completed"] || 0) + (summary["completed_with_warnings"] || 0);
  $: failedCount = (summary["failed"] || 0);

  // ---- CSS classes --------------------------------------------------------
  const btnPrimary = "inline-flex items-center justify-center gap-2 min-h-[44px] rounded-[7px] px-5 text-sm font-semibold text-[#fffdf8] bg-[var(--navy-950)] hover:bg-[var(--navy-800)] transition shadow-[0_7px_16px_rgba(6,31,59,.14)]";
  const btnSecondary = "inline-flex items-center justify-center gap-2 min-h-[44px] rounded-[7px] px-4 text-sm font-semibold text-[var(--navy-900)] border border-[var(--line)] bg-transparent hover:bg-[var(--ivory-100)] transition";
  const btnGhost = "inline-flex items-center gap-1 text-sm font-medium text-[var(--ink-700)] hover:text-[var(--navy-950)] transition border-0 bg-transparent p-0 cursor-pointer";
  const cardClass = "rounded-[7px] border border-[var(--line)] bg-white p-5 sm:p-6";
  const cardLight = "rounded-[7px] border border-[var(--line)] bg-[var(--ivory-100)] p-5";
  const labelClass = "block text-xs font-bold uppercase tracking-[0.12em] text-[var(--ink-700)] mb-1.5";
  const inputClass = "w-full min-h-[44px] rounded-[6px] border border-[var(--line)] px-3 py-2 text-sm bg-white text-[var(--ink-900)] font-[var(--sans)] focus:outline-none focus:border-[var(--gold-500)]";
  const selectClass = "w-full min-h-[44px] rounded-[6px] border border-[var(--line)] px-3 py-2 text-sm bg-white text-[var(--ink-900)] font-[var(--sans)] focus:outline-none focus:border-[var(--gold-500)] appearance-none";
  const badgeSuccess = "inline-flex items-center rounded-full bg-[#e8f5ec] px-2.5 py-0.5 text-xs font-semibold text-[#2d6a3c]";
  const badgeWarning = "inline-flex items-center rounded-full bg-[#fff2d8] px-2.5 py-0.5 text-xs font-semibold text-[#8a611c]";
  const badgeError = "inline-flex items-center rounded-full bg-[#fff0ed] px-2.5 py-0.5 text-xs font-semibold text-[#a64538]";
  const badgeNeutral = "inline-flex items-center rounded-full bg-[var(--ivory-100)] px-2.5 py-0.5 text-xs font-semibold text-[var(--ink-700)]";
  const alertSuccess = "rounded-[6px] border-l-[3px] border-l-[#2d6a3c] bg-[#e8f5ec] p-3.5 text-sm text-[#2d6a3c]";
  const alertWarning = "rounded-[6px] border-l-[3px] border-l-[var(--gold-500)] bg-[#fff2d8] p-3.5 text-sm text-[#8a611c]";
  const alertError = "rounded-[6px] border-l-[3px] border-l-[#a64538] bg-[#fff0ed] p-3.5 text-sm text-[#a64538]";
  const alertInfo = "rounded-[6px] border-l-[3px] border-l-[var(--navy-800)] bg-[var(--ivory-100)] p-3.5 text-sm text-[var(--ink-700)]";

  function statusBadgeClass(status: string): string {
    if (status === "completed") return badgeSuccess;
    if (status === "completed_with_warnings") return badgeWarning;
    if (status === "failed" || status === "cancelled") return badgeError;
    return badgeNeutral;
  }

  function statusLabel(s: string) { return STAGE_LABELS[s] || s; }
  function formatBytes(bytes: number) {
    if (bytes < 1024) return `${bytes} B`;
    if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
    return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
  }
  function formatDate(d: string | null) {
    if (!d) return "";
    return new Date(d).toLocaleDateString("es-AR", { day: "2-digit", month: "short", year: "numeric" });
  }

  // ---- API ----------------------------------------------------------------
  async function getToken() {
    const raw = localStorage.getItem("tebaai_access_token");
    if (raw) accessToken = raw;
  }

  async function api(path: string, options: RequestInit = {}) {
    const headers: Record<string, string> = { Authorization: `Bearer ${accessToken}` };
    if (!(options.body instanceof FormData)) headers["Content-Type"] = "application/json";
    const res = await fetch(`/api${path}`, {
      ...options,
      headers: { ...headers, ...((options.headers as Record<string, string>) || {}) },
    });
    if (res.status === 401) { window.location.href = "/login"; throw new Error("Unauthorized"); }
    if (res.status === 403) throw new Error("Acceso denegado");
    if (!res.ok) {
      const detail = (await res.json().catch(() => ({}))) as { detail?: string };
      throw new Error(detail?.detail || `Error ${res.status}`);
    }
    return res.json();
  }

  async function loadJobs() {
    loading = true;
    try {
      const data = await api("/admin/content/jobs");
      jobs = data.jobs || [];
      summary = data.summary || {};
    } catch (e: any) { error = e.message; }
    finally { loading = false; }
  }

  function startUpload() {
    view = "upload"; upload = null; uploadError = ""; title = ""; language = "auto"; workFamily = "";
  }

  async function handleFile(ev: Event) {
    const target = ev.target as HTMLInputElement;
    const file = target.files?.[0];
    if (!file) return;
    uploading = true; uploadError = "";
    try {
      const fd = new FormData(); fd.append("file", file);
      upload = await api("/admin/content/uploads", { method: "POST", body: fd });
    } catch (e: any) { uploadError = translateError(e.message); }
    finally { uploading = false; }
  }

  async function handleDrop(ev: DragEvent) {
    ev.preventDefault();
    const file = ev.dataTransfer?.files?.[0];
    if (!file) return;
    uploading = true; uploadError = "";
    try {
      const fd = new FormData(); fd.append("file", file);
      upload = await api("/admin/content/uploads", { method: "POST", body: fd });
    } catch (e: any) { uploadError = translateError(e.message); }
    finally { uploading = false; }
  }

  function goToConfirm() { view = "confirm"; }

  async function startJob() {
    if (!upload) return;
    error = "";
    try {
      const job = await api("/admin/content/jobs", {
        method: "POST",
        body: JSON.stringify({
          upload_id: upload.upload_id,
          title: title || upload.filename.replace(".pdf", ""),
          language, work_family: workFamily || null,
          administrative_notes: adminNotes || null,
        }),
      });
      currentJobId = job.job_id; jobStatus = job.status;
      progressPercent = job.progress?.progress_percent || 0;
      stageDisplay = job.progress?.stage_display || "";
      stageStates = job.progress?.stage_states || {};
      view = "progress"; startPolling();
    } catch (e: any) { error = e.message; }
  }

  function startPolling() {
    if (pollTimer) clearInterval(pollTimer);
    pollTimer = setInterval(pollJob, 2000);
  }

  async function pollJob() {
    try {
      const job = await api(`/admin/content/jobs/${currentJobId}`);
      jobStatus = job.status; progressPercent = job.progress?.progress_percent || 0;
      stageDisplay = job.progress?.stage_display || "";
      stageStates = job.progress?.stage_states || {};
      jobError = job.error_message || "";
      jobWarnings = job.warning_codes || [];
      if (job.progress?.is_terminal) {
        if (pollTimer) clearInterval(pollTimer);
        pollTimer = null; view = "result";
      }
    } catch (e) { /* continue polling */ }
  }

  async function retryJob(jobId: string) {
    try {
      const job = await api(`/admin/content/jobs/${jobId}/retry`, { method: "POST" });
      currentJobId = job.job_id; jobStatus = job.status;
      progressPercent = job.progress?.progress_percent || 0;
      stageDisplay = job.progress?.stage_display || "";
      stageStates = job.progress?.stage_states || {};
      view = "progress"; startPolling();
    } catch (e: any) { error = e.message; }
  }

  async function cancelJob(jobId: string) {
    try {
      await api(`/admin/content/jobs/${jobId}/cancel`, { method: "POST" });
      await loadJobs(); view = "list";
    } catch (e: any) { error = e.message; }
  }

  async function openDetail(jobId: string) {
    detailLoading = true; view = "detail";
    try {
      detailJob = await api(`/admin/content/jobs/${jobId}`);
    } catch (e: any) { error = e.message; }
    finally { detailLoading = false; }
  }

  onMount(async () => { await getToken(); await loadJobs(); });
</script>

<div class="w-full max-w-[960px] mx-auto px-4 sm:px-6 lg:px-8 py-8">
  <!-- Header editorial -->
  <header class="mb-10">
    <p class="text-[var(--gold-500)] text-xs font-bold uppercase tracking-[0.18em] mb-2">Administración</p>
    <h1 class="text-[var(--navy-950)] text-3xl sm:text-4xl font-[500] font-[var(--serif)] tracking-[-0.02em] mb-2">Gestor de Contenidos</h1>
    <p class="text-[var(--ink-700)] text-sm leading-relaxed max-w-[540px]">Carga, procesamiento y validación de fuentes documentales para la biblioteca de Breslov Research.</p>
  </header>

  {#if view === "list"}
    <!-- Summary -->
    <div class="grid grid-cols-2 sm:grid-cols-4 gap-3 mb-8">
      <div class={cardLight}>
        <p class="text-xs text-[var(--ink-700)] mb-1">En proceso</p>
        <p class="text-2xl font-[500] font-[var(--serif)] text-[var(--navy-950)]">{processingCount + pendingCount}</p>
      </div>
      <div class={cardLight}>
        <p class="text-xs text-[var(--ink-700)] mb-1">Pendientes revisión</p>
        <p class="text-2xl font-[500] font-[var(--serif)] text-[var(--navy-950)]">{reviewCount}</p>
      </div>
      <div class={cardLight}>
        <p class="text-xs text-[var(--ink-700)] mb-1">Con observaciones</p>
        <p class="text-2xl font-[500] font-[var(--serif)] text-[var(--gold-500)]">{summary["completed_with_warnings"] || 0}</p>
      </div>
      <div class={cardLight}>
        <p class="text-xs text-[var(--ink-700)] mb-1">Fallidos</p>
        <p class="text-2xl font-[500] font-[var(--serif)] text-[#a64538]">{failedCount}</p>
      </div>
    </div>

    <div class="flex justify-between items-center mb-5">
      <h2 class="text-lg font-[500] font-[var(--serif)] text-[var(--navy-950)]">Cargas recientes</h2>
      <button class={btnPrimary} on:click={startUpload}>Nueva carga</button>
    </div>

    {#if loading}
      <div class="flex justify-center py-16 text-[var(--ink-700)] italic font-[var(--serif)]">Consultando documentos…</div>
    {:else if jobs.length === 0}
      <div class="text-center py-20 border border-dashed border-[var(--line)] rounded-[7px]">
        <p class="text-[var(--navy-950)] text-lg font-[500] font-[var(--serif)] mb-2">Todavía no hay documentos cargados</p>
        <p class="text-[var(--ink-700)] text-sm mb-5 max-w-[380px] mx-auto">Las nuevas fuentes documentales aparecerán aquí junto con su estado de procesamiento.</p>
        <button class={btnPrimary} on:click={startUpload}>Cargar primer documento</button>
      </div>
    {:else}
      <!-- Desktop table -->
      <div class="hidden md:block">
        <div class="border border-[var(--line)] rounded-[7px] overflow-hidden">
          <table class="w-full text-sm">
            <thead class="bg-[var(--ivory-100)] text-[var(--ink-700)] text-xs font-bold uppercase tracking-[0.1em]">
              <tr>
                <th class="px-4 py-3 text-start font-[var(--sans)]">Documento</th>
                <th class="px-4 py-3 text-start font-[var(--sans)]">Idioma</th>
                <th class="px-4 py-3 text-start font-[var(--sans)]">Estado</th>
                <th class="px-4 py-3 text-start font-[var(--sans)]">Etapa</th>
                <th class="px-4 py-3 text-start font-[var(--sans)]">Fecha</th>
                <th class="px-4 py-3 text-start font-[var(--sans)] w-10"></th>
              </tr>
            </thead>
            <tbody class="divide-y divide-[var(--line)]">
              {#each jobs as job}
                <tr class="hover:bg-[var(--ivory-100)] transition-colors cursor-pointer" on:click={() => openDetail(job.job_id)}>
                  <td class="px-4 py-3.5 font-medium text-[var(--navy-950)] max-w-[240px] truncate" dir="auto">{job.title}</td>
                  <td class="px-4 py-3.5 text-[var(--ink-700)]">{job.language === "auto" ? "Auto" : job.language.toUpperCase()}</td>
                  <td class="px-4 py-3.5"><span class={statusBadgeClass(job.status)}>{statusLabel(job.status)}</span></td>
                  <td class="px-4 py-3.5 text-xs text-[var(--ink-700)]">{statusLabel(job.current_stage || job.status)}</td>
                  <td class="px-4 py-3.5 text-xs text-[var(--ink-700)] whitespace-nowrap">{formatDate(job.created_at)}</td>
                  <td class="px-4 py-3.5 text-[var(--ink-700)]">→</td>
                </tr>
              {/each}
            </tbody>
          </table>
        </div>
      </div>
      <!-- Mobile cards -->
      <div class="md:hidden space-y-3">
        {#each jobs as job}
          <button class={`${cardClass} w-full text-left cursor-pointer hover:border-[var(--gold-500)] transition-colors`} on:click={() => openDetail(job.job_id)}>
            <div class="flex justify-between items-start gap-3 mb-2">
              <h3 class="font-semibold text-sm text-[var(--navy-950)] truncate" dir="auto">{job.title}</h3>
              <span class={statusBadgeClass(job.status)}>{statusLabel(job.status)}</span>
            </div>
            <div class="flex justify-between text-xs text-[var(--ink-700)]">
              <span>{job.language === "auto" ? "Auto" : job.language.toUpperCase()}</span>
              <span>{formatDate(job.created_at)}</span>
            </div>
          </button>
        {/each}
      </div>
    {/if}

  {:else if view === "upload"}
    <div class="max-w-[560px] mx-auto">
      <button class={btnGhost + " mb-4"} on:click={() => { view = "list"; loadJobs(); }}>← Volver al gestor</button>
      <h2 class="text-xl font-[500] font-[var(--serif)] text-[var(--navy-950)] mb-1">Nueva carga</h2>
      <p class="text-sm text-[var(--ink-700)] mb-6">Etapa 1 de 3 — Archivo</p>

      {#if !upload}
        <div
          class="border-2 border-dashed border-[var(--line)] rounded-[7px] p-12 text-center cursor-pointer hover:border-[var(--gold-500)] transition-colors"
          on:dragover={(e) => e.preventDefault()}
          on:drop={handleDrop}
          on:click={() => document.getElementById("cm-file-input")?.click()}
          role="button" tabindex="0"
          aria-label="Seleccioná una fuente documental"
          on:keypress={(e) => e.key === "Enter" && document.getElementById("cm-file-input")?.click()}
        >
          <input id="cm-file-input" type="file" accept=".pdf,application/pdf" class="hidden" on:change={handleFile} aria-hidden="true" />
          {#if uploading}
            <p class="text-[var(--ink-700)] italic font-[var(--serif)]">Validando…</p>
          {:else}
            <div class="text-[var(--navy-800)] text-4xl mb-3">📄</div>
            <p class="text-lg font-[500] font-[var(--serif)] text-[var(--navy-950)] mb-1">Seleccioná una fuente documental</p>
            <p class="text-sm text-[var(--ink-700)] mb-1">PDF de hasta 200 MB. El archivo será validado antes de iniciar su procesamiento.</p>
            <p class="text-xs text-[var(--ink-700)] opacity-60">Arrastrá el archivo aquí o hacé clic para seleccionarlo</p>
          {/if}
        </div>
      {:else}
        <div class={cardClass + " mb-6"}>
          <h3 class="font-semibold text-lg text-[var(--navy-950)] mb-3 truncate" dir="auto">{upload.filename}</h3>
          <div class="grid grid-cols-2 gap-2 text-sm mb-4">
            <div><span class="text-[var(--ink-700)] text-xs">Tamaño:</span> <span class="font-medium">{formatBytes(upload.size_bytes)}</span></div>
            <div><span class="text-[var(--ink-700)] text-xs">Páginas:</span> <span class="font-medium">{upload.page_count ?? "—"}</span></div>
          </div>

          {#if upload.validation_status === "valid"}
            <div class={alertSuccess + " mb-3"}>Archivo validado correctamente</div>
          {/if}
          {#if upload.duplicate_status !== "new_document"}
            <div class={alertWarning + " mb-3"}>Ya existe un documento con características similares. Verificá antes de continuar.</div>
          {/if}
          {#if upload.warnings.length > 0}
            <div class={alertWarning + " mb-3"}>
              <ul class="list-disc ml-4 text-sm">
                {#each upload.warnings as w}<li>{translateError(w)}</li>{/each}
              </ul>
            </div>
          {/if}

          <div class="space-y-4 mt-5 pt-4 border-t border-[var(--line)]">
            <div>
              <label class={labelClass} for="cm-title">Título de la obra</label>
              <input id="cm-title" type="text" class={inputClass} bind:value={title} placeholder={upload.filename.replace(".pdf", "")} dir="auto" />
            </div>
            <div>
              <label class={labelClass} for="cm-lang">Idioma principal</label>
              <select id="cm-lang" class={selectClass} bind:value={language}>
                <option value="auto">Automático</option>
                <option value="es">Español</option>
                <option value="en">Inglés</option>
                <option value="he">Hebreo</option>
                <option value="mixed">Mixto</option>
                <option value="unknown">Desconocido</option>
              </select>
            </div>
            <div>
              <label class={labelClass} for="cm-family">Familia documental <span class="font-normal normal-case tracking-normal">(opcional)</span></label>
              <input id="cm-family" type="text" class={inputClass} bind:value={workFamily} placeholder="Ej: Likutey Moharán, Kitzur, Sipurey Maasiot" />
            </div>
            <button class={btnPrimary + " w-full justify-center"} on:click={goToConfirm}>Continuar a confirmación</button>
            <button class={btnGhost + " w-full justify-center"} on:click={() => { upload = null; }}>Seleccionar otro archivo</button>
          </div>
        </div>
      {/if}

      {#if uploadError}
        <div class={alertError + " mt-4"}>{uploadError}</div>
      {/if}
    </div>

  {:else if view === "confirm"}
    <div class="max-w-[560px] mx-auto">
      <h2 class="text-xl font-[500] font-[var(--serif)] text-[var(--navy-950)] mb-1">Confirmar procesamiento</h2>
      <p class="text-sm text-[var(--ink-700)] mb-6">Etapa 3 de 3 — Confirmación</p>

      {#if upload}
        <div class={cardClass + " mb-6"}>
          <h3 class="font-semibold text-lg text-[var(--navy-950)] mb-4" dir="auto">{title || upload.filename}</h3>
          <dl class="grid grid-cols-2 gap-y-3 text-sm">
            <dt class="text-[var(--ink-700)] text-xs">Archivo</dt><dd class="font-medium truncate" dir="auto">{upload.filename}</dd>
            <dt class="text-[var(--ink-700)] text-xs">Idioma</dt><dd class="font-medium">{language === "auto" ? "Automático" : language.toUpperCase()}</dd>
            <dt class="text-[var(--ink-700)] text-xs">Páginas</dt><dd class="font-medium">{upload.page_count ?? "—"}</dd>
            <dt class="text-[var(--ink-700)] text-xs">Tamaño</dt><dd class="font-medium">{formatBytes(upload.size_bytes)}</dd>
            {#if workFamily}
              <dt class="text-[var(--ink-700)] text-xs">Familia</dt><dd class="font-medium">{workFamily}</dd>
            {/if}
          </dl>

          <div class={alertInfo + " mt-5"}>El documento será procesado y quedará como candidato para revisión.</div>
          <div class={alertWarning + " mt-2"}>Esta operación no publica ni aprueba el documento.</div>

          <div class="flex gap-3 mt-6">
            <button class={btnPrimary + " flex-1 justify-center"} on:click={startJob}>Iniciar procesamiento</button>
            <button class={btnSecondary} on:click={() => view = "upload"}>Volver</button>
          </div>
        </div>
      {/if}
    </div>

  {:else if view === "progress"}
    <div class="max-w-[560px] mx-auto">
      <h2 class="text-xl font-[500] font-[var(--serif)] text-[var(--navy-950)] mb-1">Procesando documento</h2>
      <p class="text-sm text-[var(--ink-700)] mb-6" dir="auto">{title || "Documento"}</p>

      <div class={cardClass + " mb-6"}>
        <div class="mb-6">
          <div class="flex justify-between text-sm mb-2">
            <span class="font-medium">{statusLabel(jobStatus)}</span>
            <span class="text-[var(--ink-700)]">{Math.round(progressPercent)}%</span>
          </div>
          <div class="h-1.5 rounded-full bg-[var(--ivory-100)] overflow-hidden">
            <div class="h-full rounded-full bg-[var(--navy-800)] transition-all duration-500" style="width: {progressPercent}%"></div>
          </div>
        </div>

        <div class="space-y-2.5" role="status" aria-live="polite">
          {#each Object.entries(stageStates) as [stage, state]}
            <div class="flex items-center gap-2.5 text-sm">
              {#if state === "done"}
                <span class="text-[#2d6a3c] text-xs">✓</span>
                <span class="text-[var(--ink-900)]">{STAGE_LABELS[stage] || stage}</span>
              {:else if state === "active" || stage === jobStatus}
                <span class="w-3.5 h-3.5 rounded-full border-2 border-[var(--navy-800)] border-t-transparent animate-spin"></span>
                <span class="font-medium text-[var(--navy-950)]">{STAGE_LABELS[stage] || stage}</span>
              {:else if state === "failed"}
                <span class="text-[#a64538] text-xs">✗</span>
                <span class="text-[#a64538]">{STAGE_LABELS[stage] || stage}</span>
              {:else}
                <span class="w-3.5 h-3.5 rounded-full border border-[var(--line)]"></span>
                <span class="text-[var(--ink-700)] opacity-50">{STAGE_LABELS[stage] || stage}</span>
              {/if}
            </div>
          {/each}
        </div>

        {#if jobError}
          <div class={alertError + " mt-4"}>{translateError(jobError)}</div>
        {/if}
        <p class="text-xs text-[var(--ink-700)] opacity-60 mt-5">Podés salir de esta pantalla. El procesamiento continuará y quedará registrado en el historial.</p>
      </div>
    </div>

  {:else if view === "result"}
    <div class="max-w-[560px] mx-auto">
      {#if jobStatus === "completed"}
        <h2 class="text-xl font-[500] font-[var(--serif)] text-[var(--navy-950)] mb-4">Documento procesado</h2>
        <div class={alertSuccess + " mb-5"}>Candidato para revisión</div>
      {:else if jobStatus === "completed_with_warnings"}
        <h2 class="text-xl font-[500] font-[var(--serif)] text-[var(--navy-950)] mb-4">Documento procesado con observaciones</h2>
        <div class={alertWarning + " mb-5"}>El documento quedó disponible para revisión, pero se detectaron aspectos que conviene verificar.</div>
      {:else if jobStatus === "failed"}
        <h2 class="text-xl font-[500] font-[var(--serif)] text-[var(--navy-950)] mb-4">No se pudo completar el procesamiento</h2>
        <div class={alertError + " mb-5"}>{translateError(jobError) || "Error desconocido durante el procesamiento."}</div>
      {/if}

      <div class={cardClass + " mb-6"}>
        {#if jobWarnings.length > 0}
          <div class="mb-4">
            <h3 class="font-semibold text-sm text-[var(--navy-950)] mb-2">Observaciones</h3>
            <ul class="list-disc ml-4 text-sm text-[var(--ink-700)] space-y-1">
              {#each jobWarnings as w}<li>{translateError(w)}</li>{/each}
            </ul>
          </div>
        {/if}
        <div class="flex flex-col sm:flex-row gap-3">
          <button class={btnPrimary + " justify-center flex-1"} on:click={() => { view = "list"; loadJobs(); }}>Volver al gestor</button>
          {#if jobStatus === "failed"}
            <button class={btnSecondary + " justify-center"} on:click={() => retryJob(currentJobId)}>Reintentar</button>
          {/if}
          <button class={btnGhost + " justify-center"} on:click={() => { view = "list"; loadJobs(); }}>Ir al historial</button>
        </div>
      </div>
    </div>

  {:else if view === "detail"}
    <div class="max-w-[720px] mx-auto">
      <button class={btnGhost + " mb-4"} on:click={() => { view = "list"; loadJobs(); }}>← Volver al gestor</button>

      {#if detailLoading}
        <div class="flex justify-center py-16 text-[var(--ink-700)] italic font-[var(--serif)]">Consultando documento…</div>
      {:else if detailJob}
        <h2 class="text-xl font-[500] font-[var(--serif)] text-[var(--navy-950)] mb-1" dir="auto">{detailJob.title}</h2>
        <div class="flex flex-wrap gap-2 mb-6">
          <span class={statusBadgeClass(detailJob.status)}>{statusLabel(detailJob.status)}</span>
          <span class={badgeNeutral}>{detailJob.language === "auto" ? "Auto" : detailJob.language.toUpperCase()}</span>
        </div>

        <!-- Summary -->
        <div class={cardClass + " mb-5"}>
          <h3 class="text-sm font-semibold text-[var(--navy-950)] mb-4">Resumen</h3>
          <dl class="grid grid-cols-2 sm:grid-cols-3 gap-y-3 text-sm">
            <dt class="text-[var(--ink-700)] text-xs">Archivo</dt><dd class="font-medium truncate col-span-2" dir="auto">{detailJob.filename || "—"}</dd>
            <dt class="text-[var(--ink-700)] text-xs">Fecha</dt><dd class="font-medium">{formatDate(detailJob.created_at)}</dd>
            <dt class="text-[var(--ink-700)] text-xs">Páginas</dt><dd class="font-medium">{detailJob.page_count ?? "—"}</dd>
            {#if detailJob.textual_pages != null}
              <dt class="text-[var(--ink-700)] text-xs">Con contenido</dt><dd class="font-medium">{detailJob.textual_pages}</dd>
            {/if}
            {#if detailJob.chunk_count != null}
              <dt class="text-[var(--ink-700)] text-xs">Fragmentos</dt><dd class="font-medium">{detailJob.chunk_count}</dd>
            {/if}
            {#if detailJob.embedding_count != null}
              <dt class="text-[var(--ink-700)] text-xs">Registros búsqueda</dt><dd class="font-medium">{detailJob.embedding_count}</dd>
            {/if}
          </dl>
        </div>

        <!-- Timeline -->
        {#if detailJob.attempts?.length}
          <div class={cardClass + " mb-5"}>
            <h3 class="text-sm font-semibold text-[var(--navy-950)] mb-4">Historial de procesamiento</h3>
            <div class="space-y-3">
              {#each detailJob.attempts as attempt}
                <div class="flex items-center justify-between gap-3 text-sm border-b border-[var(--line)] pb-3 last:border-0 last:pb-0">
                  <div>
                    <span class="font-medium">Intento {attempt.attempt_number}</span>
                    <span class="text-[var(--ink-700)] ml-2">{statusLabel(attempt.status)}</span>
                  </div>
                  <span class="text-xs text-[var(--ink-700)]">{formatDate(attempt.started_at)}</span>
                </div>
              {/each}
            </div>
          </div>
        {/if}

        <!-- Warnings -->
        {#if detailJob.warning_codes?.length}
          <div class={cardClass + " mb-5"}>
            <h3 class="text-sm font-semibold text-[var(--navy-950)] mb-3">Observaciones</h3>
            <ul class="list-disc ml-4 text-sm text-[var(--ink-700)] space-y-1">
              {#each detailJob.warning_codes as w}<li>{translateError(w)}</li>{/each}
            </ul>
          </div>
        {/if}

        <!-- Reconciliación -->
        {#if detailJob.reconciliation}
          <details class={cardClass + " mb-5"}>
            <summary class="text-sm font-semibold text-[var(--navy-950)] cursor-pointer">Diagnóstico técnico</summary>
            <div class="mt-4 space-y-2 text-xs">
              {#each Object.entries(detailJob.reconciliation) as [key, value]}
                <div class="flex justify-between gap-3 py-1 border-b border-[var(--line)] last:border-0">
                  <span class="text-[var(--ink-700)]">{key}</span>
                  <span class="font-medium text-[var(--navy-950)]">{typeof value === "object" ? JSON.stringify(value) : String(value)}</span>
                </div>
              {/each}
            </div>
          </details>
        {/if}

        <!-- Actions -->
        <div class="flex flex-wrap gap-3">
          {#if detailJob.status === "failed"}
            <button class={btnPrimary} on:click={() => retryJob(detailJob.job_id)}>Reintentar procesamiento</button>
          {/if}
          {#if ["uploaded", "ready_to_ingest", "queued"].includes(detailJob.status)}
            <button class={btnSecondary} on:click={() => cancelJob(detailJob.job_id)}>Cancelar</button>
          {/if}
        </div>
      {:else}
        <div class={alertError}>No se pudo cargar el detalle del documento.</div>
      {/if}
    </div>
  {/if}

  {#if error && view !== "upload"}
    <div class="mt-4 {alertError}">{error}</div>
  {/if}
</div>
