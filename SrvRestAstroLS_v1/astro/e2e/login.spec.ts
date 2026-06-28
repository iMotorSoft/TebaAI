import { test, expect } from "@playwright/test";

const ADMIN_EMAIL = process.env.TEBAAI_E2E_ADMIN_EMAIL ?? "admin@tebaai.ai";
const ADMIN_PASSWORD = process.env.TEBAAI_E2E_ADMIN_PASSWORD ?? "Admin123!";

test.describe("Login UI", () => {
  test("renders the login form", async ({ page }) => {
    await page.goto("/login");
    await expect(page.locator("h2")).toContainText("Teba AI");
    await expect(page.locator("#login-email")).toBeVisible();
    await expect(page.locator("#login-password")).toBeVisible();
    await expect(page.getByRole("button", { name: "Ingresar" })).toBeVisible();
  });

  test("shows error on invalid credentials", async ({ page }) => {
    await page.goto("/login");
    await page.fill("#login-email", "invalid@test.com");
    await page.fill("#login-password", "wrongpass");
    await page.getByRole("button", { name: "Ingresar" }).click();
    await expect(page.locator('[role="alert"]')).toBeVisible({ timeout: 10000 });
  });

  test("successful login shows user info", async ({ page }) => {
    test.skip(!ADMIN_EMAIL || !ADMIN_PASSWORD, "TEBAAI_E2E_ADMIN_EMAIL/PASSWORD not set");

    await page.goto("/login");
    await page.fill("#login-email", ADMIN_EMAIL);
    await page.fill("#login-password", ADMIN_PASSWORD);
    await page.getByRole("button", { name: "Ingresar" }).click();

    await expect(page.locator("text=Sesión iniciada")).toBeVisible({ timeout: 10000 });
    await expect(page.locator(`text=${ADMIN_EMAIL}`)).toBeVisible();
    await expect(page.locator(".badge-primary")).toBeVisible();
  });

  test("logout clears session", async ({ page }) => {
    test.skip(!ADMIN_EMAIL || !ADMIN_PASSWORD, "TEBAAI_E2E_ADMIN_EMAIL/PASSWORD not set");

    await page.goto("/login");
    await page.fill("#login-email", ADMIN_EMAIL);
    await page.fill("#login-password", ADMIN_PASSWORD);
    await page.getByRole("button", { name: "Ingresar" }).click();

    await expect(page.locator("text=Sesión iniciada")).toBeVisible({ timeout: 10000 });

    await page.getByRole("button", { name: "Cerrar sesión" }).click();

    await expect(page.locator("#login-email")).toBeVisible();
    await expect(page.getByRole("button", { name: "Ingresar" })).toBeVisible();
  });
});
