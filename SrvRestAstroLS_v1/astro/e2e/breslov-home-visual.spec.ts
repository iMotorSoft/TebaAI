import { expect, test } from "@playwright/test";
import path from "node:path";

const reportRoot = path.resolve(import.meta.dirname, "../../../data/reports/breslov/2026-07-16-breslov-research-home/screenshots");

for (const [name, viewport, folder] of [
  ["desktop-1536x1024", { width: 1536, height: 1024 }, "desktop"],
  ["tablet-820x1180", { width: 820, height: 1180 }, "tablet"],
  ["mobile-390x844", { width: 390, height: 844 }, "mobile"],
] as const) {
  test(`Breslov home ${name}`, async ({ page }) => {
    await page.setViewportSize(viewport);
    await page.goto("/");
    await expect(page.getByRole("heading", { name: "BRESLOV RESEARCH" })).toBeVisible();
    await page.waitForTimeout(800);
    await expect(page.locator("body")).toHaveJSProperty("scrollWidth", await page.locator("body").evaluate((body) => body.clientWidth));
    await page.screenshot({ path: path.join(reportRoot, folder, `${name}.png`), fullPage: true });
  });
}

test("mobile navigation exposes real routes", async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 });
  await page.goto("/");
  await page.getByRole("button", { name: "Abrir menú" }).click();
  await expect(page.getByRole("link", { name: "Iniciar sesión", exact: true })).toHaveAttribute("href", "/login");
  await expect(page.getByRole("link", { name: "Acceso", exact: true })).toHaveAttribute("href", "#acceso");
  await page.keyboard.press("Escape");
  await expect(page.getByRole("navigation", { name: "Navegación móvil" })).toHaveCount(0);
  await expect(page.getByRole("button", { name: "Abrir menú" })).toBeFocused();
});

test("Breslov home remains usable across the required viewports", async ({ page }) => {
  const criticalErrors: string[] = [];
  const unexpectedResponses: string[] = [];
  page.on("console", (message) => {
    if (message.type() === "error") criticalErrors.push(message.text());
  });
  page.on("response", (response) => {
    if (response.status() >= 400) unexpectedResponses.push(`${response.status()} ${response.url()}`);
  });

  for (const viewport of [
    { width: 1280, height: 720 }, { width: 1366, height: 768 }, { width: 1440, height: 900 }, { width: 1536, height: 1024 }, { width: 1920, height: 1080 },
    { width: 768, height: 1024 }, { width: 820, height: 1180 }, { width: 1024, height: 768 },
    { width: 320, height: 568 }, { width: 360, height: 800 }, { width: 375, height: 812 }, { width: 390, height: 844 }, { width: 412, height: 915 }, { width: 430, height: 932 },
  ]) {
    await page.setViewportSize(viewport);
    await page.goto("/");
    await expect(page.getByRole("heading", { name: "BRESLOV RESEARCH" })).toBeVisible();
    await expect(page.locator("body")).toHaveJSProperty("scrollWidth", await page.locator("body").evaluate((body) => body.clientWidth));
  }

  expect(criticalErrors).toEqual([]);
  expect(unexpectedResponses).toEqual([]);
});
