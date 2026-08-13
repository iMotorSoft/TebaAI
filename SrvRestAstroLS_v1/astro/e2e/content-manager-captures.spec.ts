import { test, expect, type Page } from "@playwright/test";
import path from "node:path";
import os from "node:os";
import fs from "node:fs";
import { fileURLToPath } from "node:url";
import {
  ADMIN_EMAIL,
  ADMIN_PASSWORD,
  loginAsAdmin,
  generateFixture,
  sha256OfFile,
  authorizeFixtureSha,
  E2E_SCOPE,
} from "./content-manager-helpers";
import { execFileSync } from "node:child_process";

/**
 * Content Manager — evidence captures.
 *
 * Saves screenshots of the premium states (empty/history/upload/result/
 * diagnostic) at 1440×900, 1024×768, 768×1024 and 390×844 into the report
 * directory. Mocked API fixtures keep this spec fast and side-effect free;
 * the real backend flow is covered by content-manager-premium.spec.ts.
 */

const SHOT_DIR = path.resolve(
  path.dirname(fileURLToPath(import.meta.url)),
  "../../../data/reports/breslov/2026-08-12-content-manager-ux-integration-v2-dev/screenshots",
);

const documentsFixture = {
  documents: [
    {
      document_id: "11111111-1111-4111-8111-111111111111",
      title: "Likutey Halajot — Interior Final",
      work_family: "Likutey Halajot",
      canonical_work: "Likutey Halajot",
      language: "es",
      page_count: 284,
      document_status: "test_candidate",
      operational_state: "needs_review",
      last_activity_at: "2026-08-05T12:00:00Z",
      has_warnings: false,
      latest_job_id: "aaaaaaaa-1111-4111-8111-111111111111",
      latest_job_status: "completed",
      latest_job_stage: "completed",
      filename: "likutey-halajot-interior-final.pdf",
      is_test_data: false,
    },
    {
      document_id: "22222222-2222-4222-8222-222222222222",
      title: "Likutei Moharan — Lesson 8",
      work_family: "Likutey Moharán",
      canonical_work: null,
      language: "he",
      page_count: 442,
      document_status: "ready",
      operational_state: "idle",
      last_activity_at: "2026-08-04T09:30:00Z",
      has_warnings: false,
      latest_job_id: "cccccccc-3333-4333-8333-333333333333",
      latest_job_status: "completed",
      latest_job_stage: "completed",
      filename: "likutei-moharan-lesson-8.pdf",
      is_test_data: false,
    },
    {
      document_id: "33333333-3333-4333-8333-333333333333",
      title: "Fuente con observaciones de idioma",
      work_family: null,
      canonical_work: null,
      language: "mixed",
      page_count: null,
      document_status: "ingestion_failed",
      operational_state: "failed",
      last_activity_at: "2026-08-03T15:45:00Z",
      has_warnings: true,
      latest_job_id: "eeeeeeee-5555-4555-8555-555555555555",
      latest_job_status: "failed",
      latest_job_stage: "failed",
      filename: "fuente-observaciones-idioma.pdf",
      is_test_data: false,
    },
  ],
  summary: {
    total_documents: 3, ready: 1, test_candidate: 1,
    processing: 0, with_warnings: 0, failed: 1,
    languages: { es: 1, he: 1, mixed: 1 },
  },
};

const emptyDocumentsFixture = {
  documents: [],
  summary: {
    total_documents: 0, ready: 0, test_candidate: 0,
    processing: 0, with_warnings: 0, failed: 0, languages: {},
  },
};

const uploadFixture = {
  upload_id: "12345678-1234-4234-8234-1234567890ab",
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

const terminalFixture = {
  job_id: "12345678-9999-4999-8999-1234567890ab",
  upload_id: "12345678-1234-4234-8234-1234567890ab",
  document_id: "87654321-8765-4876-8876-876543210fed",
  title: "Fuente documental E2E",
  language: "es",
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
  error_code: null,
  error_message: null,
  warning_codes: ["empty_pages"],
  attempt_number: 1,
  ingestion_profile: "auto",
  created_at: "2026-08-05T12:00:00Z",
  started_at: "2026-08-05T12:00:01Z",
  finished_at: "2026-08-05T12:00:30Z",
  worker_id: null,
  claimed_at: null,
  lease_expires_at: null,
  heartbeat_at: null,
  cleanup_status: null,
  recovery_status: null,
  pipeline_version: "content_page_first_v1",
  idempotency_key: null,
};

const failedFixture = {
  ...terminalFixture,
  status: "failed",
  error_code: "INGESTION_FAILED",
  error_message: "La etapa validating_result no pudo completarse.",
  warning_codes: [],
  progress: {
    ...terminalFixture.progress,
    current_stage: "failed",
    stage_display: "Fallido",
    stage_states: {
      ...terminalFixture.progress.stage_states,
      validating_result: "failed",
    },
  },
};

const diagnosticFixture = {
  document_id: "87654321-8765-4876-8876-876543210fed",
  job_id: "12345678-9999-4999-8999-1234567890ab",
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
  stage_timings: { extracting: 4.2, embedding: 12.1 },
  cleanup_result: null,
  technical_details: { reconciliation: "match" },
};

type DocumentsFixture = { documents: unknown[]; summary: Record<string, unknown> };

function mockApi(page: Page, documents: DocumentsFixture) {
  void page.route("**/admin/content/documents?*", async (route) => {
    await route.fulfill({ json: documents });
  });
  void page.route("**/admin/content/summary?*", async (route) => {
    await route.fulfill({ json: documents.summary });
  });
  void page.route("**/admin/content/jobs/*/diagnostic?*", async (route) => {
    await route.fulfill({ json: diagnosticFixture });
  });
  void page.route("**/admin/content/jobs?*", async (route) => {
    const method = route.request().method();
    if (method === "GET") {
      await route.fulfill({ json: { jobs: [] } });
    } else {
      await route.fulfill({ json: terminalFixture, status: 201 });
    }
  });
  void page.route("**/admin/content/jobs/*?*", async (route) => {
    if (route.request().url().includes("/diagnostic")) return;
    await route.fulfill({ json: terminalFixture });
  });
  void page.route("**/admin/content/uploads?*", async (route) => {
    await route.fulfill({ json: uploadFixture, status: 201 });
  });
}

const VIEWPORTS: Array<{ name: string; width: number; height: number }> = [
  { name: "desktop-1440", width: 1440, height: 900 },
  { name: "desktop-1024", width: 1024, height: 768 },
  { name: "tablet-768", width: 768, height: 1024 },
  { name: "mobile-390", width: 390, height: 844 },
];

test.describe("Content Manager evidence captures", () => {
  test.skip(!ADMIN_EMAIL || !ADMIN_PASSWORD, "credentials not set");

  test("captures history, empty, upload, result and diagnostic states", async ({ page }) => {
    fs.mkdirSync(SHOT_DIR, { recursive: true });
    await loginAsAdmin(page);

    for (const vp of VIEWPORTS) {
      await page.setViewportSize({ width: vp.width, height: vp.height });

      // Library (documents) — desktop table / mobile cards
      mockApi(page, documentsFixture);
      await page.goto("/admin/content");
      await expect(page.getByRole("heading", { name: "Biblioteca" })).toBeVisible({ timeout: 15_000 });
      await page.screenshot({ path: path.join(SHOT_DIR, `history-${vp.name}.png`), fullPage: true });

      // Empty state
      mockApi(page, emptyDocumentsFixture);
      await page.goto("/admin/content");
      await expect(page.getByText("Todavía no hay contenidos incorporados")).toBeVisible({ timeout: 15_000 });
      await page.screenshot({ path: path.join(SHOT_DIR, `empty-${vp.name}.png`), fullPage: true });
    }

    // File selected + valid (desktop)
    mockApi(page, documentsFixture);
    await page.setViewportSize({ width: 1440, height: 900 });
    await page.goto("/admin/content");
    await page.getByRole("button", { name: "＋ Nueva carga" }).click();
    await page.locator("#cm-file-input").setInputFiles({
      name: "fuente-documental-e2e.pdf",
      mimeType: "application/pdf",
      buffer: Buffer.from("%PDF-1.4 mock"),
    });
    await expect(page.getByText("Archivo válido")).toBeVisible({ timeout: 15_000 });
    await page.screenshot({ path: path.join(SHOT_DIR, "file-valid-1440.png"), fullPage: true });

    // Result with warnings (terminal)
    await page.getByRole("button", { name: "Continuar" }).click();
    await page.getByLabel("Título de la obra").fill("Fuente documental E2E");
    await page.getByRole("button", { name: "Continuar a confirmación" }).click();
    await page.getByRole("button", { name: "Iniciar procesamiento" }).click();
    await expect(page.getByRole("heading", { name: /Documento procesado/ })).toBeVisible({ timeout: 20_000 });
    await page.screenshot({ path: path.join(SHOT_DIR, "result-warnings-1440.png"), fullPage: true });

    // Diagnostic expanded
    await page.getByRole("button", { name: "Abrir diagnóstico" }).click();
    await expect(page.getByText("Detalle del documento")).toBeVisible({ timeout: 15_000 });
    await page.locator("details.cm-details summary").click();
    await expect(page.locator("details.cm-details")).toHaveAttribute("open", "");
    await page.screenshot({ path: path.join(SHOT_DIR, "diagnostic-expanded-1440.png"), fullPage: true });

    // Failed state via the job detail fixture
    void page.route("**/admin/content/jobs/*?*", async (route) => {
      if (route.request().url().includes("/diagnostic")) {
        await route.fulfill({ json: diagnosticFixture });
        return;
      }
      await route.fulfill({ json: failedFixture });
    });
    await page.goto("/admin/content");
    await page.getByRole("button", { name: "Abrir" }).first().click();
    await expect(page.getByText("Fallido").first()).toBeVisible({ timeout: 15_000 });
    await page.screenshot({ path: path.join(SHOT_DIR, "failed-detail-1440.png"), fullPage: true });

    // Keyboard focus evidence (desktop)
    await page.goto("/admin/content");
    await page.getByRole("button", { name: "＋ Nueva carga" }).click();
    await page.locator(".cm-dropzone").focus();
    await expect(page.locator(".cm-dropzone")).toBeFocused();
    await page.screenshot({ path: path.join(SHOT_DIR, "keyboard-focus-dropzone-1440.png"), fullPage: true });
  });
});
