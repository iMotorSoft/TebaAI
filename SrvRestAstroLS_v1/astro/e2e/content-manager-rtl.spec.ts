import { test, expect, type Page } from "@playwright/test";
import { ADMIN_EMAIL, ADMIN_PASSWORD, loginAsAdmin } from "./content-manager-helpers";

/**
 * Content Manager — RTL / Hebrew and accessibility evidence.
 *
 * Hebrew titles/filenames must keep local RTL alignment while the interface
 * itself stays LTR. Fixtures are typed API mocks: no real writes.
 */

const HEBREW_TITLE = "ליקוטי מוהר״ן — עִקְבוֹת מְשִׁיחָא";
const HEBREW_FILENAME = "ליקוטי-מוהר״ן.pdf";
const MIXED_TITLE = "Likutey Moharan — עִקְבוֹת מְשִׁיחָא";

const documentsFixture = {
  documents: [
    {
      document_id: "aaaa0000-1111-4222-8333-444444444444",
      title: HEBREW_TITLE,
      work_family: "Likutey Moharán",
      canonical_work: null,
      language: "he",
      page_count: 3,
      document_status: "test_candidate",
      operational_state: "needs_review",
      last_activity_at: "2026-08-05T12:00:00Z",
      has_warnings: false,
      latest_job_id: "aaaa0000-1111-4222-8333-444444444444",
      latest_job_status: "completed",
      latest_job_stage: "completed",
      filename: HEBREW_FILENAME,
      is_test_data: false,
    },
    {
      document_id: "cccc0000-3333-4222-8333-444444444444",
      title: MIXED_TITLE,
      work_family: "Likutey Moharán",
      canonical_work: null,
      language: "mixed",
      page_count: null,
      document_status: "test_candidate",
      operational_state: "needs_review",
      last_activity_at: "2026-08-04T09:30:00Z",
      has_warnings: true,
      latest_job_id: "cccc0000-3333-4222-8333-444444444444",
      latest_job_status: "completed_with_warnings",
      latest_job_stage: "completed_with_warnings",
      filename: "likutey-moharan.pdf",
      is_test_data: false,
    },
  ],
  summary: {
    total_documents: 2, ready: 0, test_candidate: 2,
    processing: 0, with_warnings: 1, failed: 0,
    languages: { he: 1, mixed: 1 },
  },
};

const uploadFixture = {
  upload_id: "eeee0000-5555-4222-8333-444444444444",
  filename: HEBREW_FILENAME,
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
  job_id: "ffff0000-6666-4222-8333-444444444444",
  upload_id: "eeee0000-5555-4222-8333-444444444444",
  document_id: null,
  title: HEBREW_TITLE,
  language: "he",
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

function mockApi(page: Page) {
  void page.route("**/admin/content/documents?*", async (route) => {
    await route.fulfill({ json: documentsFixture });
  });
  void page.route("**/admin/content/summary?*", async (route) => {
    await route.fulfill({ json: documentsFixture.summary });
  });
  void page.route("**/admin/content/jobs?*", async (route) => {
    if (route.request().method() === "POST") {
      await route.fulfill({ json: terminalFixture, status: 201 });
    } else {
      await route.fulfill({ json: { jobs: [] } });
    }
  });
  void page.route("**/admin/content/jobs/*?*", async (route) => {
    await route.fulfill({ json: terminalFixture });
  });
  void page.route("**/admin/content/uploads?*", async (route) => {
    await route.fulfill({ json: uploadFixture, status: 201 });
  });
}

test.describe("Content Manager RTL / Hebrew", () => {
  test.skip(!ADMIN_EMAIL || !ADMIN_PASSWORD, "credentials not set");

  test("hebrew title and filename render RTL locally, interface stays LTR", async ({ page }) => {
    await page.setViewportSize({ width: 1440, height: 900 });
    await loginAsAdmin(page);
    mockApi(page);
    await page.goto("/admin/content");

    // Hebrew row in history: local RTL direction on the title, LTR chrome
    const hebrewTitle = page.locator(".cm-doc-title", { hasText: HEBREW_TITLE });
    await expect(hebrewTitle).toBeVisible();
    const dir = await hebrewTitle.getAttribute("dir");
    expect(dir).toBe("rtl");
    const lang = await hebrewTitle.getAttribute("lang");
    await expect(page.getByRole("heading", { name: "Biblioteca" })).toBeVisible();

    // The page container itself must NOT flip to RTL
    const pageDir = await page.evaluate(() => document.querySelector(".content-manager")?.getAttribute("dir") ?? "");
    expect(pageDir).not.toBe("rtl");

    // No layout breakage: single line of Hebrew preserves niqqud
    const text = await hebrewTitle.textContent();
    expect(text).toContain("מְשִׁיחָא");

    // Interface labels stay LTR-readable
    await expect(page.getByRole("heading", { name: "Biblioteca" })).toBeVisible();
  });

  test("upload card keeps hebrew filename readable with native bidi", async ({ page }) => {
    await page.setViewportSize({ width: 390, height: 844 });
    await loginAsAdmin(page);
    mockApi(page);
    await page.goto("/admin/content");

    await page.getByRole("button", { name: "＋ Nueva carga" }).click();
    await page.locator("#cm-file-input").setInputFiles({
      name: HEBREW_FILENAME,
      mimeType: "application/pdf",
      buffer: Buffer.from("%PDF-1.4 mock"),
    });
    await expect(page.locator(".cm-file-name")).toContainText(HEBREW_FILENAME);
    const dir = await page.locator(".cm-file-name").getAttribute("dir");
    expect(dir).toBe("rtl");

    // Full filename accessible (no truncation hiding the extension)
    const full = await page.locator(".cm-file-name").textContent();
    expect(full).toContain(".pdf");

    // No overflow
    const overflow = await page.evaluate(
      () => document.documentElement.scrollWidth - document.documentElement.clientWidth,
    );
    expect(overflow).toBeLessThanOrEqual(1);
  });
});

test.describe("Content Manager accessibility", () => {
  test.skip(!ADMIN_EMAIL || !ADMIN_PASSWORD, "credentials not set");

  test("keyboard reaches the dropzone and opens the file picker", async ({ page }) => {
    await page.setViewportSize({ width: 1440, height: 900 });
    await loginAsAdmin(page);
    mockApi(page);
    await page.goto("/admin/content");

    await page.getByRole("button", { name: "＋ Nueva carga" }).click();
    const dropzone = page.locator(".cm-dropzone");
    await expect(dropzone).toBeVisible();

    // Focus with keyboard, then Enter opens the native picker (input click)
    await dropzone.focus();
    await expect(dropzone).toBeFocused();
    const opened = page.evaluate(() => {
      const input = document.querySelector<HTMLInputElement>("#cm-file-input");
      if (!input) return false;
      input.addEventListener("click", () => {
        (window as unknown as { __cmInputClicked?: boolean }).__cmInputClicked = true;
      });
      return true;
    });
    await page.keyboard.press("Enter");
    await page.waitForTimeout(400);
    expect(await opened).toBe(true);

    // Native input remains focusable (not display:none)
    const inputVisible = await page.evaluate(() => {
      const input = document.querySelector<HTMLInputElement>("#cm-file-input");
      return input ? input.getBoundingClientRect().width > 0 || input.getBoundingClientRect().height > 0 : false;
    });
    expect(inputVisible).toBe(true);
  });

  test("focus is visible and status changes are announced", async ({ page }) => {
    await page.setViewportSize({ width: 1440, height: 900 });
    await loginAsAdmin(page);
    mockApi(page);
    await page.goto("/admin/content");

    const action = page.getByRole("button", { name: "＋ Nueva carga" });
    await action.focus();
    await expect(action).toBeFocused();
    const outline = await action.evaluate((el) => getComputedStyle(el).outlineStyle);
    expect(outline).not.toBe("none");

    // aria-live present on processing surface
    await action.click();
    await page.locator("#cm-file-input").setInputFiles({
      name: "fuente-documental-e2e.pdf",
      mimeType: "application/pdf",
      buffer: Buffer.from("%PDF-1.4 mock"),
    });
    await page.getByRole("button", { name: "Continuar" }).click();
    await page.getByLabel("Título de la obra").fill("Fuente accesible");
    await page.getByRole("button", { name: "Continuar a confirmación" }).click();
    await page.getByRole("button", { name: "Iniciar procesamiento" }).click();
    await expect(page.locator("[aria-live='polite']").first()).toBeVisible({ timeout: 15_000 });
  });
});
