import { expect, test } from "@playwright/test";
import path from "node:path";

const adminEmail = process.env.TEBAAI_E2E_ADMIN_EMAIL ?? "";
const adminPassword = process.env.TEBAAI_E2E_ADMIN_PASSWORD ?? "";
const authScreenshots = path.resolve(import.meta.dirname, "../../../data/reports/breslov/2026-07-16-breslov-research-home/screenshots/auth");

test("authenticated session reaches the protected admin route without storing secret evidence", async ({ page }) => {
  test.skip(!adminEmail || !adminPassword, "TEBAAI_E2E_ADMIN_EMAIL/PASSWORD not set");

  await page.goto("/login");
  await page.screenshot({ path: path.join(authScreenshots, "login-form.png") });
  await page.fill("#login-email", adminEmail);
  await page.fill("#login-password", adminPassword);
  await page.getByRole("button", { name: "Ingresar" }).click();
  const sessionConfirmation = page.getByText("Sesión iniciada");
  await expect(sessionConfirmation).toBeVisible();
  await sessionConfirmation.screenshot({ path: path.join(authScreenshots, "session-confirmed.png") });
  await expect(page.evaluate(() => Boolean(localStorage.getItem("tebaai_access_token")))).resolves.toBe(true);

  await page.goto("/admin/users");
  const protectedHeading = page.getByText("Administración de usuarios");
  await expect(protectedHeading).toBeVisible();
  await protectedHeading.screenshot({ path: path.join(authScreenshots, "protected-admin-heading.png") });
});
