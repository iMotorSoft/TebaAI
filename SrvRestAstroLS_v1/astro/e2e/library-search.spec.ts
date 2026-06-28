import { test, expect } from "@playwright/test";

const ADMIN_EMAIL = process.env.TEBAAI_E2E_ADMIN_EMAIL ?? "admin@tebaai.ai";
const ADMIN_PASSWORD = process.env.TEBAAI_E2E_ADMIN_PASSWORD ?? "Admin123!";

test.describe("Library search UI", () => {
  test("shows login required when not authenticated", async ({ page }) => {
    await page.goto("/library/search");
    await expect(page.locator("text=Necesitás iniciar sesión")).toBeVisible();
    await expect(page.getByRole("link", { name: "Iniciar sesión" })).toBeVisible();
  });

  test("authenticated user can search and see results", async ({ page }) => {
    // Login first
    await page.goto("/login");
    await page.fill("#login-email", ADMIN_EMAIL);
    await page.fill("#login-password", ADMIN_PASSWORD);
    await page.getByRole("button", { name: "Ingresar" }).click();
    await expect(page.locator("text=Sesión iniciada")).toBeVisible({ timeout: 10000 });

    // Go to search
    await page.goto("/library/search");
    await expect(page.locator("text=Búsqueda bibliográfica")).toBeVisible({ timeout: 10000 });

    // Search
    await page.fill('input[type="text"]', "plegaria");
    await page.getByRole("button", { name: "Buscar" }).click();

    // Wait for results
    await expect(page.locator("text=resultado(s)")).toBeVisible({ timeout: 15000 });
    await expect(page.getByRole("heading", { name: "La Potencia de la Plegaria" }).first()).toBeVisible();
  });

  test("search with no results shows message", async ({ page }) => {
    await page.goto("/login");
    await page.fill("#login-email", ADMIN_EMAIL);
    await page.fill("#login-password", ADMIN_PASSWORD);
    await page.getByRole("button", { name: "Ingresar" }).click();
    await expect(page.locator("text=Sesión iniciada")).toBeVisible({ timeout: 10000 });

    await page.goto("/library/search");
    await expect(page.locator("text=Búsqueda bibliográfica")).toBeVisible({ timeout: 10000 });

    await page.fill('input[type="text"]', "zzzz-no-existe-breslov");
    await page.getByRole("button", { name: "Buscar" }).click();

    await expect(page.locator("text=Sin resultados")).toBeVisible({ timeout: 15000 });
  });
});
