import { expect, test } from "@playwright/test";
const email = process.env.TEBAAI_E2E_ADMIN_EMAIL; const password = process.env.TEBAAI_E2E_ADMIN_PASSWORD;
test.skip(!email || !password, "requires configured E2E administrator credentials");
test("has no horizontal overflow across required viewports and restores drawer focus", async ({ page }) => {
  await page.goto("/login"); await expect(page.locator("astro-island:not([ssr])")).toBeAttached(); await page.fill("#login-email", email!); await page.fill("#login-password", password!); await page.getByRole("button", { name: "Ingresar" }).click(); await expect(page.getByTestId("research-question")).toBeVisible();
  for (const [width, height] of [[1280,720],[1366,768],[1440,900],[1536,1024],[1920,1080],[768,1024],[820,1180],[1024,768],[320,568],[360,800],[375,812],[390,844],[412,915],[430,932]]) { await page.setViewportSize({ width, height }); expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth + 1), `${width}x${height}`).toBe(true); await expect(page.getByTestId("research-question")).toBeVisible(); }
  await page.setViewportSize({ width: 390, height: 844 });
  const sourceButton = page.getByRole("button", { name: "Fuentes", exact: true });
  await sourceButton.focus();
  await sourceButton.click();
  await page.keyboard.press("Shift+Tab");
  expect(await page.evaluate(() => document.activeElement?.closest(".sources.open") !== null)).toBe(true);
  await page.keyboard.press("Escape");
  await expect(sourceButton).toBeFocused();
});
