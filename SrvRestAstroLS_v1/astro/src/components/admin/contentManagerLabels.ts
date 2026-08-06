/**
 * Content Manager V1 — editorial labels and status vocabulary.
 *
 * All user-visible strings for the Content Manager live here (single source
 * for i18n later). Technical identifiers never become the primary message;
 * codes are exposed only inside the collapsible technical diagnostic.
 */

import type {
  ContentManagerErrorCode,
  DuplicateClassification,
  IngestionStage,
  StageState,
} from "./contentManagerClient.ts";
import { detectLanguage, textDirection } from "../research/textDirection.ts";

// ── Editorial stage labels (the seven visible pipeline stages) ──────────

/** Ordered visible pipeline stages, editorial language. */
export const EDITORIAL_STAGES: ReadonlyArray<{ key: string; label: string }> = [
  { key: "validating", label: "Validando el archivo" },
  { key: "extracting", label: "Extrayendo las páginas" },
  { key: "normalizing", label: "Normalizando el contenido" },
  { key: "persisting_pages", label: "Organizando las secciones" },
  { key: "building_chunks", label: "Preparando la búsqueda" },
  { key: "embedding", label: "Generando el índice" },
  { key: "validating_result", label: "Verificando el resultado" },
];

/**
 * Map a backend stage onto its visible editorial stage key. `claimed` is the
 * worker hand-off point; `indexing` is the Milvus vector write that happens
 * inside the "Generando el índice" window.
 */
export function editorialStageKey(stage: IngestionStage | string | null | undefined): string {
  switch (stage) {
    case "uploaded":
    case "validating":
      return "validating";
    case "ready_to_ingest":
    case "queued":
    case "claimed":
      return "validating"; // queued before extraction: still "Validando el archivo" gate
    case "extracting":
      return "extracting";
    case "normalizing":
      return "normalizing";
    case "persisting_pages":
      return "persisting_pages";
    case "building_chunks":
      return "building_chunks";
    case "embedding":
    case "indexing":
      return "embedding";
    case "validating_result":
      return "validating_result";
    default:
      return "validating";
  }
}

// ── Visible status vocabulary ───────────────────────────────────────────

export const STATUS_LABELS: Record<string, string> = {
  uploaded: "Validando",
  validating: "Validando",
  validation_failed: "Validación fallida",
  ready_to_ingest: "Esperando confirmación",
  queued: "En procesamiento",
  claimed: "En procesamiento",
  extracting: "En procesamiento",
  normalizing: "En procesamiento",
  persisting_pages: "En procesamiento",
  building_chunks: "En procesamiento",
  embedding: "En procesamiento",
  indexing: "En procesamiento",
  validating_result: "En procesamiento",
  completed: "Candidato para revisión",
  completed_with_warnings: "Con observaciones",
  failed: "Fallido",
  cancelled: "Cancelado",
};

export const STATUS_TONE: Record<string, "neutral" | "active" | "review" | "warning" | "danger" | "muted"> = {
  uploaded: "neutral",
  validating: "active",
  validation_failed: "danger",
  ready_to_ingest: "neutral",
  queued: "active",
  claimed: "active",
  extracting: "active",
  normalizing: "active",
  persisting_pages: "active",
  building_chunks: "active",
  embedding: "active",
  indexing: "active",
  validating_result: "active",
  completed: "review",
  completed_with_warnings: "warning",
  failed: "danger",
  cancelled: "muted",
};

export const STAGE_STATE_LABELS: Record<StageState, string> = {
  pending: "Pendiente",
  active: "En curso",
  done: "Completada",
  failed: "Fallida",
  warning: "Con observaciones",
};

// ── Editorial messages per error code ───────────────────────────────────

export const ERROR_MESSAGES: Record<ContentManagerErrorCode, string> = {
  INVALID_PDF: "El archivo no es un PDF válido.",
  PDF_ENCRYPTED: "El PDF está protegido y no puede procesarse.",
  EXACT_DUPLICATE: "Este mismo archivo ya fue cargado.",
  FILE_TOO_LARGE: "El archivo supera el tamaño permitido.",
  PAGE_LIMIT_EXCEEDED: "El archivo supera el límite de páginas permitido.",
  NEEDS_PIPELINE_REVIEW: "El documento necesita una revisión técnica antes de procesarse.",
  REUPLOAD_REQUIRED: "El archivo original ya no está disponible. Volvé a cargarlo para intentar nuevamente.",
  NOT_CANCELLABLE: "El procesamiento ya comenzó y no puede cancelarse de forma segura.",
  RETRY_NOT_ELIGIBLE: "El documento no está en condiciones de reintentarse.",
  VALIDATION_FAILED: "El archivo no superó la validación.",
  UNKNOWN: "Ocurrió un error inesperado. Intentá nuevamente.",
};

// ── Editorial warnings (before technical codes) ─────────────────────────

/**
 * Map raw backend warning/error codes onto comprehensible editorial text.
 * Unknown codes fall back to a generic phrase — technical codes are never
 * shown as the primary message.
 */
export function warningMessage(code: string): string {
  switch (code) {
    case "empty_pages":
    case "EMPTY_PAGES":
      return "Algunas páginas no contienen texto detectable.";
    case "page_count_unknown":
      return "No se pudo verificar la cantidad exacta de páginas.";
    case "language_mismatch":
      return "Parte del contenido necesita revisión de idioma.";
    case "unicode_normalization":
      return "Se aplicaron ajustes de tipografía durante la normalización.";
    case "heading_ambiguity":
      return "Se detectaron secciones que requieren revisión.";
    case "no_printed_page":
      return "Algunas páginas no exponen numeración impresa.";
    case "duplicate_candidate":
      return "Se detectaron diferencias que requieren revisión.";
    case "reconciliation_warning":
      return "La verificación de consistencia detectó diferencias menores.";
    default:
      return "El documento presenta un detalle que conviene verificar.";
  }
}

// ── Formatting helpers ──────────────────────────────────────────────────

export function formatBytes(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

export function formatDate(iso: string | null | undefined): string {
  if (!iso) return "";
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return "";
  return d.toLocaleDateString("es-AR", {
    day: "2-digit",
    month: "short",
    year: "numeric",
  });
}

export function formatDateTime(iso: string | null | undefined): string {
  if (!iso) return "";
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return "";
  return d.toLocaleString("es-AR", {
    day: "2-digit",
    month: "short",
    year: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  });
}

export function formatDuration(seconds: number | null | undefined): string {
  if (seconds === null || seconds === undefined || Number.isNaN(seconds)) return "—";
  if (seconds < 60) return `${Math.round(seconds)} s`;
  const m = Math.floor(seconds / 60);
  const s = Math.round(seconds % 60);
  return `${m} min ${s} s`;
}

// ── RTL / Hebrew helpers ────────────────────────────────────────────────

export interface TextDirectionInfo {
  direction: "rtl" | "ltr";
  lang: string;
  isHebrew: boolean;
}

/** Direction metadata for a document title/filename, reusing textDirection. */
export function contentDirection(text: string): TextDirectionInfo {
  const language = detectLanguage(text);
  // `textDirection` may return "auto" for mixed content: native bidi
  // (unicode-bidi: plaintext) resolves it per-line, so the attribute stays ltr.
  const dir = textDirection(text);
  return {
    direction: dir === "rtl" ? "rtl" : "ltr",
    lang: language === "he" ? "he" : language === "ar" ? "ar" : "es",
    isHebrew: language === "he" || language === "mixed",
  };
}

export const LANGUAGE_LABELS: Record<string, string> = {
  auto: "Automático",
  es: "Español",
  en: "Inglés",
  he: "Hebreo",
  mixed: "Mixto",
  unknown: "Desconocido",
};

export const DUPLICATE_LABELS: Record<DuplicateClassification, string> = {
  new_document: "Nueva fuente documental",
  exact_duplicate: "Duplicado exacto",
  known_source_new_instance: "Fuente conocida, nueva instancia",
  possible_revised_edition: "Posible edición revisada",
};
