import { expect, test } from "@playwright/test";
const email = process.env.TEBAAI_E2E_ADMIN_EMAIL;
const password = process.env.TEBAAI_E2E_ADMIN_PASSWORD;
test.skip(!email || !password, "requires configured E2E administrator credentials");
test("hydrates the composer after login ten consecutive times", async ({ page }) => {
  test.setTimeout(120_000);
  for (let attempt = 1; attempt <= 10; attempt += 1) {
    await page.goto("/login");
    await expect(page.locator("astro-island:not([ssr])")).toBeAttached();
    await page.fill("#login-email", email!); await page.fill("#login-password", password!);
    await page.getByRole("button", { name: "Ingresar" }).click();
    await expect(page).toHaveURL(/\/research$/);
    await expect(page.getByTestId("research-question"), `composer attempt ${attempt}`).toBeVisible();
    await page.getByRole("button", { name: "Cerrar sesión" }).first().click();
    await expect(page).toHaveURL(/\/login$/);
  }
});
test("recovers from corrupt preferences", async ({ page }) => {
  await page.goto("/login"); await page.evaluate(() => sessionStorage.setItem("tebaai_research_filters", "{broken"));
  await page.fill("#login-email", email!); await page.fill("#login-password", password!); await page.getByRole("button", { name: "Ingresar" }).click();
  await expect(page.getByTestId("research-question")).toBeVisible();
});
