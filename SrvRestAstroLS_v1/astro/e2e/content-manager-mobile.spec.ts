import { test, expect } from "@playwright/test";
import { ADMIN_EMAIL, ADMIN_PASSWORD, loginAsAdmin } from "./content-manager-helpers";

/**
 * Content Manager — mobile 390×844.
 *
 * Uses typed API fixtures (no real backend writes): validates layout,
 * touch targets, no horizontal overflow, cards instead of a horizontal
 * table, and the full wizard flow operable at 390×844.
 */

const listJobsFixture = {
  jobs: [
    {
      job_id: "11111111-1111-4111-8111-111111111111",
      upload_id: "22222222-2222-4222-8222-222222222222",
      document_id: null,
      title: "Likutey Moharan — Interior Final",
      language: "es",
      status: "completed_with_warnings",
      current_stage: "completed_with_warnings",
      created_at: "2026-08-05T12:00:00Z",
      attempt_number: 1,
      filename: "likutey-moharan-interior-final.pdf",
      sha256_short: "a1b2c3d4…",
    },
    {
      job_id: "33333333-3333-4333-8333-333333333333",
      upload_id: "44444444-4444-4444-8444-444444444444",
      document_id: null,
      title: "Fuente con título hebreo ליקוטי מוהר״ן",
      language: "he",
      status: "completed",
      current_stage: "completed",
      created_at: "2026-08-04T09:30:00Z",
      attempt_number: 1,
      filename: "hebrew-source.pdf",
      sha256_short: "e5f6a7b8…",
    },
  ],
  summary: { completed: 1, completed_with_warnings: 1 },
};

const uploadFixture = {
  upload_id: "55555555-5555-4555-8555-555555555555",
  filename: "fuente-documental-e2e.pdf",
  size_bytes: 420000,
  sha256: "ab".repeat(32),
  mime_type: "application/pdf",
  page_count: 3,
  validation_status: "valid",
  duplicate_status: "new_document",
  existing_document: null,
  warnings: [],
  limits: { max_upload_bytes: 200 * 1024 * 1024, max_pdf_pages: 2000 },
};

const progressFixture = {
  job_id: "66666666-6666-4666-8666-666666666666",
  upload_id: "55555555-5555-4555-8555-555555555555",
  document_id: null,
  title: "Fuente documental E2E",
  language: "es",
  status: "extracting",
  progress: {
    current_stage: "extracting",
    progress_percent: 18,
    stage_display: "Extrayendo las páginas",
    is_terminal: false,
    stage_states: {
      validating: "done",
      ready_to_ingest: "done",
      queued: "done",
      claimed: "done",
      extracting: "active",
      normalizing: "pending",
      persisting_pages: "pending",
      building_chunks: "pending",
      embedding: "pending",
      indexing: "pending",
      validating_result: "pending",
    },
  },
  error_code: null,
  error_message: null,
  warning_codes: [],
  attempt_number: 1,
  ingestion_profile: "auto",
  created_at: "2026-08-05T12:00:00Z",
  started_at: "2026-08-05T12:00:01Z",
  finished_at: null,
  worker_id: null,
  claimed_at: null,
  lease_expires_at: null,
  heartbeat_at: null,
  cleanup_status: null,
  recovery_status: null,
  pipeline_version: "content_page_first_v1",
  idempotency_key: null,
};

const terminalFixture = {
  ...progressFixture,
  status: "completed_with_warnings",
  progress: {
    current_stage: "completed_with_warnings",
    progress_percent: 100,
    stage_display: "Documento procesado con observaciones",
    is_terminal: true,
    stage_states: {
      validating: "done",
      ready_to_ingest: "done",
      queued: "done",
      claimed: "done",
      extracting: "done",
      normalizing: "done",
      persisting_pages: "done",
      building_chunks: "done",
      embedding: "done",
      indexing: "done",
      validating_result: "done",
    },
  },
  warning_codes: ["empty_pages"],
  finished_at: "2026-08-05T12:00:30Z",
};

const diagnosticFixture = {
  document_id: "77777777-7777-4777-8777-777777777777",
  job_id: "66666666-6666-4666-8666-666666666666",
  attempt_number: 1,
  job_status: "completed_with_warnings",
  document_status: "test_candidate",
  pipeline_version: "content_page_first_v1",
  scope: "breslov_e2e",
  collection_code: "tebaai_content_manager_e2e_v1",
  pdf_pages: 3,
  canonical_pages: 3,
  textual_pages: 2,
  empty_pages: 1,
  headings: 1,
  footnotes: 1,
  printed_references: 1,
  chunks: 2,
  embeddings: 2,
  pg_embedding_count: 2,
  milvus_entity_count: 2,
  pg_missing: 0,
  milvus_missing: 0,
  milvus_orphan: 0,
  duplicates: 0,
  duration_seconds: 29,
  page_integrity: "match",
  warnings: ["physical_empty_pages_detected", "empty_pages_preserved"],
  errors: [],
  stage_timings: { extracting: 4.2 },
  cleanup_result: null,
  technical_details: {},
};

function mockApi(page: import("@playwright/test").Page) {
  void page.route("**/admin/content/jobs?*", async (route) => {
    const method = route.request().method();
    if (method === "GET") {
      await route.fulfill({ json: listJobsFixture });
    } else if (method === "POST") {
      await route.fulfill({ json: progressFixture, status: 201 });
    }
  });
  void page.route("**/admin/content/jobs/66666666-6666-4666-8666-666666666666?*", async (route) => {
    await route.fulfill({ json: terminalFixture });
  });
  void page.route("**/admin/content/jobs/66666666-6666-4666-8666-666666666666/diagnostic?*", async (route) => {
    await route.fulfill({ json: diagnosticFixture });
  });
  void page.route("**/admin/content/uploads?*", async (route) => {
    await route.fulfill({ json: uploadFixture, status: 201 });
  });
}

test.describe("Content Manager mobile 390×844", () => {
  test.skip(!ADMIN_EMAIL || !ADMIN_PASSWORD, "credentials not set");

  test("list renders cards, no horizontal overflow", async ({ page }) => {
    await page.setViewportSize({ width: 390, height: 844 });
    await loginAsAdmin(page);
    mockApi(page);
    await page.goto("/admin/content");

    // Mobile cards visible; desktop table hidden
    await expect(page.locator(".cm-mobile-cards")).toBeVisible();
    await expect(page.locator(".cm-table-wrap")).toBeHidden();
    await expect(page.locator(".cm-mobile-card").first()).toContainText("Likutey Moharan");

    // No horizontal overflow
    const overflow = await page.evaluate(
      () => document.documentElement.scrollWidth - document.documentElement.clientWidth,
    );
    expect(overflow).toBeLessThanOrEqual(1);

    // Touch targets ≥ 40px for primary actions
    const btnHeight = await page
      .getByRole("button", { name: "＋ Nueva carga" })
      .evaluate((el) => el.getBoundingClientRect().height);
    expect(btnHeight).toBeGreaterThanOrEqual(40);
  });

  test("wizard flow is fully operable at 390×844", async ({ page }) => {
    await page.setViewportSize({ width: 390, height: 844 });
    await loginAsAdmin(page);
    mockApi(page);
    await page.goto("/admin/content");

    await page.getByRole("button", { name: "＋ Nueva carga" }).click();
    await expect(page.getByText("Seleccioná una fuente documental")).toBeVisible();

    // File selection via hidden native input (accessible to keyboard/AT)
    await page.locator("#cm-file-input").setInputFiles({
      name: "fuente-documental-e2e.pdf",
      mimeType: "application/pdf",
      buffer: Buffer.from("%PDF-1.4 mock"),
    });
    await expect(page.locator(".cm-file-name")).toContainText("fuente-documental-e2e.pdf");
    await expect(page.getByText("Archivo válido")).toBeVisible();

    await page.getByRole("button", { name: "Continuar" }).click();
    await page.getByLabel("Título de la obra").fill("Fuente documental E2E");
    await page.getByLabel("Idioma principal").selectOption("es");
    await page.getByRole("button", { name: "Continuar a confirmación" }).click();
    await expect(page.getByText("El documento será procesado y quedará como candidato para revisión.")).toBeVisible();
    await page.getByRole("button", { name: "Iniciar procesamiento" }).click();

    // Processing: mocked job may reach terminal on the first poll (state
    // transitions are validated by the real-backend spec).
    await expect(page.getByText("Extrayendo las páginas").first()).toBeVisible({ timeout: 5_000 }).catch(() => {});
    await expect(page.getByRole("heading", { name: /Documento procesado/ })).toBeVisible({ timeout: 20_000 });

    // Diagnostic
    await page.getByRole("button", { name: "Abrir diagnóstico" }).click();
    await expect(page.getByText("Detalle del documento")).toBeVisible({ timeout: 15_000 });
    await page.locator("details.cm-details summary").click();
    await expect(page.getByText("Páginas PDF")).toBeVisible();

    // No horizontal overflow at any point
    const overflow = await page.evaluate(
      () => document.documentElement.scrollWidth - document.documentElement.clientWidth,
    );
    expect(overflow).toBeLessThanOrEqual(1);

    await page.getByRole("button", { name: "Cerrar sesión" }).click();
  });
});
