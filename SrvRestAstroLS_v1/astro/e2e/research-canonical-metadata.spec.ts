import { expect, test, type Page } from "@playwright/test";

const adminEmail = process.env.TEBAAI_E2E_ADMIN_EMAIL ?? "";
const adminPassword = process.env.TEBAAI_E2E_ADMIN_PASSWORD ?? "";
const guestEmail = process.env.TEBAAI_E2E_GUEST_EMAIL ?? "";
const guestPassword = process.env.TEBAAI_E2E_GUEST_PASSWORD ?? "";
const endpoint = "/library/investigative-qa/v1";

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

test.describe("canonical work edition source metadata", () => {
  test.skip(!adminEmail || !adminPassword, "admin E2E credentials are required");

  test("admin distinguishes family, edition, original source and cross-source roles", async ({ page }) => {
    test.setTimeout(900_000);
    await login(page, adminEmail, adminPassword);

    const family = await ask(page, "¿Dónde habla Likutey Halajot sobre la plegaria?");
    expect(family.retrieval.canonical_scope.scope_family).toEqual(["likutey_halajot"]);
    expect(new Set(family.hits.map((hit: any) => hit.work_family_code))).toEqual(new Set(["likutey_halajot"]));

    const edition = await ask(page, "¿Dónde aparece MELODÍAS Y PLEGARIAS en Interior Final?");
    expect(primary(edition)).toEqual(expect.arrayContaining([
      expect.objectContaining({ edition: "Interior Final", volume_number: null, technical_version: "v2", physical_pdf_page: 56 }),
    ]));
    const sources = page.locator('aside[aria-label="Fuentes del turno"]');
    await expect(sources).toContainText("Obra: Likutey Halajot");
    await expect(sources).toContainText("Edición: Interior Final (derivada)");
    await expect(sources).toContainText("Versión técnica");

    const source = await ask(page, "¿Dónde desarrolla Likutey Halajot la lección 8 de Likutey Moharán II?");
    expect(primary(source)).toEqual(expect.arrayContaining([
      expect.objectContaining({ work_family_code: "likutey_halajot", source_work_code: "likutey_moharan_ii", source_lesson: 8, source_relation: "develops" }),
    ]));
    await expect(sources).toContainText("Fuente desarrollada: Likutey Moharán II, lección 8");

    const original = await ask(page, "¿Dónde está la lección 8 de Likutey Moharán II?");
    expect(primary(original).every((hit: any) => hit.work_family_code === "likutey_moharan_ii")).toBe(true);

    const cross = await ask(page, "Compará Likutey Moharán II 8 con Likutey Halajot.");
    expect(new Set(cross.hits.map((hit: any) => hit.work_family_code))).toEqual(new Set(["likutey_halajot", "likutey_moharan_ii"]));
    expect(cross.retrieval.canonical_scope.cross_family).toBe(true);

    const ambiguous = await ask(page, "Likutey");
    expect(ambiguous.research_status).toBe("no_evidence");
    expect(ambiguous.warnings).toContain("scope_ambiguous");

    await page.reload();
    await expect(page.getByTestId("research-question")).toBeVisible();
    await clickVisible(page, "Cerrar sesión");
    await expect(page).toHaveURL(/\/login\/?$/);
  });
});

test.describe("canonical metadata guest", () => {
  test.skip(!guestEmail || !guestPassword, "guest E2E credentials are required");

  test("guest sees canonical labels and remains read-only", async ({ page }) => {
    test.setTimeout(480_000);
    await login(page, guestEmail, guestPassword);
    const body = await ask(page, "¿Dónde desarrolla Likutey Halajot la lección 8 de Likutey Moharán II?");
    expect(primary(body)[0]).toMatchObject({ work_family: "Likutey Halajot", source_work: "Likutey Moharán II", source_lesson: 8 });
    await expect(page.locator('aside[aria-label="Fuentes del turno"]')).toContainText("Fuente desarrollada");
    await page.goto("/admin/users");
    await expect(page).toHaveURL(/\/research\/?$/);
    await expect(page.getByRole("button", { name: "Crear usuario" })).toHaveCount(0);
    await page.reload();
    await expect(page.getByTestId("research-question")).toBeVisible();
    await clickVisible(page, "Cerrar sesión");
  });

  test("guest mobile shows edition metadata without overflow", async ({ page }) => {
    test.setTimeout(360_000);
    await page.setViewportSize({ width: 390, height: 844 });
    await login(page, guestEmail, guestPassword);
    const body = await ask(page, "¿Dónde aparece MELODÍAS Y PLEGARIAS en Interior Final?");
    expect(primary(body)[0]).toMatchObject({ edition: "Interior Final", technical_version: "v2" });
    await clickVisible(page, "Fuentes");
    const sources = page.locator('aside[aria-label="Fuentes del turno"]');
    await expect(sources).toContainText("Obra: Likutey Halajot");
    await expect(sources).toContainText("Edición: Interior Final (derivada)");
    const overflow = await page.evaluate(() => document.documentElement.scrollWidth - document.documentElement.clientWidth);
    expect(overflow).toBeLessThanOrEqual(1);
    await page.reload();
    await expect(page.getByTestId("research-question")).toBeVisible();
    await clickVisible(page, "Conversación");
    await clickVisible(page, "Cerrar sesión");
  });
});
