import { test, expect, type Page } from "@playwright/test";

const ADMIN_EMAIL = process.env.TEBAAI_E2E_ADMIN_EMAIL ?? "";
const ADMIN_PASSWORD = process.env.TEBAAI_E2E_ADMIN_PASSWORD ?? "";

/**
 * Intended destination — the login honors a safe `next` value: Research and
 * Edición land on their destination, login errors preserve the intention, and
 * malicious external/protocol-relative/encoded values never navigate away.
 */

async function login(page: Page, email: string, password: string) {
  await page.fill("#login-email", email);
  await page.fill("#login-password", password);
  await page.getByRole("button", { name: "Ingresar" }).click();
}

test.describe("auth intended destination", () => {
  test.skip(!ADMIN_EMAIL || !ADMIN_PASSWORD, "TEBAAI_E2E_ADMIN_EMAIL/PASSWORD not set");

  test("login with next=/research lands on research", async ({ page }) => {
    await page.goto("/login?next=%2Fresearch");
    await login(page, ADMIN_EMAIL, ADMIN_PASSWORD);
    await expect(page).toHaveURL(/\/research\/?$/);
    await expect(page.getByTestId("research-question")).toBeVisible();
  });

  test("login with next=/admin/content lands on the Content Manager", async ({ page }) => {
    await page.goto("/login?next=%2Fadmin%2Fcontent");
    await login(page, ADMIN_EMAIL, ADMIN_PASSWORD);
    await expect(page).toHaveURL(/\/admin\/content\/?$/);
    await expect(page.getByRole("heading", { name: "Gestor de Contenidos" })).toBeVisible();
  });

  test("direct login without next keeps the historical research fallback", async ({ page }) => {
    await page.goto("/login");
    await login(page, ADMIN_EMAIL, ADMIN_PASSWORD);
    await expect(page).toHaveURL(/\/research\/?$/);
  });

  test("login error preserves the intended destination", async ({ page }) => {
    await page.goto("/login?next=%2Fadmin%2Fcontent");
    await login(page, ADMIN_EMAIL, "wrong-password");
    await expect(page.locator('[role="alert"]')).toBeVisible({ timeout: 10000 });
    // The `next` intent survives the failed attempt; correcting it lands on edition.
    await login(page, ADMIN_EMAIL, ADMIN_PASSWORD);
    await expect(page).toHaveURL(/\/admin\/content\/?$/);
  });
});

test.describe("safe redirect hardening", () => {
  test.skip(!ADMIN_EMAIL || !ADMIN_PASSWORD, "TEBAAI_E2E_ADMIN_EMAIL/PASSWORD not set");

  test("external URL next falls back to internal research", async ({ page }) => {
    await page.goto("/login?next=https%3A%2F%2Fexample.invalid");
    await login(page, ADMIN_EMAIL, ADMIN_PASSWORD);
    await expect(page).toHaveURL(/\/research\/?$/);
    await expect(page).not.toHaveURL(/example\.invalid/);
  });

  test("protocol-relative URL next stays internal", async ({ page }) => {
    await page.goto("/login?next=%2F%2Fexample.invalid");
    await login(page, ADMIN_EMAIL, ADMIN_PASSWORD);
    await expect(page).toHaveURL(/\/research\/?$/);
    await expect(page).not.toHaveURL(/example\.invalid/);
  });

  test("javascript scheme next stays internal", async ({ page }) => {
    await page.goto("/login?next=javascript%3Aalert(1)");
    await login(page, ADMIN_EMAIL, ADMIN_PASSWORD);
    await expect(page).toHaveURL(/\/research\/?$/);
    await expect(page).not.toHaveURL(/alert/);
  });
});
