import { expect, test } from "@playwright/test";

test("home loads", async ({ page }) => {
  await page.goto("/");
  await expect(page.getByRole("heading", { name: "Teba AI" })).toBeVisible();
  await expect(page.getByText("Generic content platform")).toBeVisible();
});
