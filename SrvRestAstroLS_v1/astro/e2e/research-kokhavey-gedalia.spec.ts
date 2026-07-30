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
  const analyzing = page.getByTestId("research-submit").locator("span").last();
  await page.getByTestId("research-submit").click();
  await expect(analyzing).toHaveText("Analyzing…");
  await expect(analyzing).toHaveAttribute("lang", "en");
  const response = await pending;
  expect(response.status()).toBe(200);
  const body = await response.json();
  await expect(page.getByTestId("research-result-heading")).toBeVisible({
    timeout: 120_000,
  });
  return body;
}

function expectCanonicalGedalia(body: any) {
  expect(body).toMatchObject({
    pipeline: "simple_rag",
    original_query: "Gedalia of Linitz",
    research_status: "complete",
    retrieval: {
      query_language: "en",
      query_shape: "short_proper_name",
      primary_match_type: "english_name_exact",
      matched_tokens: ["gedalia", "linitz"],
    },
  });
  const primary = body.hits.find((hit: { is_primary: boolean }) => hit.is_primary);
  expect(primary).toMatchObject({
    evidence_id: "ev-0f2b0ebedf5e0315",
    chunk_id: "91472546-4ffd-421c-9ec1-25d73d368352",
    document_id: "c7c10741-c324-4916-93a7-61070863e3f9",
    work_title: "Kokhavey Ohr",
    physical_file_name: "Kokhavey Ohr layout BH_PRINT-4.pdf",
    pdf_page: 21,
    match_kind: "english_name_exact",
    literal_match_kind: "exact_phrase",
  });
  expect(primary.quote).toContain("Gedalia of Linitz and other great Rabbis");
  expect(body.answer_markdown).toContain(primary.evidence_id);
}

test.describe("Kokhavey Ohr short proper-name DEV gate", () => {
  test.skip(!adminEmail || !adminPassword, "admin E2E credentials are required");

  test("admin recovers the exact canonical mention through the real confirmation flow", async ({ page }) => {
    test.setTimeout(180_000);
    await login(page, adminEmail, adminPassword);
    const body = await ask(page, "Gedalia of Linitz");
    expectCanonicalGedalia(body);
    await expect(page.locator('[data-research-status="complete"]')).toBeVisible();
    const sources = page.locator('aside[aria-label="Fuentes del turno"]');
    await expect(sources.getByText("Kokhavey Ohr", { exact: true }).first()).toBeVisible();
    await expect(sources.getByText("PDF p. 21", { exact: false }).first()).toBeVisible();
    await expect(sources.getByText("Coincidencia literal exacta", { exact: true })).toBeVisible();
    await clickVisibleButton(page, "Cerrar sesión");
    await expect(page).toHaveURL(/\/login\/?$/);
  });
});

test.describe("Kokhavey Ohr guest and mobile gate", () => {
  test.skip(!guestPassword, "guest E2E credentials are required");

  test("guest sees the same source on mobile and remains read-only", async ({ page }) => {
    test.setTimeout(180_000);
    await page.setViewportSize({ width: 390, height: 844 });
    await login(page, guestEmail, guestPassword);
    const body = await ask(page, "Gedalia of Linitz");
    expectCanonicalGedalia(body);
    await clickVisibleButton(page, "Fuentes");
    const sources = page.locator('aside[aria-label="Fuentes del turno"]');
    await expect(sources).toBeVisible();
    await expect(sources).toContainText("Kokhavey Ohr");
    await expect(sources).toContainText("PDF p. 21");
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
