import { expect, test, type Page } from "@playwright/test";

const adminEmail = process.env.TEBAAI_E2E_ADMIN_EMAIL ?? "";
const adminPassword = process.env.TEBAAI_E2E_ADMIN_PASSWORD ?? "";
const guestEmail = process.env.TEBAAI_E2E_GUEST_EMAIL ?? "guest@tebaai.live";
const guestPassword = process.env.TEBAAI_E2E_GUEST_PASSWORD ?? "";
const endpoint = "/library/investigative-qa/v1";

async function login(page: Page, email: string, password: string) {
  await page.goto("/login");
  await page.fill("#login-email", email);
  await page.fill("#login-password", password);
  await page.getByRole("button", { name: "Ingresar" }).click();
  await expect(page.getByTestId("research-question")).toBeVisible();
}

async function clickVisibleButton(page: Page, name: string) {
  const buttons = page.getByRole("button", { name, exact: true });
  for (let index = 0; index < await buttons.count(); index += 1) {
    if (await buttons.nth(index).isVisible()) {
      await buttons.nth(index).click();
      return;
    }
  }
  throw new Error(`No visible button: ${name}`);
}

async function ask(page: Page, question: string) {
  const pending = page.waitForResponse((response) =>
    response.url().includes(endpoint)
    && response.request().method() === "POST"
    && !response.request().postDataJSON()?.phase
  );
  await page.getByTestId("research-question").fill(question);
  await page.getByTestId("research-submit").click();
  await expect(page.getByTestId("research-submit")).toContainText("Analizando…");
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

function expectCanonicalHeading(body: any, expectedMatch = "structural_heading_exact") {
  expect(body).toMatchObject({
    pipeline: "simple_rag",
    original_query: expect.any(String),
    research_status: "complete",
    retrieval: {
      query_language: "es",
      query_shape: "structural_heading",
      primary_match_type: expectedMatch,
      matched_tokens: ["construyendo", "un", "mishkan"],
    },
    primary_evidence_ids: ["ev-bf5ac6e2fbf46812"],
  });
  const primary = body.hits.find((hit: { is_primary: boolean }) => hit.is_primary);
  expect(primary).toMatchObject({
    evidence_id: "ev-bf5ac6e2fbf46812",
    chunk_id: "91aba034-7a02-4520-aa1c-3f29be2741be",
    associated_chunk_id: "d0ae8b80-0947-4503-a45f-11e4b9c7d0ff",
    document_id: "47768aac-704e-4296-9649-53b9ea037096",
    work_title: "Likutey Halajot",
    physical_file_name: "LIKUTEY HALAJOT (Interior Final).pdf",
    physical_pdf_page: 51,
    printed_page: 33,
    section: "4. CONSTRUYENDO UN MISHKÁN",
    source_layer: "section_heading",
    literal_match_kind: expectedMatch,
    heading_original: "4 ■ CONSTRUYENDO UN MISHKÁN",
  });
  expect(primary.quote).toContain("El Rabí Natán concluye su explicación");
  expect(body.answer_markdown).toContain(primary.evidence_id);
  return primary;
}

test.describe("structural section heading literal DEV gate", () => {
  test.skip(!adminEmail || !adminPassword, "admin E2E credentials are required");

  test("admin recovers exact, accent-folded and negative heading lookups", async ({ page }) => {
    test.setTimeout(300_000);
    await login(page, adminEmail, adminPassword);

    expectCanonicalHeading(await ask(page, "CONSTRUYENDO UN MISHKÁN"));
    const sources = page.locator('aside[aria-label="Fuentes del turno"]');
    await expect(sources).toContainText("Coincidencia exacta con título de sección");
    await expect(sources).toContainText("PDF p. 51 · Página impresa 33 · 4. CONSTRUYENDO UN MISHKÁN");
    await expect(sources).toContainText("LIKUTEY HALAJOT (Interior Final).pdf");
    await expect(sources).toContainText("El Rabí Natán concluye su explicación");
    await expect(sources).toContainText("ev-bf5ac6e2fbf46812");

    expectCanonicalHeading(
      await ask(page, "Construyendo un Mishkan"),
      "structural_heading_accent_folded",
    );
    const negative = await ask(page, "CONSTRUYENDO UN TEMPLO INEXISTENTE");
    expect(negative).toMatchObject({
      pipeline: "simple_rag",
      research_status: "no_evidence",
      primary_evidence_ids: [],
    });
    expect(negative.hits).toEqual([]);

    await clickVisibleButton(page, "Cerrar sesión");
    await expect(page).toHaveURL(/\/login\/?$/);
  });
});

test.describe("structural heading guest mobile gate", () => {
  test.skip(!guestPassword, "guest E2E credentials are required");

  test("guest recovers the same evidence at 390x844 and remains read-only", async ({ page }) => {
    test.setTimeout(240_000);
    await page.setViewportSize({ width: 390, height: 844 });
    await login(page, guestEmail, guestPassword);
    expectCanonicalHeading(await ask(page, "CONSTRUYENDO UN MISHKÁN"));
    await clickVisibleButton(page, "Fuentes");
    const sources = page.locator('aside[aria-label="Fuentes del turno"]');
    await expect(sources).toBeVisible();
    await expect(sources).toContainText("Likutey Halajot");
    await expect(sources).toContainText("PDF p. 51");
    await expect(sources).toContainText("Página impresa 33");
    await expect(sources).toContainText("Coincidencia exacta con título de sección");
    const overflow = await page.evaluate(
      () => document.documentElement.scrollWidth - document.documentElement.clientWidth,
    );
    expect(overflow).toBeLessThanOrEqual(1);
    await page.goto("/admin/users");
    await expect(page).toHaveURL(/\/research\/?$/);
    await expect(page.getByTestId("research-question")).toBeVisible();
    await expect(page.getByRole("button", { name: "Crear usuario" })).toHaveCount(0);
    await clickVisibleButton(page, "Conversación");
    await clickVisibleButton(page, "Cerrar sesión");
    await expect(page).toHaveURL(/\/login\/?$/);
  });
});
