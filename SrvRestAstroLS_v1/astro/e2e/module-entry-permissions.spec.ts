import { test, expect, type Page } from "@playwright/test";

const ADMIN_EMAIL = process.env.TEBAAI_E2E_ADMIN_EMAIL ?? "";
const ADMIN_PASSWORD = process.env.TEBAAI_E2E_ADMIN_PASSWORD ?? "";
const GUEST_EMAIL = process.env.TEBAAI_E2E_GUEST_EMAIL ?? "guest@tebaai.live";
const GUEST_PASSWORD = process.env.TEBAAI_E2E_GUEST_PASSWORD ?? "";

/**
 * Module entry permissions — authorization is enforced after authentication.
 * A viewer/guest can enter Investigación but not Edición; the denial is a
 * readable UX that keeps the session alive, never a silent redirect.
 */

async function login(page: Page, email: string, password: string) {
  await page.fill("#login-email", email);
  await page.fill("#login-password", password);
  await page.getByRole("button", { name: "Ingresar" }).click();
}

test.describe("module entry permissions", () => {
  test("admin logs into Edición directly", async ({ page }) => {
    test.skip(!ADMIN_EMAIL || !ADMIN_PASSWORD, "TEBAAI_E2E_ADMIN_EMAIL/PASSWORD not set");
    await page.goto("/login?next=%2Fadmin%2Fcontent");
    await login(page, ADMIN_EMAIL, ADMIN_PASSWORD);
    await expect(page).toHaveURL(/\/admin\/content\/?$/);
    await expect(page.getByRole("heading", { name: "Gestor de Contenidos" })).toBeVisible();
  });

  test("viewer enters Investigación", async ({ page }) => {
    test.skip(!GUEST_PASSWORD, "TEBAAI_E2E_GUEST_PASSWORD not set");
    await page.goto("/login?next=%2Fresearch");
    await login(page, GUEST_EMAIL, GUEST_PASSWORD);
    await expect(page).toHaveURL(/\/research\/?$/);
    await expect(page.getByTestId("research-question")).toBeVisible();
  });

  test("viewer is denied Edición with a readable message and a live session", async ({ page }) => {
    test.skip(!GUEST_PASSWORD, "TEBAAI_E2E_GUEST_PASSWORD not set");
    await page.goto("/login?next=%2Fadmin%2Fcontent");
    await login(page, GUEST_EMAIL, GUEST_PASSWORD);

    // Readable denial UX, not a generic 403 page or a silent research redirect.
    await expect(page.getByText(/No tenés permisos para acceder a Edición/)).toBeVisible({ timeout: 10000 });
    await expect(page.getByRole("link", { name: "Ir a Investigación" })).toBeVisible();
    await expect(page.getByRole("link", { name: "Volver al inicio" })).toBeVisible();

    // Session remains valid: navigating to Investigación works without re-login.
    await page.getByRole("link", { name: "Ir a Investigación" }).click();
    await expect(page).toHaveURL(/\/research\/?$/);
    await expect(page.getByTestId("research-question")).toBeVisible();
  });

  test("already-authenticated viewer hitting Edición is denied, not re-login", async ({ page }) => {
    test.skip(!GUEST_PASSWORD, "TEBAAI_E2E_GUEST_PASSWORD not set");
    await page.goto("/login?next=%2Fresearch");
    await login(page, GUEST_EMAIL, GUEST_PASSWORD);
    await expect(page).toHaveURL(/\/research\/?$/);

    // Back to the Home; the module entry links straight to the destination.
    await page.goto("/");
    await page.getByRole("link", { name: /Entrar a Edición/ }).click();

    // The Content Manager's own guard denies without requesting a new login.
    await expect(page.getByText(/No tenés permiso para acceder al Gestor de Contenidos/)).toBeVisible({ timeout: 10000 });
    await expect(page).not.toHaveURL(/\/login/);
  });
});
