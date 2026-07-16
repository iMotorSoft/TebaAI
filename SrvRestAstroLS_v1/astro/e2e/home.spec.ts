import { expect, test } from "@playwright/test";

test("home loads", async ({ page }) => {
  await page.goto("/");
  await expect(page.getByRole("heading", { name: "BRESLOV RESEARCH" })).toBeVisible();
  await expect(page.getByText("Investigación verdadera. Fuentes originales. Comprensión más profunda.")).toBeVisible();
  await expect(page.locator(".hero-bri").getByText("Breslov Research Institute — BRI")).toBeVisible();
  await expect(page.getByRole("link", { name: "Iniciar sesión para acceder" })).toHaveAttribute("href", "/login");
  await expect(page.getByRole("link", { name: "Solicitar acceso" })).toHaveAttribute("href", "/request-access");
});
