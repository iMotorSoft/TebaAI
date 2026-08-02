import { expect, test } from "@playwright/test";
import path from "node:path";

const GUEST_EMAIL = process.env.TEBAAI_E2E_GUEST_EMAIL ?? "guest@tebaai.live";
const GUEST_PASSWORD = process.env.TEBAAI_E2E_GUEST_PASSWORD ?? "";
const SCREENSHOTS = path.resolve(
  import.meta.dirname,
  "../../../data/reports/breslov/2026-08-02-guest-research-access-e2e-recovery-dev/screenshots",
);
const endpoint = "/library/investigative-qa/v1";

/**
 * Guest flow follows the documented primary UX (ADR-006): the composer sends
 * the question directly and the workspace renders the grounded answer, the
 * evidence panel and the pages. No interpretation confirmation gate.
 */
async function loginGuest(page: import("@playwright/test").Page) {
  await page.goto("/login");
  await page.fill("#login-email", GUEST_EMAIL);
  await page.fill("#login-password", GUEST_PASSWORD);
  await page.getByRole("button", { name: "Ingresar" }).click();
  await expect(page).toHaveURL(/\/research\/?$/);
  // The "Verificando acceso…" state must terminate into the composer.
  await expect(page.getByTestId("research-question")).toBeVisible({ timeout: 20_000 });
}

async function ask(page: import("@playwright/test").Page, question: string) {
  const pending = page.waitForResponse(
    (response) => response.url().includes(endpoint)
      && response.request().method() === "POST"
      && !response.request().postDataJSON()?.phase,
  );
  await page.getByTestId("research-question").fill(question);
  await page.getByTestId("research-submit").click();
  // Working state is language-agnostic: the analyzing label follows the
  // detected query language ("Analizando…" / "Analyzing…").
  await expect(page.getByTestId("research-submit")).toHaveAttribute("aria-disabled", "true");
  const response = await pending;
  expect(response.status()).toBe(200);
  const body = await response.json();
  if (body.research_status === "no_evidence") {
    await expect(page.getByRole("status")).toContainText(
      "No se encontró evidencia suficiente",
      { timeout: 120_000 },
    );
  } else {
    await expect(page.getByTestId("research-result-heading")).toBeVisible({ timeout: 120_000 });
  }
  return body;
}

function primaryHit(body: Record<string, any>) {
  const hit = body.hits?.find((candidate: Record<string, any>) => candidate.is_primary);
  expect(hit, "expected the response to include a primary evidence hit").toBeTruthy();
  return hit;
}

test.describe("read-only research guest", () => {
  test.skip(!GUEST_PASSWORD, "TEBAAI_E2E_GUEST_PASSWORD not set");

  test("guest recovers footnote 35 and Salmos 16:1 with read-only evidence and a persisted session", async ({ page }) => {
    test.setTimeout(420_000);
    await loginGuest(page);
    await page.screenshot({ path: path.join(SCREENSHOTS, "research-guest-composer.png"), fullPage: true });

    // ── Footnote 35 (exact editorial evidence) ───────────────────────────
    const footnote = await ask(
      page,
      "El hombre se une a HaShem desde este mundo físico principalmente a través de la melodía y de la canción",
    );
    expect(footnote).toMatchObject({ pipeline: "simple_rag", original_query: expect.any(String) });
    expect(footnote.retrieval).toMatchObject({ primary_match_type: "footnote_literal_exact" });
    const primary = primaryHit(footnote);
    expect(primary).toMatchObject({
      work_title: "Likutey Halajot — Interior Final",
      physical_pdf_page: 56,
      printed_page: 38,
      source_layer: "footnote",
      footnote_marker: "35",
    });

    // Evidence panel shows the primary footnote evidence.
    const sources = page.locator('aside[aria-label="Fuentes del turno"]');
    await expect(sources).toContainText("EVIDENCIA PRINCIPAL");
    await expect(sources).toContainText("PDF p. 56 · Página impresa 38");
    await expect(sources).toContainText("Likutey Halajot — Interior Final");
    await expect(sources).toContainText("El hombre se une a HaShem");
    await page.screenshot({ path: path.join(SCREENSHOTS, "research-guest-footnote-35.png"), fullPage: true });

    // ── Salmos 16:1 → page 55 ────────────────────────────────────────────
    const salmos = await ask(page, "Salmos 16:1");
    const salmosPrimary = primaryHit(salmos);
    expect(salmos.retrieval).toMatchObject({ primary_match_type: "printed_reference_exact" });
    expect(salmosPrimary).toMatchObject({ physical_pdf_page: 55 });
    await expect(sources).toContainText("PDF p. 55");
    await page.screenshot({ path: path.join(SCREENSHOTS, "research-guest-salmos-16-1.png"), fullPage: true });

    // ── Read-only: no administrative surface ─────────────────────────────
    await expect(page.getByRole("button", { name: "Crear usuario" })).toHaveCount(0);
    await expect(page.getByText("Administración de usuarios")).toHaveCount(0);

    // ── Refresh keeps the session and the composer ───────────────────────
    await page.reload();
    await expect(page).toHaveURL(/\/research\/?$/);
    await expect(page.getByTestId("research-question")).toBeVisible({ timeout: 20_000 });
    await page.screenshot({ path: path.join(SCREENSHOTS, "research-guest-after-reload.png"), fullPage: true });
  });

  test("admin route redirects without rendering admin controls", async ({ page }) => {
    await loginGuest(page);
    await page.goto("/admin/users");
    await expect(page).toHaveURL(/\/research\/?$/);
    await expect(page.getByTestId("research-question")).toBeVisible();
    await expect(page.getByRole("button", { name: "Crear usuario" })).toHaveCount(0);
    await expect(page.getByText("Administración de usuarios")).toHaveCount(0);
    await page.screenshot({ path: path.join(SCREENSHOTS, "forbidden-admin-redirect.png"), fullPage: true });
  });

  test("logout revokes the browser session", async ({ page }) => {
    await loginGuest(page);
    await page.getByRole("button", { name: "Cerrar sesión" }).first().click();
    await expect(page).toHaveURL(/\/login\/?$/);
    await page.goto("/research");
    await expect(page).toHaveURL(/\/login\/?$/);
    await page.screenshot({ path: path.join(SCREENSHOTS, "logout.png"), fullPage: true });
  });
});
