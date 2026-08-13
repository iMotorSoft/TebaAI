import { test, expect } from "@playwright/test";
import { ADMIN_EMAIL, ADMIN_PASSWORD, loginAsAdmin } from "./content-manager-helpers";

/**
 * Content Manager — test data visibility (E2E separation).
 *
 * E2E fixtures (scope breslov_e2e) are hidden from the library by default.
 * An admin can explicitly enable "Mostrar datos de prueba", which reveals
 * them clearly marked. Disabling hides them again. No data is deleted.
 */

test.describe("Content Manager test data visibility (real backend)", () => {
  test.skip(!ADMIN_EMAIL || !ADMIN_PASSWORD, "TEBAAI_E2E_ADMIN_EMAIL/PASSWORD not set");

  test("E2E data is hidden by default and revealed only on demand", async ({ page }) => {
    await loginAsAdmin(page);
    await page.goto("/admin/content");

    // Toggle starts OFF (unchecked).
    const toggle = page.getByLabel("Mostrar datos de prueba");
    await expect(toggle).toBeVisible();
    await expect(toggle).not.toBeChecked();

    // E2E fixtures (marked "Fuente ... Playwright") are absent by default.
    await expect(page.locator(".cm-badge--test")).toHaveCount(0);

    // Enable test data.
    await toggle.check();
    // The E2E items now appear, clearly marked.
    await expect(page.locator(".cm-badge--test").first()).toBeVisible({ timeout: 15_000 });

    // Disable again — E2E items disappear.
    await toggle.uncheck();
    await expect(page.locator(".cm-badge--test")).toHaveCount(0);
  });
});
