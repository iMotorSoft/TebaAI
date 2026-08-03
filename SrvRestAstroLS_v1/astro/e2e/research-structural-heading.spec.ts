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

interface ResearchHit {
  is_primary?: boolean;
  work_title?: string;
  physical_file_name?: string;
  physical_pdf_page?: number | null;
  printed_page?: number | null;
  section?: string;
  source_layer?: string;
  literal_match_kind?: string;
  heading_original?: string;
  quote?: string;
  evidence_id?: string;
  hit_id?: string;
}

interface ResearchPayload {
  pipeline?: string;
  original_query?: string;
  research_status?: string;
  answer_markdown?: string;
  primary_evidence_ids?: string[];
  hits?: ResearchHit[];
  retrieval?: {
    query_language?: string;
    query_shape?: string;
    primary_match_type?: string | null;
    matched_tokens?: string[];
  };
}

function expectCanonicalHeading(body: ResearchPayload, expected: {
  pdfPage: number;
  printedPage: number;
  section: string;
  tokens: string[];
  headingOriginal: string;
  quotePattern: RegExp;
}) {
  expect(body).toMatchObject({
    pipeline: "simple_rag",
    original_query: expect.any(String),
    research_status: expect.stringMatching(/^(complete|partial|degraded)$/),
    retrieval: {
      query_language: "es",
      query_shape: "structural_heading",
      primary_match_type: expect.stringMatching(
        /^structural_heading_(exact|normalized|accent_folded)$/,
      ),
      matched_tokens: expected.tokens,
    },
  });
  const primary = body.hits?.find((hit) => hit.is_primary);
  expect(primary, "expected a primary evidence hit").toBeTruthy();
  expect(primary).toMatchObject({
    work_title: expect.stringMatching(/Likutey Halajot/),
    physical_file_name: "LIKUTEY HALAJOT (Interior Final).pdf",
    physical_pdf_page: expected.pdfPage,
    printed_page: expected.printedPage,
    section: expect.stringContaining(expected.section),
    source_layer: "section_heading",
    literal_match_kind: expect.stringMatching(
      /^structural_heading_(exact|normalized|accent_folded)$/,
    ),
    heading_original: expect.stringContaining(expected.headingOriginal),
  });
  expect(primary?.quote).toMatch(expected.quotePattern);
  expect(body.answer_markdown).toContain(primary?.evidence_id);
  return primary;
}

const MISHKAN = {
  pdfPage: 51,
  printedPage: 33,
  section: "CONSTRUYENDO UN MISHKÁN",
  tokens: ["construyendo", "un", "mishkan"],
  headingOriginal: "4 ■ CONSTRUYENDO UN MISHKÁN",
  quotePattern: /El Rabí Natán concluye su explicación/,
};

const BONDAD = {
  pdfPage: 53,
  printedPage: 35,
  section: "INCLINADO HACIA LA BONDAD",
  tokens: ["inclinado", "hacia", "la", "bondad"],
  headingOriginal: "5 ■ INCLINADO HACIA LA BONDAD",
  quotePattern: /De la misma manera/,
};

const MELODIAS = {
  pdfPage: 56,
  printedPage: 38,
  section: "MELODÍAS Y PLEGARIAS",
  tokens: ["melodias", "y", "plegarias"],
  headingOriginal: "6 ■ MELODÍAS Y PLEGARIAS",
  quotePattern: /El Rabí Natán expandirá ahora/,
};

test.describe("structural section heading literal DEV gate", () => {
  test.skip(!adminEmail || !adminPassword, "admin E2E credentials are required");

  test("admin recovers exact, accent-folded and negative heading lookups", async ({ page }) => {
    test.setTimeout(600_000);
    await login(page, adminEmail, adminPassword);

    const mishkan = expectCanonicalHeading(
      await ask(page, "CONSTRUYENDO UN MISHKÁN"),
      MISHKAN,
    ) ?? null;
    const sources = page.locator('aside[aria-label="Fuentes del turno"]');
    await expect(sources).toContainText("Coincidencia exacta con título de sección");
    await expect(sources).toContainText(/PDF p\. 51 · Página impresa 33 · 4\. CONSTRUYENDO UN MISHKÁN/);
    await expect(sources).toContainText("LIKUTEY HALAJOT (Interior Final).pdf");
    await expect(sources).toContainText("El Rabí Natán concluye su explicación");
    await expect(sources).toContainText(mishkan?.evidence_id ?? "");

    expectCanonicalHeading(await ask(page, "Construyendo un Mishkan"), MISHKAN);
    expectCanonicalHeading(await ask(page, "INCLINADO HACIA LA BONDAD"), BONDAD);
    expectCanonicalHeading(await ask(page, "MELODÍAS Y PLEGARIAS"), MELODIAS);
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
    expectCanonicalHeading(await ask(page, "CONSTRUYENDO UN MISHKÁN"), MISHKAN);
    await clickVisibleButton(page, "Fuentes");
    const sources = page.locator('aside[aria-label="Fuentes del turno"]');
    await expect(sources).toBeVisible();
    await expect(sources).toContainText("Likutey Halajot");
    await expect(sources).toContainText(/PDF p\. 51/);
    await expect(sources).toContainText(/Página impresa 33/);
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
