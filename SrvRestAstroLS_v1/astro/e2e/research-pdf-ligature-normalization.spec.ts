import { expect, test, type Page } from "@playwright/test";

const adminEmail = process.env.TEBAAI_E2E_ADMIN_EMAIL ?? "";
const adminPassword = process.env.TEBAAI_E2E_ADMIN_PASSWORD ?? "";
const guestEmail = process.env.TEBAAI_E2E_GUEST_EMAIL ?? "";
const guestPassword = process.env.TEBAAI_E2E_GUEST_PASSWORD ?? "";
const endpoint = "/library/investigative-qa/v1";

const NOTE36 = "Birur hace referencia a la extracción y refinamiento de las chispas";
const NOTE35 = "El hombre se une a HaShem desde este mundo físico principalmente a través de la melodía y de la canción";

async function login(page: Page, email: string, password: string) {
  await page.goto("/login");
  await page.fill("#login-email", email);
  await page.fill("#login-password", password);
  await page.getByRole("button", { name: "Ingresar" }).click();
  await expect(page.getByTestId("research-question")).toBeVisible();
}

async function clickVisible(page: Page, name: string) {
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
  const response = await pending;
  expect(response.status()).toBe(200);
  const body = await response.json();
  if (body.research_status === "no_evidence") {
    await expect(page.getByRole("status")).toContainText("No se encontró evidencia suficiente", { timeout: 120_000 });
  } else {
    await expect(page.getByTestId("research-result-heading")).toBeVisible({ timeout: 120_000 });
  }
  return body;
}

function primary(body: any) {
  return body.hits?.filter((hit: any) => hit.is_primary) ?? [];
}

test.describe("pdf ligature literal normalization admin", () => {
  test.skip(!adminEmail || !adminPassword, "admin E2E credentials are required");

  test("admin recovers note 36 with literal quote preserving the ligature", async ({ page }) => {
    test.setTimeout(900_000);
    await login(page, adminEmail, adminPassword);

    // 1. normal query for note 36
    const note36 = await ask(page, NOTE36);
    const p36 = primary(note36)[0];
    expect(p36).toMatchObject({
      work_title: "Likutey Halajot — Interior Final",
      physical_file_name: "LIKUTEY HALAJOT (Interior Final).pdf",
      physical_pdf_page: 56,
      printed_page: 38,
      footnote_number: 36,
      literal_match_kind: "footnote_literal_exact",
      source_layer: "footnote",
    });

    // 2. open the evidence panel and verify the original quote keeps the ligature
    const evidenceButton = page.locator('button[data-evidence-id="' + p36.evidence_id + '"]').first();
    await expect(evidenceButton).toBeVisible();
    await evidenceButton.click();
    const quote = page.locator('article[data-evidence-id="' + p36.evidence_id + '"] blockquote').first();
    await expect(quote).toContainText("reﬁ namiento");
    await expect(quote).toContainText("Inﬁ nito");
    await expect(quote).toContainText("36 Birur");

    // 3. note 35 regression
    const note35 = await ask(page, NOTE35);
    expect(primary(note35)[0]).toMatchObject({
      physical_pdf_page: 56,
      footnote_number: 35,
      literal_match_kind: "footnote_literal_exact",
      source_layer: "footnote",
    });

    // 4. printed reference
    const salmos = await ask(page, "Salmos 16:1");
    expect(primary(salmos)[0]).toMatchObject({
      physical_pdf_page: 55,
      printed_page: 37,
      literal_match_kind: "printed_reference_exact",
    });

    // 5. heading
    const heading = await ask(page, "MELODÍAS Y PLEGARIAS");
    expect(primary(heading)[0]).toMatchObject({
      physical_pdf_page: 56,
      literal_match_kind: "structural_heading_exact",
    });

    // 6. negative does not become literal
    const negative = await ask(page, "frase fabricada que nunca aparece en el corpus xyzzy");
    const negativePrimary = primary(negative)[0];
    expect(
      negative.research_status === "no_evidence"
      || !negativePrimary
      || !String(negativePrimary.literal_match_kind ?? "").endsWith("exact")
    ).toBe(true);

    // 7. refresh + logout
    await page.reload();
    await expect(page.getByTestId("research-question")).toBeVisible();
    await clickVisible(page, "Cerrar sesión");
    await expect(page).toHaveURL(/\/login\/?$/);
  });
});

test.describe("pdf ligature literal normalization guest", () => {
  test.skip(!guestEmail || !guestPassword, "guest E2E credentials are required");

  test("guest sees note 36 primary and original quote, remains read-only", async ({ page }) => {
    test.setTimeout(480_000);
    await login(page, guestEmail, guestPassword);
    const body = await ask(page, "refinamiento");
    const p36 = primary(body)[0];
    expect(p36).toMatchObject({
      physical_file_name: "LIKUTEY HALAJOT (Interior Final).pdf",
      physical_pdf_page: 56,
      footnote_number: 36,
      literal_match_kind: "footnote_literal_exact",
      source_layer: "footnote",
    });
    const evidenceButton = page.locator('button[data-evidence-id="' + p36.evidence_id + '"]').first();
    await expect(evidenceButton).toBeVisible();
    await evidenceButton.click();
    await expect(page.locator('article[data-evidence-id="' + p36.evidence_id + '"] blockquote').first())
      .toContainText("reﬁ namiento");
    await page.goto("/admin/users");
    await expect(page).toHaveURL(/\/research\/?$/);
    await expect(page.getByRole("button", { name: "Crear usuario" })).toHaveCount(0);
    await page.reload();
    await expect(page.getByTestId("research-question")).toBeVisible();
    await clickVisible(page, "Cerrar sesión");
  });
});

test.describe("pdf ligature literal normalization mobile", () => {
  test.skip(!guestEmail || !guestPassword, "guest E2E credentials are required");

  test("mobile recovers note 36 without overflow", async ({ page }) => {
    test.setTimeout(480_000);
    await page.setViewportSize({ width: 390, height: 844 });
    await login(page, guestEmail, guestPassword);
    const body = await ask(page, "refinamiento");
    expect(primary(body)[0]).toMatchObject({
      physical_pdf_page: 56,
      footnote_number: 36,
      literal_match_kind: "footnote_literal_exact",
    });
    await clickVisible(page, "Fuentes");
    const evidenceButton = page.locator('button[data-evidence-id="' + primary(body)[0].evidence_id + '"]').first();
    await expect(evidenceButton).toBeVisible();
    await evidenceButton.click();
    await expect(page.locator('article[data-evidence-id="' + primary(body)[0].evidence_id + '"] blockquote').first())
      .toContainText("reﬁ namiento");
    const overflow = await page.evaluate(() => document.documentElement.scrollWidth - document.documentElement.clientWidth);
    expect(overflow).toBeLessThanOrEqual(1);
    await page.reload();
    await expect(page.getByTestId("research-question")).toBeVisible();
    await clickVisible(page, "Conversación");
    await clickVisible(page, "Cerrar sesión");
  });
});
