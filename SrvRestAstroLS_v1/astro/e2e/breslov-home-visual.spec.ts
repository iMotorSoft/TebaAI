import { expect, test } from "@playwright/test";
import path from "node:path";

const reportRoot = path.resolve(import.meta.dirname, "../../../data/reports/breslov/2026-07-20-home-investigative-positioning/screenshots");

test("captures the investigative home evidence", async ({ page }) => {
  await page.setViewportSize({ width: 1536, height: 1024 });
  await page.goto("/");
  await expect(page.getByRole("heading", { level: 1 })).toBeVisible();
  await page.screenshot({ path: path.join(reportRoot, "home-after-desktop.png"), fullPage: true });
  await page.locator(".research-hero").screenshot({ path: path.join(reportRoot, "hero-desktop.png") });
  await page.locator("#capacidades").screenshot({ path: path.join(reportRoot, "research-capabilities.png") });
  await page.locator("#verificacion").screenshot({ path: path.join(reportRoot, "verifiable-sources.png") });
  await page.locator("#idiomas").screenshot({ path: path.join(reportRoot, "multilingual-section.png") });
  await page.locator("#casos").screenshot({ path: path.join(reportRoot, "use-cases.png") });
  await page.locator("#rigor").screenshot({ path: path.join(reportRoot, "rigor-and-limits.png") });
  await page.locator("#acceso").screenshot({ path: path.join(reportRoot, "access-cta.png") });
  await page.locator(".home-footer").screenshot({ path: path.join(reportRoot, "footer.png") });
});

test("captures the mobile home and navigation", async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 });
  await page.goto("/");
  await expect(page.getByRole("heading", { level: 1 })).toBeVisible();
  await page.screenshot({ path: path.join(reportRoot, "home-after-mobile.png"), fullPage: true });
  await page.locator(".research-hero").screenshot({ path: path.join(reportRoot, "hero-mobile.png") });
  await page.getByRole("button", { name: "Abrir menú" }).click();
  const mobileNavigation = page.getByRole("navigation", { name: "Navegación móvil" });
  await expect(mobileNavigation.getByRole("link", { name: "Ingresar", exact: true })).toHaveAttribute("href", "/login");
  await expect(mobileNavigation.getByRole("link", { name: "Acceso", exact: true })).toHaveAttribute("href", "#acceso");
  await page.locator(".home-header").screenshot({ path: path.join(reportRoot, "mobile-menu.png") });
  await page.keyboard.press("Escape");
  await expect(page.getByRole("navigation", { name: "Navegación móvil" })).toHaveCount(0);
  await expect(page.getByRole("button", { name: "Abrir menú" })).toBeFocused();
});

test("Breslov home remains usable across the required viewports", async ({ page }) => {
  const criticalErrors: string[] = [];
  const unexpectedResponses: string[] = [];
  page.on("console", (message) => { if (message.type() === "error") criticalErrors.push(message.text()); });
  page.on("response", (response) => { if (response.status() >= 400) unexpectedResponses.push(`${response.status()} ${response.url()}`); });

  for (const viewport of [
    { width: 1536, height: 1024 }, { width: 1366, height: 768 }, { width: 1024, height: 768 },
    { width: 820, height: 1180 }, { width: 768, height: 1024 }, { width: 430, height: 932 },
    { width: 390, height: 844 }, { width: 375, height: 667 }, { width: 320, height: 568 },
  ]) {
    await page.setViewportSize(viewport);
    await page.goto("/");
    await expect(page.getByRole("heading", { level: 1 })).toBeVisible();
    const dimensions = await page.locator("body").evaluate((body) => ({ scroll: body.scrollWidth, client: body.clientWidth }));
    expect(dimensions.scroll, `${viewport.width}x${viewport.height}`).toBe(dimensions.client);
  }

  expect(criticalErrors).toEqual([]);
  expect(unexpectedResponses).toEqual([]);
});
