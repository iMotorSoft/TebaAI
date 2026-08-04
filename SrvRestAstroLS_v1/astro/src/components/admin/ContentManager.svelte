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

  let accessToken = "";
  let view: "list" | "upload" | "confirm" | "progress" | "result" = "list";
  let jobs: JobItem[] = [];
  let summary: Record<string, number> = {};
  let error = "";
  let loading = false;

  // Upload state
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

  const STATUS_BADGES: Record<string, string> = {
    completed: "badge-success",
    completed_with_warnings: "badge-warning",
    failed: "badge-error",
    cancelled: "badge-ghost",
  };

  async function getToken() {
    const raw = localStorage.getItem("tebaai_access_token");
    if (raw) accessToken = raw;
  }

  async function api(path: string, options: RequestInit = {}) {
    const headers: Record<string, string> = {
      Authorization: `Bearer ${accessToken}`,
    };
    if (!(options.body instanceof FormData)) {
      headers["Content-Type"] = "application/json";
    }
    const res = await fetch(`/api${path}`, {
      ...options,
      headers: { ...headers, ...((options.headers as Record<string, string>) || {}) },
    });
    if (res.status === 401) {
      window.location.href = "/login";
      throw new Error("Unauthorized");
    }
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
    } catch (e: any) {
      error = e.message;
    } finally {
      loading = false;
    }
  }

  function startUpload() {
    view = "upload";
    upload = null;
    uploadError = "";
    title = "";
    language = "auto";
    workFamily = "";
  }

  async function handleFile(ev: Event) {
    const target = ev.target as HTMLInputElement;
    const file = target.files?.[0];
    if (!file) return;
    uploading = true;
    uploadError = "";
    try {
      const fd = new FormData();
      fd.append("file", file);
      upload = await api("/admin/content/uploads", { method: "POST", body: fd });
    } catch (e: any) {
      uploadError = e.message;
    } finally {
      uploading = false;
    }
  }

  async function handleDrop(ev: DragEvent) {
    ev.preventDefault();
    const file = ev.dataTransfer?.files?.[0];
    if (!file) return;
    uploading = true;
    uploadError = "";
    try {
      const fd = new FormData();
      fd.append("file", file);
      upload = await api("/admin/content/uploads", { method: "POST", body: fd });
    } catch (e: any) {
      uploadError = e.message;
    } finally {
      uploading = false;
    }
  }

  function goToConfirm() {
    view = "confirm";
  }

  async function startJob() {
    if (!upload) return;
    error = "";
    try {
      const job = await api("/admin/content/jobs", {
        method: "POST",
        body: JSON.stringify({
          upload_id: upload.upload_id,
          title: title || upload.filename.replace(".pdf", ""),
          language,
          work_family: workFamily || null,
          administrative_notes: adminNotes || null,
        }),
      });
      currentJobId = job.job_id;
      jobStatus = job.status;
      progressPercent = job.progress?.progress_percent || 0;
      stageDisplay = job.progress?.stage_display || "";
      stageStates = job.progress?.stage_states || {};
      view = "progress";
      startPolling();
    } catch (e: any) {
      error = e.message;
    }
  }

  function startPolling() {
    if (pollTimer) clearInterval(pollTimer);
    pollTimer = setInterval(pollJob, 2000);
  }

  async function pollJob() {
    try {
      const job = await api(`/admin/content/jobs/${currentJobId}`);
      jobStatus = job.status;
      progressPercent = job.progress?.progress_percent || 0;
      stageDisplay = job.progress?.stage_display || "";
      stageStates = job.progress?.stage_states || {};
      jobError = job.error_message || "";
      jobWarnings = job.warning_codes || [];
      if (job.progress?.is_terminal) {
        if (pollTimer) clearInterval(pollTimer);
        pollTimer = null;
        view = "result";
      }
    } catch (e) {
      // continue polling
    }
  }

  function formatBytes(bytes: number) {
    if (bytes < 1024) return `${bytes} B`;
    if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
    return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
  }

  function formatDate(d: string | null) {
    if (!d) return "";
    return new Date(d).toLocaleDateString("es-AR", {
      day: "2-digit", month: "short", year: "numeric",
    });
  }

  onMount(async () => {
    await getToken();
    await loadJobs();
  });

  function statusLabel(s: string) {
    return STAGE_LABELS[s] || s;
  }

  $: pendingCount = summary["validating"] || 0;
  $: processingCount = (summary["queued"] || 0) + (summary["extracting"] || 0) + (summary["normalizing"] || 0) + (summary["persisting_pages"] || 0) + (summary["building_chunks"] || 0) + (summary["embedding"] || 0) + (summary["indexing"] || 0) + (summary["validating_result"] || 0);
  $: reviewCount = (summary["completed"] || 0) + (summary["completed_with_warnings"] || 0);
  $: failedCount = (summary["failed"] || 0);
</script>

<div class="w-full max-w-4xl mx-auto">
  <!-- Header -->
  <header class="mb-8">
    <h1 class="text-3xl font-bold text-base-content">Gestor de Contenidos</h1>
    <p class="text-base-content/60 mt-1">Carga, procesamiento y validación de fuentes documentales</p>
  </header>

  {#if view === "list"}
    <!-- Summary row -->
    <div class="flex flex-wrap gap-4 mb-8">
      <div class="stats shadow">
        <div class="stat py-3 px-5">
          <div class="stat-title text-xs">En procesamiento</div>
          <div class="stat-value text-2xl">{processingCount + pendingCount}</div>
        </div>
      </div>
      <div class="stats shadow">
        <div class="stat py-3 px-5">
          <div class="stat-title text-xs">Pendientes de revisión</div>
          <div class="stat-value text-2xl">{reviewCount}</div>
        </div>
      </div>
      <div class="stats shadow">
        <div class="stat py-3 px-5">
          <div class="stat-title text-xs">Fallidos</div>
          <div class="stat-value text-2xl text-error">{failedCount}</div>
        </div>
      </div>
    </div>

    <div class="flex justify-between items-center mb-4">
      <h2 class="text-xl font-semibold text-base-content">Cargas recientes</h2>
      <button class="btn btn-primary" on:click={startUpload}> Nueva carga </button>
    </div>

    {#if loading}
      <div class="flex justify-center py-12"><span class="loading loading-spinner loading-lg"></span></div>
    {:else if jobs.length === 0}
      <div class="text-center py-16 border border-dashed border-base-300 rounded-xl">
        <p class="text-base-content/60 text-lg mb-2">Todavía no hay documentos cargados</p>
        <p class="text-base-content/40 text-sm mb-4">Las nuevas fuentes documentales aparecerán aquí junto con su estado de procesamiento.</p>
        <button class="btn btn-primary btn-outline" on:click={startUpload}> Cargar primer documento </button>
      </div>
    {:else}
      <!-- Job list - desktop table -->
      <div class="hidden md:block overflow-x-auto">
        <table class="table table-zebra w-full">
          <thead>
            <tr>
              <th>Documento</th>
              <th>Idioma</th>
              <th>Estado</th>
              <th>Etapa</th>
              <th>Fecha</th>
            </tr>
          </thead>
          <tbody>
            {#each jobs as job}
              <tr>
                <td class="font-medium max-w-xs truncate">{job.title}</td>
                <td><span class="badge badge-sm">{job.language}</span></td>
                <td><span class="badge {STATUS_BADGES[job.status] || 'badge-ghost'}">{statusLabel(job.status)}</span></td>
                <td class="text-sm text-base-content/60">{statusLabel(job.current_stage || job.status)}</td>
                <td class="text-sm text-base-content/60">{formatDate(job.created_at)}</td>
              </tr>
            {/each}
          </tbody>
        </table>
      </div>
      <!-- Job list - mobile cards -->
      <div class="md:hidden space-y-3">
        {#each jobs as job}
          <div class="card bg-base-100 shadow-sm p-4">
            <div class="flex justify-between items-start mb-2">
              <h3 class="font-semibold text-sm truncate">{job.title}</h3>
              <span class="badge {STATUS_BADGES[job.status] || 'badge-ghost'} text-xs">{statusLabel(job.status)}</span>
            </div>
            <div class="text-xs text-base-content/60 flex justify-between">
              <span>{job.language}</span>
              <span>{formatDate(job.created_at)}</span>
            </div>
          </div>
        {/each}
      </div>
    {/if}

  {:else if view === "upload"}
    <div class="max-w-lg mx-auto">
      <h2 class="text-xl font-semibold mb-1">Nueva carga</h2>
      <p class="text-sm text-base-content/60 mb-6">Etapa 1 de 3 — Archivo</p>

      <!-- Upload drop zone -->
      {#if !upload}
        <div
          class="border-2 border-dashed border-base-300 rounded-xl p-12 text-center cursor-pointer hover:border-primary transition-colors"
          on:dragover={(e) => e.preventDefault()}
          on:drop={handleDrop}
          on:click={() => document.getElementById("cm-file-input")?.click()}
          role="button"
          tabindex="0"
          aria-label="Seleccioná una fuente documental"
          on:keypress={(e) => e.key === "Enter" && document.getElementById("cm-file-input")?.click()}
        >
          <input
            id="cm-file-input"
            type="file"
            accept=".pdf,application/pdf"
            class="hidden"
            on:change={handleFile}
            aria-hidden="true"
          />
          {#if uploading}
            <span class="loading loading-spinner loading-lg text-primary"></span>
            <p class="mt-3 text-base-content/60">Validando…</p>
          {:else}
            <div class="text-4xl mb-3 text-base-content/30">📄</div>
            <p class="text-lg font-medium text-base-content mb-1">Seleccioná una fuente documental</p>
            <p class="text-sm text-base-content/50">PDF de hasta {200} MB. El archivo será validado antes de iniciar su procesamiento.</p>
            <p class="text-xs text-base-content/40 mt-3">Arrastrá el archivo aquí o hacé clic para seleccionarlo</p>
          {/if}
        </div>
      {:else}
        <!-- File selected - card -->
        <div class="card bg-base-100 shadow-sm p-6 mb-6">
          <h3 class="font-semibold text-lg mb-2 truncate">{upload.filename}</h3>
          <div class="grid grid-cols-2 gap-2 text-sm mb-4">
            <div><span class="text-base-content/60">Tamaño:</span> {formatBytes(upload.size_bytes)}</div>
            <div><span class="text-base-content/60">Páginas:</span> {upload.page_count ?? "—"}</div>
            <div class="col-span-2"><span class="text-base-content/60">SHA-256:</span> <code class="text-xs">{upload.sha256.slice(0, 16)}…</code></div>
          </div>
          {#if upload.validation_status === "valid"}
            <div class="alert alert-success mb-4">
              <span>Archivo validado correctamente</span>
            </div>
          {/if}
          {#if upload.duplicate_status !== "new_document"}
            <div class="alert alert-warning mb-4">
              <span>Ya existe un documento con características similares. Verificá antes de continuar.</span>
            </div>
          {/if}
          {#if upload.warnings.length > 0}
            <div class="alert alert-warning mb-4">
              <ul class="list-disc ml-4 text-sm">
                {#each upload.warnings as w}<li>{w}</li>{/each}
              </ul>
            </div>
          {/if}

          <!-- Metadata form -->
          <div class="space-y-4 mt-4">
            <label class="form-control w-full">
              <div class="label"><span class="label-text">Título de la obra</span></div>
              <input type="text" class="input input-bordered w-full" bind:value={title} placeholder={upload.filename.replace(".pdf", "")} />
            </label>
            <label class="form-control w-full">
              <div class="label"><span class="label-text">Idioma principal</span></div>
              <select class="select select-bordered w-full" bind:value={language}>
                <option value="auto">Auto (detectar)</option>
                <option value="es">Español</option>
                <option value="en">Inglés</option>
                <option value="he">Hebreo</option>
                <option value="mixed">Mixto</option>
              </select>
            </label>
            <button class="btn btn-primary w-full" on:click={goToConfirm}> Continuar a confirmación </button>
            <button class="btn btn-ghost w-full" on:click={() => { upload = null; }}> Seleccionar otro archivo </button>
          </div>
        </div>
      {/if}

      {#if uploadError}
        <div class="alert alert-error mt-4"><span>{uploadError}</span></div>
      {/if}
      <button class="btn btn-ghost mt-4" on:click={() => { view = "list"; loadJobs(); }}>← Volver al gestor</button>
    </div>

  {:else if view === "confirm"}
    <div class="max-w-lg mx-auto">
      <h2 class="text-xl font-semibold mb-1">Confirmar procesamiento</h2>
      <p class="text-sm text-base-content/60 mb-6">Etapa 3 de 3 — Confirmación</p>

      {#if upload}
        <div class="card bg-base-100 shadow-sm p-6 mb-6">
          <h3 class="font-semibold text-lg mb-3">{title || upload.filename}</h3>
          <dl class="grid grid-cols-2 gap-y-2 text-sm">
            <dt class="text-base-content/60">Archivo</dt><dd class="truncate">{upload.filename}</dd>
            <dt class="text-base-content/60">Idioma</dt><dd>{language}</dd>
            <dt class="text-base-content/60">Páginas</dt><dd>{upload.page_count ?? "—"}</dd>
            <dt class="text-base-content/60">Tamaño</dt><dd>{formatBytes(upload.size_bytes)}</dd>
            <dt class="text-base-content/60 col-span-2">SHA-256</dt><dd class="col-span-2"><code class="text-xs">{upload.sha256.slice(0, 24)}…</code></dd>
          </dl>

          <div class="alert mt-4">
            <span>El documento será procesado y quedará como candidato para revisión.</span>
          </div>
          <div class="alert alert-warning mt-2">
            <span>Esta operación no publica ni aprueba el documento.</span>
          </div>

          <div class="flex gap-3 mt-6">
            <button class="btn btn-primary flex-1" on:click={startJob}> Iniciar procesamiento </button>
            <button class="btn btn-ghost" on:click={() => view = "upload"}> Volver </button>
          </div>
        </div>
      {/if}
    </div>

  {:else if view === "progress"}
    <div class="max-w-lg mx-auto">
      <h2 class="text-xl font-semibold mb-1">Procesando documento</h2>
      <p class="text-sm text-base-content/60 mb-6">{title || "Documento"}</p>

      <div class="card bg-base-100 shadow-sm p-6 mb-6">
        <!-- Progress bar -->
        <div class="mb-6">
          <div class="flex justify-between text-sm mb-1">
            <span>{statusLabel(jobStatus)}</span>
            <span>{Math.round(progressPercent)}%</span>
          </div>
          <progress class="progress progress-primary w-full" value={progressPercent} max="100"></progress>
        </div>

        <!-- Stages -->
        <div class="space-y-2">
          {#each Object.entries(stageStates) as [stage, state]}
            <div class="flex items-center gap-2 text-sm">
              {#if state === "done"}
                <span class="text-success">✓</span>
                <span class="text-base-content">{STAGE_LABELS[stage] || stage}</span>
              {:else if state === "active" || stage === jobStatus}
                <span class="loading loading-spinner loading-xs text-primary"></span>
                <span class="font-medium">{STAGE_LABELS[stage] || stage}</span>
              {:else if state === "failed"}
                <span class="text-error">✗</span>
                <span class="text-error">{STAGE_LABELS[stage] || stage}</span>
              {:else}
                <span class="text-base-content/20">○</span>
                <span class="text-base-content/40">{STAGE_LABELS[stage] || stage}</span>
              {/if}
            </div>
          {/each}
        </div>

        {#if jobError}
          <div class="alert alert-error mt-4"><span>{jobError}</span></div>
        {/if}

        <p class="text-xs text-base-content/40 mt-4">Podés salir de esta pantalla. El procesamiento continuará y quedará registrado en el historial.</p>
      </div>
    </div>

  {:else if view === "result"}
    <div class="max-w-lg mx-auto">
      {#if jobStatus === "completed"}
        <h2 class="text-xl font-semibold mb-1">Documento procesado</h2>
        <div class="alert alert-success my-4">
          <span>Candidato para revisión</span>
        </div>
      {:else if jobStatus === "completed_with_warnings"}
        <h2 class="text-xl font-semibold mb-1">Documento procesado con observaciones</h2>
        <div class="alert alert-warning my-4">
          <span>El documento quedó disponible para revisión, pero se detectaron aspectos que conviene verificar.</span>
        </div>
      {:else if jobStatus === "failed"}
        <h2 class="text-xl font-semibold mb-1">No se pudo completar el procesamiento</h2>
        <div class="alert alert-error my-4">
          <span>{jobError || "Error desconocido"}</span>
        </div>
      {/if}

      <div class="card bg-base-100 shadow-sm p-6 mb-6">
        {#if jobWarnings.length > 0}
          <div class="mb-4">
            <h3 class="font-semibold text-sm mb-1">Observaciones</h3>
            <ul class="list-disc ml-4 text-sm text-base-content/70">
              {#each jobWarnings as w}<li>{w}</li>{/each}
            </ul>
          </div>
        {/if}
        <div class="flex gap-3">
          <button class="btn btn-primary" on:click={() => { view = "list"; loadJobs(); }}> Volver al gestor </button>
          <button class="btn btn-ghost" on:click={() => { upload = null; title = ""; view = "upload"; }}> Nueva carga </button>
        </div>
      </div>
    </div>
  {/if}
</div>
