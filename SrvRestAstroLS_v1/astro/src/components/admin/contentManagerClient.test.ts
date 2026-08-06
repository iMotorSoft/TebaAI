import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import {
  normalizeUploadError,
  isTerminal,
  isCancellable,
  isRetryable,
  uploadFile,
  createJob,
  listJobs,
  getJob,
  retryJob,
  cancelJob,
  getDiagnostic,
  CONTENT_MANAGER_SCOPE,
  ContentManagerApiError,
} from "./contentManagerClient.ts";
import {
  ERROR_MESSAGES,
  STATUS_LABELS,
  warningMessage,
  editorialStageKey,
  contentDirection,
  formatBytes,
  formatDate,
  LANGUAGE_LABELS,
} from "./contentManagerLabels.ts";

// ── Client: error normalization ─────────────────────────────────────────

describe("normalizeUploadError", () => {
  it("maps backend size message to FILE_TOO_LARGE", () => {
    const err = normalizeUploadError("El archivo supera el tamaño permitido de 200 MB.");
    expect(err.code).toBe("FILE_TOO_LARGE");
    expect(err).toBeInstanceOf(ContentManagerApiError);
  });

  it("maps invalid signature to INVALID_PDF", () => {
    expect(normalizeUploadError("El archivo no es un PDF válido (firma inválida).").code).toBe("INVALID_PDF");
  });

  it("maps page limit to PAGE_LIMIT_EXCEEDED", () => {
    expect(normalizeUploadError("El PDF supera el límite de 2000 páginas (3000 detectadas).").code).toBe("PAGE_LIMIT_EXCEEDED");
  });

  it("maps encrypted to PDF_ENCRYPTED", () => {
    expect(normalizeUploadError("El PDF está protegido.").code).toBe("PDF_ENCRYPTED");
  });

  it("maps exact duplicate to EXACT_DUPLICATE", () => {
    expect(normalizeUploadError("El archivo es un duplicado exacto y no puede reingerirse.").code).toBe("EXACT_DUPLICATE");
  });

  it("maps reupload_required to REUPLOAD_REQUIRED", () => {
    expect(normalizeUploadError("reupload_required: el archivo temporal ya no está disponible.").code).toBe("REUPLOAD_REQUIRED");
  });

  it("maps not cancellable message", () => {
    expect(normalizeUploadError("No se puede cancelar un job en estado 'extracting'.").code).toBe("NOT_CANCELLABLE");
  });

  it("falls back to UNKNOWN", () => {
    expect(normalizeUploadError("algo raro").code).toBe("UNKNOWN");
  });
});

// ── Client: state helpers ───────────────────────────────────────────────

describe("stage helpers", () => {
  it("treats completed/failed/cancelled as terminal", () => {
    expect(isTerminal("completed")).toBe(true);
    expect(isTerminal("completed_with_warnings")).toBe(true);
    expect(isTerminal("failed")).toBe(true);
    expect(isTerminal("cancelled")).toBe(true);
    expect(isTerminal("queued")).toBe(false);
    expect(isTerminal("extracting")).toBe(false);
    expect(isTerminal(null)).toBe(false);
  });

  it("allows cancellation only before writes", () => {
    expect(isCancellable("uploaded")).toBe(true);
    expect(isCancellable("ready_to_ingest")).toBe(true);
    expect(isCancellable("queued")).toBe(true);
    expect(isCancellable("claimed")).toBe(false);
    expect(isCancellable("extracting")).toBe(false);
    expect(isCancellable("completed")).toBe(false);
  });

  it("allows retry only after failure or cancellation", () => {
    expect(isRetryable("failed")).toBe(true);
    expect(isRetryable("cancelled")).toBe(true);
    expect(isRetryable("completed")).toBe(false);
    expect(isRetryable("queued")).toBe(false);
  });
});

// ── Client: HTTP contract ───────────────────────────────────────────────

describe("client endpoints", () => {
  const originalFetch = globalThis.fetch;
  let fetches: Array<{ url: string; init: RequestInit }> = [];

  beforeEach(() => {
    fetches = [];
    vi.stubGlobal(
      "fetch",
      vi.fn(async (url: string | URL | Request, init?: RequestInit) => {
        fetches.push({ url: String(url), init: init ?? {} });
        return new Response(JSON.stringify({ ok: true }), {
          status: 200,
          headers: { "Content-Type": "application/json" },
        });
      }),
    );
  });

  afterEach(() => {
    globalThis.fetch = originalFetch;
    vi.unstubAllGlobals();
  });

  it("sends the scope as knowledge_scope_code", async () => {
    await listJobs();
    expect(fetches[0].url).toContain(`knowledge_scope_code=${CONTENT_MANAGER_SCOPE}`);
  });

  it("creates a job with test_candidate requested status", async () => {
    await createJob({
      upload_id: "u1",
      title: "Obra",
      language: "es",
      work_family: null,
      administrative_notes: null,
    });
    const init = fetches[0].init;
    const body = JSON.parse(String(init.body));
    expect(body.requested_status).toBe("test_candidate");
    expect(body.title).toBe("Obra");
    expect(body.knowledge_scope_code).toBe(CONTENT_MANAGER_SCOPE);
  });

  it("routes endpoints to the expected paths", async () => {
    await getJob("j1");
    expect(fetches[0].url).toContain("/admin/content/jobs/j1?");
    await retryJob("j1");
    expect(fetches[1].url).toContain("/admin/content/jobs/j1/retry?");
    await cancelJob("j1");
    expect(fetches[2].url).toContain("/admin/content/jobs/j1/cancel?");
    await getDiagnostic("j1");
    expect(fetches[3].url).toContain("/admin/content/jobs/j1/diagnostic?");
  });

  it("redirects to login on 401", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(async () => new Response(JSON.stringify({ detail: "unauthorized" }), { status: 401 })),
    );
    const assign = vi.fn();
    Object.defineProperty(window, "location", { value: { assign }, writable: true });
    await expect(listJobs()).rejects.toThrow("La sesión expiró");
    expect(assign).toHaveBeenCalledWith("/login");
  });

  it("normalizes a 400 upload detail", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(async () =>
        new Response(JSON.stringify({ detail: "El archivo supera el límite de 2000 páginas (5000 detectadas)." }), { status: 400 }),
      ),
    );
    await expect(uploadFile(new File(["x"], "a.pdf"))).rejects.toMatchObject({ code: "PAGE_LIMIT_EXCEEDED" });
  });
});

// ── Labels: editorial vocabulary ────────────────────────────────────────

describe("editorial labels", () => {
  it("exposes every visible status in Spanish", () => {
    expect(STATUS_LABELS.completed).toBe("Candidato para revisión");
    expect(STATUS_LABELS.completed_with_warnings).toBe("Con observaciones");
    expect(STATUS_LABELS.failed).toBe("Fallido");
    expect(STATUS_LABELS.cancelled).toBe("Cancelado");
    expect(STATUS_LABELS.queued).toBe("En procesamiento");
    expect(STATUS_LABELS.ready_to_ingest).toBe("Esperando confirmación");
  });

  it("maps every error code to a comprehensible message", () => {
    for (const [code, message] of Object.entries(ERROR_MESSAGES)) {
      expect(message.length).toBeGreaterThan(8);
      expect(/Código|INGESTION|PIPELINE/i.test(message)).toBe(false);
      expect(code).toBeTruthy();
    }
  });

  it("maps warning codes to editorial text before codes", () => {
    expect(warningMessage("empty_pages")).toBe("Algunas páginas no contienen texto detectable.");
    expect(warningMessage("EMPTY_PAGES")).toBe("Algunas páginas no contienen texto detectable.");
    expect(warningMessage("unknown_code_xyz")).toBeTruthy();
    expect(warningMessage("unknown_code_xyz")).not.toContain("unknown_code_xyz");
  });

  it("maps backend stages onto the seven visible stages", () => {
    expect(editorialStageKey("extracting")).toBe("extracting");
    expect(editorialStageKey("indexing")).toBe("embedding");
    expect(editorialStageKey("embedding")).toBe("embedding");
    expect(editorialStageKey("queued")).toBe("validating");
    expect(editorialStageKey("validating_result")).toBe("validating_result");
  });
});

// ── Labels: RTL / formatting ────────────────────────────────────────────

describe("RTL and formatting", () => {
  it("detects Hebrew titles as RTL", () => {
    const info = contentDirection("ליקוטי מוהר״ן");
    expect(info.direction).toBe("rtl");
    expect(info.lang).toBe("he");
  });

  it("keeps Spanish titles LTR", () => {
    expect(contentDirection("Interior Final").direction).toBe("ltr");
  });

  it("formats bytes and dates", () => {
    expect(formatBytes(512)).toBe("512 B");
    expect(formatBytes(2048)).toBe("2.0 KB");
    expect(formatBytes(5 * 1024 * 1024)).toBe("5.0 MB");
    const d = formatDate("2026-08-05T12:00:00Z");
    expect(d).toContain("2026");
    expect(formatDate(null)).toBe("");
  });

  it("covers all language options", () => {
    expect(LANGUAGE_LABELS.auto).toBe("Automático");
    expect(LANGUAGE_LABELS.he).toBe("Hebreo");
    expect(LANGUAGE_LABELS.mixed).toBe("Mixto");
    expect(LANGUAGE_LABELS.unknown).toBe("Desconocido");
  });
});
