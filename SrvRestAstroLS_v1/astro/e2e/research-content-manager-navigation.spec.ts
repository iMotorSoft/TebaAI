import { test, expect } from "@playwright/test";
import {
  ADMIN_EMAIL,
  ADMIN_PASSWORD,
  loginAsAdmin,
  loginAs,
} from "./content-manager-helpers";

/**
 * Unified navigation: Investigación ↔ Gestor de Contenidos.
 *
 * The admin sees a "Gestor de Contenidos" action on /research; the manager
 * shows "Investigación" back. Both reuse the same session. Non-admin roles
 * never see the administrative entry point.
 */

const GUEST_EMAIL = process.env.TEBAAI_E2E_GUEST_EMAIL ?? "guest@tebaai.live";
const GUEST_PASSWORD = process.env.TEBAAI_E2E_GUEST_PASSWORD ?? "";

test.describe("unified navigation (real backend)", () => {
  test.skip(!ADMIN_EMAIL || !ADMIN_PASSWORD, "TEBAAI_E2E_ADMIN_EMAIL/PASSWORD not set");

  test("admin navigates Investigación → Gestor and back in the same session", async ({ page }) => {
    await loginAsAdmin(page);
    await page.goto("/research");

    // Admin sees the manager entry point in the research header.
    const managerLink = page.getByRole("link", { name: "Gestor de Contenidos" }).first();
    await expect(managerLink).toBeVisible();

    // Navigate to the manager, same session (no login redirect).
    await managerLink.click();
    await page.waitForURL(/\/admin\/content/);
    await expect(page.getByRole("heading", { name: "Gestor de Contenidos" })).toBeVisible();

    // The manager exposes Investigación back.
    const researchLink = page.getByRole("link", { name: "Investigación" });
    await expect(researchLink).toBeVisible();

    // Return to research in the same tab.
    await researchLink.click();
    await page.waitForURL(/\/research/);
    await expect(page.getByRole("heading", { name: "Investigación" })).toBeVisible();
  });

  test("admin manager → research preserves session without a new login", async ({ page }) => {
    await loginAsAdmin(page);
    await page.goto("/admin/content");
    await expect(page.getByRole("heading", { name: "Gestor de Contenidos" })).toBeVisible();

    await page.getByRole("link", { name: "Investigación" }).click();
    await page.waitForURL(/\/research/);
    // Session preserved: the research workspace loads, not the login page.
    await expect(page.getByRole("heading", { name: "Investigación" })).toBeVisible();
    await expect(page).not.toHaveURL(/\/login/);
  });

  test("guest never sees the manager entry point on /research", async ({ page }) => {
    test.skip(!GUEST_PASSWORD, "TEBAAI_E2E_GUEST_PASSWORD not set");
    await loginAs(page, GUEST_EMAIL, GUEST_PASSWORD);
    await page.goto("/research");

    await expect(page.getByRole("heading", { name: "Investigación" })).toBeVisible();
    await expect(page.getByRole("link", { name: "Gestor de Contenidos" })).toHaveCount(0);
  });
});
