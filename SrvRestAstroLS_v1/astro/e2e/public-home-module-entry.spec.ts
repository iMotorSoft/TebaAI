import { test, expect } from "@playwright/test";

/**
 * Public Home module entry — the pre-auth selector exposes Investigación and
 * Edición (and does not yet expose Administración). Each entry routes an
 * anonymous visitor to the login with the intended destination preserved.
 */

test.describe("public home module entry", () => {
  test("anonymous home exposes Investigación and Edición modules", async ({ page }) => {
    await page.goto("/");

    await expect(page.getByRole("heading", { name: "Investigación", exact: true })).toBeVisible();
    await expect(page.getByRole("heading", { name: "Edición", exact: true })).toBeVisible();

    // Module descriptions are human-readable, no technical jargon. The modal
    // shares the same copy, so scope to the Home section to avoid ambiguity.
    const section = page.locator(".module-entry-section");
    await expect(section.getByText(/Consultá, buscá y relacioná/)).toBeVisible();
    await expect(section.getByText(/Administrá las fuentes documentales/)).toBeVisible();

    // CTA labels are the module entry actions.
    await expect(page.getByRole("link", { name: /Entrar a Investigación/ })).toBeVisible();
    await expect(page.getByRole("link", { name: /Entrar a Edición/ })).toBeVisible();
  });

  test("Administración is not exposed yet", async ({ page }) => {
    await page.goto("/");
    await expect(page.getByRole("heading", { name: "Administración", exact: true })).toHaveCount(0);
    await expect(page.getByText(/Usuarios · Roles · Permisos/)).toHaveCount(0);
  });

  test("each module entry preserves its intended destination via next", async ({ page }) => {
    await page.goto("/");

    const research = page.getByRole("link", { name: /Entrar a Investigación/ });
    await expect(research).toHaveAttribute("href", "/login?next=%2Fresearch");

    const edition = page.getByRole("link", { name: /Entrar a Edición/ });
    await expect(edition).toHaveAttribute("href", "/login?next=%2Fadmin%2Fcontent");
  });

  test("Edición entry navigates to login with the edition destination", async ({ page }) => {
    await page.goto("/");
    await page.getByRole("link", { name: /Entrar a Edición/ }).click();
    await expect(page).toHaveURL(/\/login\?next=%2Fadmin%2Fcontent/);
    await expect(page.locator("#login-email")).toBeVisible();
  });

  test("mobile (390×844) shows both modules without horizontal overflow", async ({ page }) => {
    await page.setViewportSize({ width: 390, height: 844 });
    await page.goto("/");

    await expect(page.getByRole("heading", { name: "Investigación", exact: true })).toBeVisible();
    await expect(page.getByRole("heading", { name: "Edición", exact: true })).toBeVisible();
    await expect(page.getByRole("link", { name: /Entrar a Edición/ })).toBeVisible();

    const overflow = await page.evaluate(
      () => document.documentElement.scrollWidth - document.documentElement.clientWidth,
    );
    expect(overflow).toBeLessThanOrEqual(1);
  });
});
