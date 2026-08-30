/**
 * Content Manager V1 — typed API client.
 *
 * Single typed layer over the backend /admin/content/* endpoints. All
 * components go through this module: no scattered `fetch` calls, no state
 * derived from visible text. Auth comes from the shared authClient storage.
 *
 * The knowledge scope is a deployment-time constant (PUBLIC_CONTENT_MANAGER_SCOPE),
 * never a UI selector: DEV E2E runs set it to `breslov_e2e`; the default is
 * the backend contract `breslov_primary`. The backend worker still requires
 * explicit primary-ingestion enablement; the browser cannot enable it.
 */

import { API_BASE_URL } from "../global.js";
import { getStoredAccessToken } from "../auth/authClient.ts";

const BASE = API_BASE_URL.replace(/\/+$/, "");

/** Deployment-time scope. Default matches the backend CreateJobRequest. */
export const CONTENT_MANAGER_SCOPE: string =
  (import.meta.env.PUBLIC_CONTENT_MANAGER_SCOPE as string | undefined) || "breslov_primary";

/** Default backend upload cap (200 MB) used for pre-upload copy. */
export const DEFAULT_MAX_UPLOAD_MB = 200;

// ── Upload contract ─────────────────────────────────────────────────────

export type UploadValidationStatus = "pending" | "valid" | "invalid";

export type DuplicateClassification =
  | "new_document"
  | "exact_duplicate"
  | "known_source_new_instance"
  | "possible_revised_edition";

export interface UploadLimits {
  max_upload_bytes: number;
  max_pdf_pages: number;
}

export interface ExistingDocumentInfo {
  document_id: string;
  title: string;
  status: string;
  created_at: string | null;
  source_sha256_short: string | null;
}

export interface UploadResponse {
  upload_id: string;
  filename: string;
  size_bytes: number;
  sha256: string;
  mime_type: string;
  page_count: number | null;
  validation_status: UploadValidationStatus;
  duplicate_status: DuplicateClassification;
  existing_document: ExistingDocumentInfo | null;
  warnings: string[];
  limits: UploadLimits;
}

/**
 * Editorial error codes surfaced by the console. The backend communicates
 * validation failures as HTTP 400 `detail` strings; the client normalizes
 * them into these typed codes so the UI never branches on raw text.
 */
export type ContentManagerErrorCode =
  | "INVALID_PDF"
  | "PDF_ENCRYPTED"
  | "EXACT_DUPLICATE"
  | "FILE_TOO_LARGE"
  | "PAGE_LIMIT_EXCEEDED"
  | "NEEDS_PIPELINE_REVIEW"
  | "REUPLOAD_REQUIRED"
  | "NOT_CANCELLABLE"
  | "RETRY_NOT_ELIGIBLE"
  | "VALIDATION_FAILED"
  | "UNKNOWN";

// ── Ingestion job contract ──────────────────────────────────────────────

export type IngestionStage =
  | "uploaded"
  | "validating"
  | "validation_failed"
  | "ready_to_ingest"
  | "queued"
  | "claimed"
  | "extracting"
  | "normalizing"
  | "persisting_pages"
  | "building_chunks"
  | "embedding"
  | "indexing"
  | "validating_result"
  | "completed"
  | "completed_with_warnings"
  | "failed"
  | "cancelled";

export type StageState = "pending" | "active" | "done" | "failed" | "warning";

export interface JobProgress {
  current_stage: IngestionStage;
  progress_percent: number;
  stage_display: string | null;
  is_terminal: boolean;
  stage_states: Record<string, StageState>;
}

export interface JobResponse {
  job_id: string;
  upload_id: string;
  document_id: string | null;
  title: string;
  language: string;
  status: IngestionStage;
  progress: JobProgress | null;
  error_code: string | null;
  error_message: string | null;
  warning_codes: string[];
  attempt_number: number;
  ingestion_profile: "auto" | "needs_pipeline_review";
  created_at: string | null;
  started_at: string | null;
  finished_at: string | null;
  worker_id: string | null;
  claimed_at: string | null;
  lease_expires_at: string | null;
  heartbeat_at: string | null;
  cleanup_status: string | null;
  recovery_status: string | null;
  pipeline_version: string | null;
  idempotency_key: string | null;
}

export interface JobListItem {
  job_id: string;
  upload_id: string;
  document_id: string | null;
  title: string;
  language: string;
  status: IngestionStage;
  current_stage: IngestionStage | null;
  created_at: string | null;
  attempt_number: number;
  filename: string | null;
  sha256_short: string | null;
}

export interface JobListResponse {
  jobs: JobListItem[];
  summary: Record<string, number>;
}

// ── Diagnostic contract ─────────────────────────────────────────────────

export interface IngestionDiagnostic {
  document_id: string | null;
  job_id: string;
  attempt_number: number;
  job_status: string | null;
  document_status: string | null;
  pipeline_version: string | null;
  scope: string | null;
  collection_code: string | null;
  pdf_pages: number | null;
  canonical_pages: number | null;
  textual_pages: number | null;
  empty_pages: number | null;
  headings: number | null;
  footnotes: number | null;
  printed_references: number | null;
  chunks: number | null;
  embeddings: number | null;
  pg_embedding_count: number | null;
  milvus_entity_count: number | null;
  pg_missing: number | null;
  milvus_missing: number | null;
  milvus_orphan: number | null;
  duplicates: number | null;
  duration_seconds: number | null;
  page_integrity: string | null;
  warnings: string[];
  errors: string[];
  stage_timings: Record<string, number>;
  cleanup_result: string | null;
  technical_details: Record<string, unknown>;
}

export interface PublishResponse {
  document_id: string;
  job_id: string;
  status: "ready";
  published_at: string;
  chunks: number;
  embeddings: number;
  vectors: number;
}

export interface CreateJobInput {
  upload_id: string;
  title: string;
  language: string;
  work_family?: string | null;
  administrative_notes?: string | null;
}

// ── Errors ──────────────────────────────────────────────────────────────

export class ContentManagerApiError extends Error {
  readonly code: ContentManagerErrorCode;
  readonly status: number;

  constructor(message: string, code: ContentManagerErrorCode, status: number) {
    super(message);
    this.name = "ContentManagerApiError";
    this.code = code;
    this.status = status;
  }
}

const SIZE_RE = /supera el tamaño permitido de (\d+)/;
const PAGE_RE = /supera el límite de (\d+) páginas/;

/** Map backend HTTP 400 detail messages onto typed editorial codes. */
export function normalizeUploadError(detail: string, status = 400): ContentManagerApiError {
  if (detail.startsWith("reupload_required")) {
    return new ContentManagerApiError(detail, "REUPLOAD_REQUIRED", status);
  }
  if (/duplicado exacto/.test(detail)) {
    return new ContentManagerApiError(detail, "EXACT_DUPLICATE", status);
  }
  if (/protegido|encrypted|encrypt/i.test(detail)) {
    return new ContentManagerApiError(detail, "PDF_ENCRYPTED", status);
  }
  if (SIZE_RE.test(detail)) {
    return new ContentManagerApiError(detail, "FILE_TOO_LARGE", status);
  }
  if (PAGE_RE.test(detail)) {
    return new ContentManagerApiError(detail, "PAGE_LIMIT_EXCEEDED", status);
  }
  if (/no es un PDF válido|firma inválida/.test(detail)) {
    return new ContentManagerApiError(detail, "INVALID_PDF", status);
  }
  if (/revisión técnica|needs_pipeline_review|revision_tecnica/i.test(detail)) {
    return new ContentManagerApiError(detail, "NEEDS_PIPELINE_REVIEW", status);
  }
  if (/no se puede cancelar/i.test(detail)) {
    return new ContentManagerApiError(detail, "NOT_CANCELLABLE", status);
  }
  if (/reintentar/i.test(detail)) {
    return new ContentManagerApiError(detail, "RETRY_NOT_ELIGIBLE", status);
  }
  if (/no superó la validación|validation/i.test(detail)) {
    return new ContentManagerApiError(detail, "VALIDATION_FAILED", status);
  }
  return new ContentManagerApiError(detail, "UNKNOWN", status);
}

// ── HTTP plumbing ───────────────────────────────────────────────────────

async function api<T>(path: string, options: RequestInit = {}): Promise<T> {
  const token = getStoredAccessToken();
  const headers: Record<string, string> = {};
  if (token) headers.Authorization = `Bearer ${token}`;
  const isForm = options.body instanceof FormData;
  if (!isForm && options.body !== undefined) headers["Content-Type"] = "application/json";

  let res: Response;
  try {
    res = await fetch(`${BASE}${path}`, { ...options, headers });
  } catch {
    throw new ContentManagerApiError(
      "No se pudo conectar con el servicio. Verificá tu conexión e intentá de nuevo.",
      "UNKNOWN",
      0,
    );
  }

  if (res.status === 401) {
    window.location.assign("/login");
    throw new ContentManagerApiError("La sesión expiró.", "UNKNOWN", 401);
  }
  if (res.status === 403) {
    throw new ContentManagerApiError("No tenés permiso para realizar esta operación.", "UNKNOWN", 403);
  }
  if (!res.ok) {
    const body = (await res.json().catch(() => ({}))) as { detail?: unknown };
    const detail = typeof body.detail === "string" ? body.detail : `Error ${res.status}`;
    throw normalizeUploadError(detail, res.status);
  }
  return (await res.json()) as T;
}

function scopeQuery(): string {
  return `knowledge_scope_code=${encodeURIComponent(CONTENT_MANAGER_SCOPE)}`;
}

// ── Public API ──────────────────────────────────────────────────────────

export function uploadFile(file: File): Promise<UploadResponse> {
  const fd = new FormData();
  fd.append("file", file);
  return api<UploadResponse>(`/admin/content/uploads?${scopeQuery()}`, {
    method: "POST",
    body: fd,
  });
}

export function createJob(input: CreateJobInput): Promise<JobResponse> {
  return api<JobResponse>(`/admin/content/jobs?${scopeQuery()}`, {
    method: "POST",
    body: JSON.stringify({
      upload_id: input.upload_id,
      knowledge_scope_code: CONTENT_MANAGER_SCOPE,
      title: input.title,
      language: input.language,
      work_family: input.work_family || null,
      administrative_notes: input.administrative_notes || null,
      requested_status: "test_candidate",
    }),
  });
}

export function listJobs(): Promise<JobListResponse> {
  return api<JobListResponse>(`/admin/content/jobs?${scopeQuery()}`);
}

export function getJob(jobId: string): Promise<JobResponse> {
  return api<JobResponse>(`/admin/content/jobs/${jobId}?${scopeQuery()}`);
}

export function retryJob(jobId: string): Promise<JobResponse> {
  return api<JobResponse>(`/admin/content/jobs/${jobId}/retry?${scopeQuery()}`, {
    method: "POST",
  });
}

export function cancelJob(jobId: string): Promise<JobResponse> {
  return api<JobResponse>(`/admin/content/jobs/${jobId}/cancel?${scopeQuery()}`, {
    method: "POST",
  });
}

export function getDiagnostic(jobId: string): Promise<IngestionDiagnostic> {
  return api<IngestionDiagnostic>(`/admin/content/jobs/${jobId}/diagnostic?${scopeQuery()}`);
}

export function publishJob(jobId: string): Promise<PublishResponse> {
  return api<PublishResponse>(`/admin/content/jobs/${jobId}/publish?${scopeQuery()}`, {
    method: "POST",
  });
}

// ── Terminal-state helpers ──────────────────────────────────────────────

const TERMINAL_STAGES = new Set<IngestionStage>([
  "completed",
  "completed_with_warnings",
  "failed",
  "cancelled",
]);

export function isTerminal(stage: IngestionStage | null | undefined): boolean {
  return !!stage && TERMINAL_STAGES.has(stage);
}

/** Stages from which cancellation is safe (before any pipeline write). */
const CANCELLABLE_STAGES = new Set<IngestionStage>([
  "uploaded",
  "ready_to_ingest",
  "queued",
]);

export function isCancellable(stage: IngestionStage | null | undefined): boolean {
  return !!stage && CANCELLABLE_STAGES.has(stage);
}

export function isRetryable(stage: IngestionStage | null | undefined): boolean {
  return stage === "failed" || stage === "cancelled";
}

// ── Document-Centric Administrative Views ─────────────────────────────────

export interface ContentSummary {
  total_documents: number;
  ready: number;
  test_candidate: number;
  processing: number;
  with_warnings: number;
  failed: number;
  languages: Record<string, number>;
}

export interface DocumentListItem {
  document_id: string | null;
  title: string;
  work_family: string | null;
  canonical_work: string | null;
  language: string;
  page_count: number | null;
  document_status: string | null;
  operational_state: "processing" | "idle" | "needs_review" | "failed" | "cancelled";
  last_activity_at: string | null;
  has_warnings: boolean;
  latest_job_id: string | null;
  latest_job_status: string | null;
  latest_job_stage: string | null;
  filename: string | null;
  is_test_data: boolean;
}

export interface DocumentListResponse {
  documents: DocumentListItem[];
  summary: ContentSummary;
}

export function getContentSummary(includeTestData = false): Promise<ContentSummary> {
  const qs = `${scopeQuery()}&include_test_data=${includeTestData}`;
  return api<ContentSummary>(`/admin/content/summary?${qs}`);
}

export function listContentDocuments(
  options: {
    includeTestData?: boolean;
    status?: string;
    language?: string;
    workFamily?: string;
    search?: string;
    limit?: number;
    offset?: number;
  } = {},
): Promise<DocumentListResponse> {
  const params = new URLSearchParams({ [scopeQueryParam()]: scopeQueryValue() });
  if (options.includeTestData) params.set("include_test_data", "true");
  if (options.status) params.set("status", options.status);
  if (options.language) params.set("language", options.language);
  if (options.workFamily) params.set("work_family", options.workFamily);
  if (options.search) params.set("search", options.search);
  if (options.limit) params.set("limit", String(options.limit));
  if (options.offset) params.set("offset", String(options.offset));
  return api<DocumentListResponse>(`/admin/content/documents?${params.toString()}`);
}

function scopeQueryParam(): string {
  return "knowledge_scope_code";
}

function scopeQueryValue(): string {
  return CONTENT_MANAGER_SCOPE;
}
