import { test, expect, type Page } from "@playwright/test";
import path from "path";

const BACKEND = "http://127.0.0.1:7008";
const FRONTEND = "http://127.0.0.1:3008";
const ADMIN_EMAIL = process.env.TEBAAI_E2E_ADMIN_EMAIL ?? "";
const ADMIN_PASSWORD = process.env.TEBAAI_E2E_ADMIN_PASSWORD ?? "";
const SCREENSHOTS = path.resolve("test-results", "analyzing-state");

/** Mock response that passes normalizeResearchResponse */
function mockResponse(overrides: Record<string, unknown> = {}) {
  return {
    status: "ok",
    research_status: "complete",
    original_query: "test",
    summary: "Respuesta simulada para pruebas",
    answer_text: "Answer text",
    answer_markdown: "# Test\nsimulado",
    conversation: { conversation_id: null, turn_id: null },
    works_consulted: ["kitzur"],
    hits: [],
    claims: [],
    relations: [],
    primary_evidence_ids: [],
    evidence_counts: { primary: 0, contextual: 0, additional_literal: 0 },
    evidence_matrix: [],
    cross_corpus_matrix: [],
    warnings: [],
    not_found: [],
    execution: { duration_ms: 50 },
    ...overrides,
  };
}

async function login(page: Page) {
  await page.goto(`${FRONTEND}/login`);
  await page.fill("#login-email", ADMIN_EMAIL);
  await page.fill("#login-password", ADMIN_PASSWORD);
  await page.getByRole("button", { name: "Ingresar" }).click();
  await expect(page.getByTestId("research-question")).toBeVisible({ timeout: 10000 });
}

test.describe("research analyzing state", () => {
  test.beforeAll(async () => {
    const response = await fetch(`${BACKEND}/health`);
    expect(response.status).toBe(200);
  });

  test.beforeEach(async ({ page }) => {
    await login(page);
  });

  test("immediate feedback on submit — Spanish query", async ({ page }) => {
    await page.route("**/library/investigative-qa/v1", async (route) => {
      await new Promise((resolve) => setTimeout(resolve, 2000));
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify(mockResponse({ original_query: "alegría" })),
      });
    });

    await page.getByTestId("research-question").fill("alegría");
    await page.getByTestId("research-submit").click();

    // Immediate visual feedback
    await expect(page.getByTestId("research-submit")).toBeDisabled();
    await expect(page.getByTestId("research-submit")).toHaveAttribute("aria-disabled", "true");
    await expect(page.getByTestId("research-submit")).toContainText(/Analizando/i);

    // Status indicator with role="status"
    const status = page.getByRole("status");
    await expect(status).toBeVisible();
    await expect(status).toContainText(/Buscando fuentes/i);
  });

  test("blocks double submission — 1 request for 10 rapid clicks", async ({ page }) => {
    let requestCount = 0;
    await page.route("**/library/investigative-qa/v1", (route) => {
      requestCount++;
      return route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify(mockResponse()),
      });
    });

    await page.getByTestId("research-question").fill("alegría");
    await page.getByTestId("research-submit").click();

    // Wait for analyzing state
    await expect(page.getByTestId("research-submit")).toBeDisabled({ timeout: 3000 });

    // The button is disabled → clicks are safely ignored
    for (let i = 0; i < 9; i++) {
      await page.getByTestId("research-submit").click({ timeout: 50 }).catch(() => {});
    }

    // Wait for response heading (it appears as markdown h1 "Test")
    await expect(page.getByTestId("research-result-heading")).toBeVisible({ timeout: 10000 });

    // Exactly 1 request
    expect(requestCount).toBe(1);

    // Fill the input to test the button is re-enabled
    await page.getByTestId("research-question").fill("siguiente");
    await expect(page.getByTestId("research-submit")).not.toBeDisabled();
  });

  test("error preserves question and allows retry", async ({ page }) => {
    // First submission returns 500
    await page.route("**/library/investigative-qa/v1", (route) => {
      return route.fulfill({ status: 500, body: "Server error" });
    });

    await page.getByTestId("research-question").fill("alegría");
    await page.getByTestId("research-submit").click();

    // Error → isWorking should be false; fill input to test button re-enable
    const textarea = page.getByTestId("research-question");
    await expect(textarea).not.toHaveAttribute("readonly", { timeout: 15000 });
    await textarea.fill("reintentar");
    await expect(page.getByTestId("research-submit")).not.toBeDisabled();

    // Retry with success
    await page.unroute("**/library/investigative-qa/v1");
    await page.route("**/library/investigative-qa/v1", (route) => {
      return route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify(mockResponse({
          original_query: "alegría",
          summary: "Retry exitoso",
        })),
      });
    });

    await page.getByTestId("research-submit").click();
    await expect(page.getByText("Retry exitoso")).toBeVisible({ timeout: 10000 });
  });

  test("fast response has no leftover working state", async ({ page }) => {
    await page.route("**/library/investigative-qa/v1", (route) => {
      return route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify(mockResponse({
          summary: "Respuesta ultrarrápida",
        })),
      });
    });

    await page.getByTestId("research-question").fill("alegría");
    await page.getByTestId("research-submit").click();

    // Response appears
    await expect(page.getByText("Respuesta ultrarrápida")).toBeVisible({ timeout: 10000 });

    // No analyzing state visible
    const btn = page.getByTestId("research-submit");
    await expect(btn).not.toHaveClass(/analyzing/);

    // Fill input to check button is re-enabled
    await page.getByTestId("research-question").fill("siguiente pregunta");
    await expect(btn).not.toBeDisabled();

    // No status indicator
    await expect(page.getByRole("status")).not.toBeVisible();

    // Textarea editable
    const textarea = page.getByTestId("research-question");
    await expect(textarea).not.toHaveAttribute("readonly");
    await textarea.fill("nueva consulta");
    await expect(textarea).toHaveValue("nueva consulta");
  });

  test("slow response shows progressive messages (English)", async ({ page }) => {
    // "tristeza" → detectLanguage returns "en" (no Spanish diacritics)
    await page.route("**/library/investigative-qa/v1", async (route) => {
      await new Promise((resolve) => setTimeout(resolve, 12000));
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify(mockResponse({
          original_query: "tristeza",
          summary: "Respuesta tras 12s",
        })),
      });
    });

    await page.getByTestId("research-question").fill("tristeza");
    await page.getByTestId("research-submit").click();

    // Initial status (English because "tristeza" has no ñ/¿/diacritics)
    await expect(page.getByRole("status")).toContainText(/Searching the sources/i, { timeout: 2000 });

    // After ~4s: verifying
    await expect(page.getByRole("status")).toContainText(/Verifying the retrieved sources/i, { timeout: 10000 });

    // After ~9s: organizing
    await expect(page.getByRole("status")).toContainText(/Organizing the research/i, { timeout: 15000 });

    // Response
    await expect(page.getByText("Respuesta tras 12s")).toBeVisible({ timeout: 20000 });

    // Fill input → button re-enabled
    await page.getByTestId("research-question").fill("continuar");
    await expect(page.getByTestId("research-submit")).not.toBeDisabled();
    await expect(page.getByRole("status")).not.toBeVisible();
  });

  test("Hebrew RTL query shows correct direction", async ({ page }) => {
    await page.route("**/library/investigative-qa/v1", async (route) => {
      await new Promise((resolve) => setTimeout(resolve, 1500));
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify(mockResponse({
          original_query: "אתה מחפש איפה נמצא מושג העקרב.",
          summary: "נמצאו מקורות על עקרב",
        })),
      });
    });

    const textarea = page.getByTestId("research-question");
    await textarea.fill("אתה מחפש איפה נמצא מושג העקרב.");
    await expect(textarea).toHaveAttribute("dir", "rtl");

    await page.getByTestId("research-submit").click();

    // Button shows Hebrew "מנתח…"
    await expect(page.getByTestId("research-submit")).toContainText(/מנתח/, { timeout: 3000 });

    // Status in Hebrew
    await expect(page.getByRole("status")).toContainText(/מחפש מקורות/, { timeout: 3000 });

    // Response
    await expect(page.getByText("נמצאו מקורות על עקרב")).toBeVisible({ timeout: 10000 });
  });

  test("mobile viewport 390×844 — no overflow, button visible", async ({ page }) => {
    await page.setViewportSize({ width: 390, height: 844 });

    await page.route("**/library/investigative-qa/v1", async (route) => {
      await new Promise((resolve) => setTimeout(resolve, 2000));
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify(mockResponse({ summary: "Respuesta móvil exitosa" })),
      });
    });

    await page.getByTestId("research-question").fill("alegría");

    // No overflow before submit
    const beforeOverflow = await page.evaluate(() => {
      const el = document.querySelector(".research");
      return el ? el.scrollWidth > el.clientWidth : false;
    });
    expect(beforeOverflow).toBe(false);

    await page.getByTestId("research-submit").click();

    // Button visible and analyzing
    await expect(page.getByTestId("research-submit")).toBeVisible();
    await expect(page.getByTestId("research-submit")).toContainText(/Analizando/i);
    await expect(page.getByTestId("research-submit")).toBeDisabled();

    // Status visible
    await expect(page.getByRole("status")).toBeVisible();
    await expect(page.getByRole("status")).toContainText(/Buscando fuentes/i);

    // No overflow during analyzing
    const duringOverflow = await page.evaluate(() => {
      const el = document.querySelector(".research");
      return el ? el.scrollWidth > el.clientWidth : false;
    });
    expect(duringOverflow).toBe(false);

    await page.screenshot({ path: path.join(SCREENSHOTS, "mobile-analyzing.png"), fullPage: true });

    // Response
    await expect(page.getByText("Respuesta móvil exitosa")).toBeVisible({ timeout: 10000 });

    // Fill input → button re-enabled
    await page.getByTestId("research-question").fill("siguiente");
    await expect(page.getByTestId("research-submit")).not.toBeDisabled();
  });

  test("Enter key submits and shows analyzing state", async ({ page }) => {
    await page.route("**/library/investigative-qa/v1", async (route) => {
      await new Promise((resolve) => setTimeout(resolve, 1000));
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify(mockResponse({ summary: "Respuesta con Enter" })),
      });
    });

    const composer = page.getByTestId("research-question");
    await composer.fill("alegría");
    await composer.press("Enter");

    // Analyzing state
    await expect(page.getByTestId("research-submit")).toBeDisabled();
    await expect(page.getByTestId("research-submit")).toContainText(/Analizando/i);

    // Response
    await expect(page.getByText("Respuesta con Enter")).toBeVisible({ timeout: 10000 });
  });
});
