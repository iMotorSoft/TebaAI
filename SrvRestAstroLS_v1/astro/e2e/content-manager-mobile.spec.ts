import { test, expect, type Page } from "@playwright/test";
import { ADMIN_EMAIL, ADMIN_PASSWORD, loginAsAdmin } from "./content-manager-helpers";

/**
 * Content Manager — mobile 390×844.
 *
 * Uses typed API fixtures (no real backend writes): validates layout,
 * touch targets, no horizontal overflow, cards instead of a horizontal
 * table, and the full wizard flow operable at 390×844.
 */

const documentsFixture = {
  documents: [
    {
      document_id: "11111111-1111-4111-8111-111111111111",
      title: "Likutey Moharan — Interior Final",
      work_family: "Likutey Moharán",
      canonical_work: null,
      language: "es",
      page_count: 284,
      document_status: "test_candidate",
      operational_state: "needs_review",
      last_activity_at: "2026-08-05T12:00:00Z",
      has_warnings: true,
      latest_job_id: "11111111-1111-4111-8111-111111111111",
      latest_job_status: "completed_with_warnings",
      latest_job_stage: "completed_with_warnings",
      filename: "likutey-moharan-interior-final.pdf",
      is_test_data: false,
    },
    {
      document_id: "33333333-3333-4333-8333-333333333333",
      title: "Fuente con título hebreo ליקוטי מוהר״ן",
      work_family: null,
      canonical_work: null,
      language: "he",
      page_count: null,
      document_status: "ready",
      operational_state: "idle",
      last_activity_at: "2026-08-04T09:30:00Z",
      has_warnings: false,
      latest_job_id: "33333333-3333-4333-8333-333333333333",
      latest_job_status: "completed",
      latest_job_stage: "completed",
      filename: "hebrew-source.pdf",
      is_test_data: false,
    },
  ],
  summary: {
    total_documents: 2, ready: 1, test_candidate: 1,
    processing: 0, with_warnings: 1, failed: 0,
    languages: { es: 1, he: 1 },
  },
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

function mockApi(page: Page) {
  void page.route("**/admin/content/documents?*", async (route) => {
    await route.fulfill({ json: documentsFixture });
  });
  void page.route("**/admin/content/summary?*", async (route) => {
    await route.fulfill({ json: documentsFixture.summary });
  });
  void page.route("**/admin/content/jobs?*", async (route) => {
    if (route.request().method() === "POST") {
      await route.fulfill({ json: progressFixture, status: 201 });
    } else {
      await route.fulfill({ json: { jobs: [] } });
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
