import { expect, test } from "@playwright/test";
import path from "node:path";

const GUEST_EMAIL = process.env.TEBAAI_E2E_GUEST_EMAIL ?? "guest@tebaai.live";
const GUEST_PASSWORD = process.env.TEBAAI_E2E_GUEST_PASSWORD ?? "";
const SCREENSHOTS = path.resolve(
  import.meta.dirname,
  "../../../data/reports/breslov/2026-07-27-private-beta-guest-user/screenshots",
);

async function loginGuest(page: import("@playwright/test").Page) {
  await page.goto("/login");
  await page.fill("#login-email", GUEST_EMAIL);
  await page.fill("#login-password", GUEST_PASSWORD);
  await page.getByRole("button", { name: "Ingresar" }).click();
  await expect(page).toHaveURL(/\/research\/?$/);
  await expect(page.getByTestId("research-question")).toBeVisible();
}

test.describe("read-only research guest", () => {
  test.skip(!GUEST_PASSWORD, "TEBAAI_E2E_GUEST_PASSWORD not set");

  test("can research and inspect evidence", async ({ page }) => {
    test.setTimeout(150_000);
    await loginGuest(page);
    await page.screenshot({ path: path.join(SCREENSHOTS, "research-guest.png"), fullPage: true });
    await page.getByTestId("research-question").fill("¿En qué partes se habla de la tristeza y cuáles son las fuentes?");
    await page.getByTestId("research-submit").click();
    await expect(page.getByTestId("interpretation-analyze")).toBeVisible();
    await expect(page.getByTestId("interpretation-modify")).toBeVisible();
    await page.screenshot({ path: path.join(SCREENSHOTS, "interpretation.png"), fullPage: true });
    await page.getByTestId("interpretation-analyze").click();
    await expect(page.getByTestId("research-result-heading")).toBeVisible({ timeout: 120_000 });
    await expect(page.locator('aside[aria-label="Fuentes del turno"]')).toBeVisible();
    await page.screenshot({ path: path.join(SCREENSHOTS, "analyze-evidence.png"), fullPage: true });
  });

  test("admin route redirects without rendering admin controls", async ({ page }) => {
    await loginGuest(page);
    await page.goto("/admin/users");
    await expect(page).toHaveURL(/\/research\/?$/);
    await expect(page.getByTestId("research-question")).toBeVisible();
    await expect(page.getByRole("button", { name: "Crear usuario" })).toHaveCount(0);
    await expect(page.getByText("Administración de usuarios")).toHaveCount(0);
    await page.screenshot({ path: path.join(SCREENSHOTS, "forbidden-admin-redirect.png"), fullPage: true });
  });

  test("logout revokes the browser session", async ({ page }) => {
    await loginGuest(page);
    await page.getByRole("button", { name: "Cerrar sesión" }).first().click();
    await expect(page).toHaveURL(/\/login\/?$/);
    await page.goto("/research");
    await expect(page).toHaveURL(/\/login\/?$/);
    await page.screenshot({ path: path.join(SCREENSHOTS, "logout.png"), fullPage: true });
  });
});
