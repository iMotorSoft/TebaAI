import { expect, test } from "@playwright/test";
import AxeBuilder from "@axe-core/playwright";

const email = process.env.TEBAAI_E2E_ADMIN_EMAIL;
const password = process.env.TEBAAI_E2E_ADMIN_PASSWORD;

test.describe("authenticated research workspace", () => {
  test.skip(!email || !password, "requires configured E2E administrator credentials");
  test("redirects, researches with the real API, and logs out", async ({ page }) => {
    test.setTimeout(120_000);
    await page.goto("/research");
    await expect(page).toHaveURL(/\/login$/);
    await page.fill("#login-email", email!);
    await page.fill("#login-password", password!);
    await page.getByRole("button", { name: "Ingresar" }).click();
    await expect(page).toHaveURL(/\/research$/);
    await page.getByTestId("research-question").fill("¿Dónde aparece la plegaria?");
    await page.getByTestId("research-submit").click();
    await expect(page.getByText("Breslov Research", { exact: true })).toBeVisible({ timeout: 30_000 });
    await expect(page.getByText(/evidencias principales/)).toBeVisible();
    await expect(page.getByText(/PDF p\.|Página no disponible/).first()).toBeVisible();
    await expect(page.getByRole("heading", { name: "Fuentes del turno" })).toBeVisible();
    const sources = page.locator(".source-list button:visible");
    await expect(sources.first()).toBeVisible();
    if (await sources.count() > 1) await sources.nth(1).click();
    await page.getByText("Matriz de evidencia", { exact: true }).click();
    await expect(page.locator(".matrix-row").nth(1)).toBeVisible();
    await page.getByRole("button", { name: "Filtros" }).last().click();
    const dialog = page.getByRole("dialog", { name: "Filtros de investigación" });
    await dialog.getByLabel("Kitzur Likutey Moharán").uncheck(); await dialog.getByLabel("Likutey Moharán I — edición española BRI").uncheck(); await dialog.getByLabel("Likutey Moharán II").uncheck(); await dialog.getByLabel("Likutey Moharán XV").uncheck(); await dialog.getByLabel("La Potencia de la Plegaria").uncheck();
    await dialog.getByLabel("Incluir paralelos temáticos").uncheck(); await dialog.getByLabel("Resultados").selectOption("5"); await dialog.getByRole("button", { name: "Aplicar filtros" }).click();
    await page.getByTestId("research-question").fill("¿Y en Likutey Halajot?");
    const filteredRequest = page.waitForRequest((request) => request.url().endsWith("/library/investigative-qa/v1") && request.method() === "POST");
    await page.getByTestId("research-submit").click();
    const payload = (await filteredRequest).postDataJSON(); expect(payload.works).toEqual(["lh"]); expect(payload.max_hits_per_work).toBe(5); expect(payload.include_thematic).toBe(false); expect(payload.include_audit).toBe(false);
    await expect(page.getByText(/evidencias principales|No se encontró evidencia suficiente/)).toBeVisible({ timeout: 30_000 });
    const accessibility = await new AxeBuilder({ page }).exclude(".enriched-markdown").analyze();
    expect(accessibility.violations.filter((item) => item.impact === "critical")).toEqual([]);
    await page.getByRole("button", { name: /Nueva investigación/ }).first().click();
    await expect(page.getByRole("heading", { name: "¿Qué querés investigar?" })).toBeVisible();
    await page.getByRole("button", { name: "Cerrar sesión" }).first().click();
    await expect(page).toHaveURL(/\/login$/);
  });
});
