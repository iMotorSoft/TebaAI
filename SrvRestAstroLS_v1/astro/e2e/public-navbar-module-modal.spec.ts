import { test, expect, type Page } from "@playwright/test";

const ADMIN_EMAIL = process.env.TEBAAI_E2E_ADMIN_EMAIL ?? "";
const ADMIN_PASSWORD = process.env.TEBAAI_E2E_ADMIN_PASSWORD ?? "";

/**
 * Public navbar module modal — the "Ingresar" CTA opens a premium selector
 * (Investigación / Edición) that reuses the safe intended-destination flow.
 *
 * The page renders two ModuleModal islands (desktop header + mobile menu), so
 * every assertion is scoped to the currently-open dialog.
 */

const OPEN_MODAL = "dialog.module-modal[open]";

async function openModal(page: Page) {
  await page.goto("/");
  await page.getByRole("button", { name: "Ingresar", exact: true }).first().click();
  const dialog = page.locator(OPEN_MODAL);
  await expect(dialog).toBeVisible();
  return dialog;
}

test.describe("public navbar module modal", () => {
  test("Ingresar opens the modal with Investigación and Edición", async ({ page }) => {
    const dialog = await openModal(page);
    await expect(dialog.getByRole("heading", { name: "¿Dónde querés ingresar?" })).toBeVisible();
    await expect(dialog.getByRole("heading", { name: "Investigación", exact: true })).toBeVisible();
    await expect(dialog.getByRole("heading", { name: "Edición", exact: true })).toBeVisible();
    await expect(dialog.getByRole("heading", { name: "Administración", exact: true })).toHaveCount(0);
  });

  test("anonymous module cards preserve the intended destination", async ({ page }) => {
    const dialog = await openModal(page);
    await expect(dialog.locator(".module-modal-card", { hasText: "Investigación" }))
      .toHaveAttribute("href", "/login?next=%2Fresearch");
    await expect(dialog.locator(".module-modal-card", { hasText: "Edición" }))
      .toHaveAttribute("href", "/login?next=%2Fadmin%2Fcontent");
  });

  test("Escape closes the modal and restores focus to Ingresar", async ({ page }) => {
    await openModal(page);
    await page.keyboard.press("Escape");
    await expect(page.locator(OPEN_MODAL)).toHaveCount(0);
    await expect(page.getByRole("button", { name: "Ingresar", exact: true }).first()).toBeFocused();
  });

  test("close button closes the modal", async ({ page }) => {
    const dialog = await openModal(page);
    await dialog.getByRole("button", { name: "Cerrar" }).click();
    await expect(page.locator(OPEN_MODAL)).toHaveCount(0);
  });

  test("click outside (backdrop) closes the modal", async ({ page }) => {
    await openModal(page);
    await page.mouse.click(8, 8);
    await expect(page.locator(OPEN_MODAL)).toHaveCount(0);
  });

  test("keyboard navigation stays within the modal", async ({ page }) => {
    const dialog = await openModal(page);
    // Native showModal focuses the first focusable (the close button).
    await expect(dialog.getByRole("button", { name: "Cerrar" })).toBeFocused();

    await page.keyboard.press("Tab");
    await expect(dialog.locator(".module-modal-card").first()).toBeFocused();

    await page.keyboard.press("Tab");
    await expect(dialog.locator(".module-modal-card").nth(1)).toBeFocused();

    // Focus wraps back to the close button (still inside the dialog).
    await page.keyboard.press("Tab");
    await expect(dialog.getByRole("button", { name: "Cerrar" })).toBeFocused();
  });

  test("Shift+Tab wraps focus backwards within the modal", async ({ page }) => {
    const dialog = await openModal(page);
    await expect(dialog.getByRole("button", { name: "Cerrar" })).toBeFocused();

    await page.keyboard.press("Shift+Tab");
    await expect(dialog.locator(".module-modal-card").nth(1)).toBeFocused();

    await page.keyboard.press("Shift+Tab");
    await expect(dialog.locator(".module-modal-card").first()).toBeFocused();

    // Focus wraps back to the close button (still inside the dialog).
    await page.keyboard.press("Shift+Tab");
    await expect(dialog.getByRole("button", { name: "Cerrar" })).toBeFocused();
  });

  test("authenticated admin sees direct module destinations", async ({ page }) => {
    test.skip(!ADMIN_EMAIL || !ADMIN_PASSWORD, "TEBAAI_E2E_ADMIN_EMAIL/PASSWORD not set");
    await page.goto("/login");
    await page.fill("#login-email", ADMIN_EMAIL);
    await page.fill("#login-password", ADMIN_PASSWORD);
    await page.getByRole("button", { name: "Ingresar" }).click();
    await expect(page).toHaveURL(/\/research\/?$/);

    const dialog = await openModal(page);
    await expect(dialog.locator(".module-modal-card", { hasText: "Investigación" }))
      .toHaveAttribute("href", "/research");
    await expect(dialog.locator(".module-modal-card", { hasText: "Edición" }))
      .toHaveAttribute("href", "/admin/content");
  });

  test("mobile modal (390×844) renders without overflow", async ({ page }) => {
    await page.setViewportSize({ width: 390, height: 844 });
    await page.goto("/");
    await page.getByRole("button", { name: "Abrir menú" }).click();
    await page.getByRole("button", { name: "Ingresar", exact: true }).click();

    const dialog = page.locator(OPEN_MODAL);
    await expect(dialog).toBeVisible();
    // Opening the modal closes the mobile menu (no competing overlay behind).
    await expect(page.getByRole("navigation", { name: "Navegación móvil" })).toHaveCount(0);
    await expect(dialog.getByRole("heading", { name: "Investigación", exact: true })).toBeVisible();
    await expect(dialog.getByRole("heading", { name: "Edición", exact: true })).toBeVisible();
    await expect(dialog.getByRole("button", { name: "Cerrar" })).toBeVisible();

    const overflow = await page.evaluate(
      () => document.documentElement.scrollWidth - document.documentElement.clientWidth,
    );
    expect(overflow).toBeLessThanOrEqual(1);
  });

  test("mobile modal close restores focus to the menu toggle", async ({ page }) => {
    await page.setViewportSize({ width: 390, height: 844 });
    await page.goto("/");
    await page.getByRole("button", { name: "Abrir menú" }).click();
    await page.getByRole("button", { name: "Ingresar", exact: true }).click();
    await expect(page.locator(OPEN_MODAL)).toBeVisible();
    await page.keyboard.press("Escape");
    await expect(page.locator(OPEN_MODAL)).toHaveCount(0);
    await expect(page.getByRole("button", { name: "Abrir menú" })).toBeFocused();
  });

  test("mobile modal at 390×667 keeps CTAs and close reachable", async ({ page }) => {
    await page.setViewportSize({ width: 390, height: 667 });
    await page.goto("/");
    await page.getByRole("button", { name: "Abrir menú" }).click();
    await page.getByRole("button", { name: "Ingresar", exact: true }).click();
    const dialog = page.locator(OPEN_MODAL);
    await expect(dialog).toBeVisible();
    // The whole dialog fits the viewport height; close and both CTAs visible.
    const box = await dialog.boundingBox();
    expect(box).not.toBeNull();
    expect(box!.y + box!.height).toBeLessThanOrEqual(667);
    await expect(dialog.getByRole("button", { name: "Cerrar" })).toBeInViewport();
    await expect(dialog.locator(".module-modal-cta").nth(1)).toBeInViewport();
  });

  test("scroll locks while open and is preserved after close", async ({ page }) => {
    await page.setViewportSize({ width: 1440, height: 900 });
    await page.goto("/");
    await expect(page.getByRole("heading", { level: 1 })).toBeVisible();
    await page.evaluate(() => window.scrollTo(0, 400));
    // Open via a DOM click to avoid Playwright scrolling the trigger into view.
    await page.locator("button.header-login").evaluate((el) => (el as HTMLButtonElement).click());
    await expect(page.locator(OPEN_MODAL)).toBeVisible();
    await expect.poll(() => page.evaluate(() => window.scrollY)).toBe(400);
    // User wheel input over the backdrop must not scroll the page.
    await page.mouse.move(40, 450);
    await page.mouse.wheel(0, 600);
    await expect.poll(() => page.evaluate(() => window.scrollY)).toBe(400);
    await page.keyboard.press("Escape");
    await expect(page.locator(OPEN_MODAL)).toHaveCount(0);
    await expect.poll(() => page.evaluate(() => window.scrollY)).toBe(400);
  });
});
