import { expect, test } from "@playwright/test";
import AxeBuilder from "@axe-core/playwright";

const ADMIN_EMAIL = process.env.TEBAAI_E2E_ADMIN_EMAIL ?? "";
const ADMIN_PASSWORD = process.env.TEBAAI_E2E_ADMIN_PASSWORD ?? "";
const forbiddenInstitutional = /Breslov Research Institute|(^|\W)BRI(\W|$)|En colaboración con|Con el respaldo de|En asociación con/i;
const forbiddenTone = /\b(tú|vos)\b|profundizá|descubrí|transformá|comenzá tu viaje/i;

test("home communicates the investigative positioning and verifiable evidence", async ({ page }) => {
  await page.goto("/");
  await expect(page.getByRole("heading", { level: 1, name: "Localización de conceptos, fuentes y relaciones en las obras de Breslov" })).toBeVisible();
  await expect(page.getByText("Investigación documental sobre literatura Breslov")).toBeVisible();
  await expect(page.getByText(/consultar obras en español, inglés y hebreo/)).toBeVisible();
  await expect(page.getByRole("heading", { name: "Cada respuesta conserva su referencia" })).toBeVisible();
  await expect(page.getByText("Página física e impresa, cuando están disponibles")).toBeVisible();
  await expect(page.getByText("Original, cita, traducción, comentario o nota")).toBeVisible();
  await expect(page.getByRole("heading", { name: "Rigor en la presentación de resultados" })).toBeVisible();
  await expect(page.locator(".hero-actions").getByRole("link", { name: "Ingresar a Investigación" })).toHaveAttribute("href", "/login");
  await expect(page.locator(".hero-actions").getByRole("link", { name: "Solicitar acceso" })).toHaveAttribute("href", "/request-access");

  const body = await page.locator("body").innerText();
  expect(body).not.toMatch(forbiddenInstitutional);
  expect(body).not.toMatch(forbiddenTone);
  expect(body).not.toMatch(/PostgreSQL|Milvus|LiteLLM|embeddings|API|JSON/i);
});

test("home metadata uses the exclusive product identity", async ({ page }) => {
  await page.goto("/");
  await expect(page).toHaveTitle("Breslov Research — Investigación de fuentes y conceptos en la literatura Breslov");
  await expect(page.locator('meta[name="description"]')).toHaveAttribute("content", /referencias verificables en español, inglés y hebreo/);
  await expect(page.locator('meta[property="og:site_name"]')).toHaveAttribute("content", "Breslov Research");
  await expect(page.locator('link[rel="canonical"]')).toHaveAttribute("href", "https://breslov.tebaai.live/");
  await expect(page.locator("h1")).toHaveCount(1);
});

test("public navigation, language fallback and accessibility remain operational", async ({ page }) => {
  await page.goto("/");
  await expect(page.getByRole("link", { name: "Capacidades", exact: true }).first()).toHaveAttribute("href", "#capacidades");
  await page.getByRole("button", { name: "Idiomas disponibles" }).click();
  await page.getByRole("menuitem", { name: "HE" }).click();
  await expect(page.getByRole("status")).toContainText("La interfaz se mantiene en español");
  await expect(page.locator('[lang="he"][dir="rtl"]')).not.toHaveCount(0);

  const accessibility = await new AxeBuilder({ page }).analyze();
  expect(accessibility.violations.filter((item) => item.impact === "critical" || item.impact === "serious")).toEqual([]);
});

test("valid session changes the home access route to research", async ({ page }) => {
  test.skip(!ADMIN_EMAIL || !ADMIN_PASSWORD, "TEBAAI_E2E_ADMIN_EMAIL/PASSWORD not set");
  await page.goto("/login");
  await page.fill("#login-email", ADMIN_EMAIL);
  await page.fill("#login-password", ADMIN_PASSWORD);
  await page.getByRole("button", { name: "Ingresar" }).click();
  await expect(page).toHaveURL(/\/research$/);
  await expect(page.getByTestId("research-question")).toBeVisible();
  await page.goto("/");
  const access = page.locator(".hero-actions").getByRole("link", { name: "Abrir investigación" });
  await expect(access).toHaveAttribute("href", "/research");
  await access.click();
  await expect(page).toHaveURL(/\/research$/);
});

test("request access route remains available", async ({ page }) => {
  await page.goto("/");
  await page.locator(".hero-actions").getByRole("link", { name: "Solicitar acceso" }).click();
  await expect(page).toHaveURL(/\/request-access$/);
  await expect(page.getByRole("heading", { level: 1, name: "Solicitar acceso" })).toBeVisible();
});
