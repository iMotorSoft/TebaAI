import { test, expect } from "@playwright/test";

const ADMIN_EMAIL = process.env.TEBAAI_E2E_ADMIN_EMAIL ?? "";
const ADMIN_PASSWORD = process.env.TEBAAI_E2E_ADMIN_PASSWORD ?? "";

test.describe("Login 10/10 regression", () => {
  const CONSECUTIVE_RUNS = 10;

  for (let i = 1; i <= CONSECUTIVE_RUNS; i++) {
    test(`run ${i}/${CONSECUTIVE_RUNS}: login → research → login → verify → logout`, async ({ page }) => {
      test.skip(!ADMIN_EMAIL || !ADMIN_PASSWORD, "TEBAAI_E2E_ADMIN_EMAIL/PASSWORD not set");

      const errors: string[] = [];
      page.on("console", (msg) => { if (msg.type() === "error") errors.push(msg.text()); });
      page.on("pageerror", (err) => errors.push(err.message));

      // 1. Login
      await page.goto("/login");
      await page.fill("#login-email", ADMIN_EMAIL);
      await page.fill("#login-password", ADMIN_PASSWORD);
      await page.getByRole("button", { name: "Ingresar" }).click();
      await expect(page).toHaveURL(/\/research$/);
      await expect(page.getByTestId("research-question")).toBeVisible({ timeout: 15000 });

      // 2. Navigate to /login — session card
      await page.goto("/login");
      await expect(page.getByText("Sesión iniciada")).toBeVisible({ timeout: 10000 });

      // 3. Ir a Investigación
      await page.getByRole("link", { name: "Ir a Investigación" }).click();
      await expect(page).toHaveURL(/\/research$/);

      // 4. Volver a /login
      await page.goto("/login");
      await expect(page.getByText("Sesión iniciada")).toBeVisible({ timeout: 10000 });

      // 5. Verificar sesión
      await page.getByRole("button", { name: "Verificar sesión" }).click();
      await expect(page.getByText("Sesión válida.")).toBeVisible({ timeout: 10000 });

      // 6. Cerrar sesión
      await page.getByRole("button", { name: "Cerrar sesión" }).click();
      await expect(page.locator("#login-email")).toBeVisible({ timeout: 10000 });

      // 7. /research redirects
      await page.goto("/research");
      await expect(page).toHaveURL(/\/login$/);

      // 8. No console errors
      expect(errors.length).toBe(0);
    });
  }
});
