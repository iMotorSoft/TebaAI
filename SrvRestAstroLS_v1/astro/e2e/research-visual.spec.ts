import { expect, test, type Page } from "@playwright/test";
import path from "node:path";
import fs from "node:fs";
import { fulfillConfirmationPhases } from "./research-confirmation-helpers";
const email = process.env.TEBAAI_E2E_ADMIN_EMAIL; const password = process.env.TEBAAI_E2E_ADMIN_PASSWORD;
const shots = path.resolve(import.meta.dirname, "../../../data/reports/breslov/2026-07-16-research-workspace-v1/screenshots");
fs.mkdirSync(shots, { recursive: true });
async function login(page: Page) { await page.goto("/login"); await expect(page.locator("astro-island:not([ssr])")).toBeAttached(); await page.fill("#login-email", email!); await page.fill("#login-password", password!); await page.getByRole("button", { name: "Ingresar" }).click(); await expect(page.getByTestId("research-question")).toBeVisible(); }
test.skip(!email || !password, "requires configured E2E administrator credentials");
test("captures the real desktop research workspace", async ({ page }) => {
  test.setTimeout(90_000); await page.setViewportSize({ width: 1536, height: 1024 }); await login(page);
  await page.screenshot({ path: path.join(shots, "desktop-empty.png"), fullPage: true });
  await page.getByRole("button", { name: "Filtros" }).last().click(); await page.screenshot({ path: path.join(shots, "desktop-filters.png") }); await page.getByRole("button", { name: "Cerrar filtros" }).click();
  await page.getByTestId("research-question").fill("¿Dónde aparece la plegaria?"); await page.getByTestId("research-submit").click(); await page.getByTestId("interpretation-analyze").click(); await expect(page.locator(".synthesis")).toBeVisible({ timeout: 30_000 });
  await page.screenshot({ path: path.join(shots, "desktop-answer.png"), fullPage: true }); await page.locator(".source-list button").first().click(); await page.screenshot({ path: path.join(shots, "desktop-source-panel.png") });
  await page.getByText("Matriz de evidencia", { exact: true }).click(); await page.screenshot({ path: path.join(shots, "desktop-matrix.png"), fullPage: true });
  const crossCorpus = page.getByText("Cruces entre obras", { exact: true });
  if (await crossCorpus.isVisible()) { await crossCorpus.click(); await page.screenshot({ path: path.join(shots, "desktop-cross-corpus.png"), fullPage: true }); }
});
test("captures mobile drawers with real evidence", async ({ page }) => {
  test.setTimeout(90_000); await page.setViewportSize({ width: 390, height: 844 }); await login(page); await page.screenshot({ path: path.join(shots, "mobile-empty.png"), fullPage: true });
  await page.getByRole("button", { name: "Filtros" }).first().click(); await page.screenshot({ path: path.join(shots, "mobile-filters.png") }); await page.getByRole("button", { name: "Cerrar filtros" }).click();
  await page.getByTestId("research-question").fill("תשעה באב"); await page.getByTestId("research-submit").click(); await page.getByTestId("interpretation-analyze").click(); await expect(page.locator(".synthesis")).toBeVisible({ timeout: 45_000 }); await page.screenshot({ path: path.join(shots, "hebrew.png"), fullPage: true }); await page.screenshot({ path: path.join(shots, "mobile-answer.png"), fullPage: true });
  await page.getByRole("button", { name: "Fuentes", exact: true }).click(); await page.screenshot({ path: path.join(shots, "mobile-sources.png") }); await page.getByRole("button", { name: "Cerrar fuentes" }).click(); await page.getByText("Matriz de evidencia", { exact: true }).click(); await page.screenshot({ path: path.join(shots, "mobile-matrix.png"), fullPage: true });
});
const mockBase = { question: "prueba", answer_text: "Respuesta segura", answer_markdown: "## Respuesta\n\n> Evidencia", summary: "Síntesis de prueba", conversation: { conversation_id: null, turn_id: null, resolved_context: [] }, works_consulted: ["lh"], hits: [], evidence_matrix: [], cross_corpus_matrix: [], warnings: [], not_found: [], execution: { used_ai_rendering: false, duration_ms: 1 } };
test("captures partial, no-evidence and error states safely", async ({ page }) => {
  await page.setViewportSize({ width: 1280, height: 720 }); await login(page);
  await page.route("**/library/investigative-qa/v1", (route) => fulfillConfirmationPhases(route, { ...mockBase, status: "partial" })); await page.getByTestId("research-question").fill("consulta parcial"); await page.getByTestId("research-submit").click(); await page.getByTestId("interpretation-analyze").click(); await expect(page.getByText(/respuesta es parcial/)).toBeVisible(); await page.screenshot({ path: path.join(shots, "partial.png") });
  await page.unroute("**/library/investigative-qa/v1"); await page.getByRole("button", { name: /Nueva investigación/ }).first().click(); await page.route("**/library/investigative-qa/v1", (route) => fulfillConfirmationPhases(route, { ...mockBase, status: "no_evidence", answer_text: "", answer_markdown: "", summary: "Sin evidencia suficiente" })); await page.getByTestId("research-question").fill("sin evidencia"); await page.getByTestId("research-submit").click(); await page.getByTestId("interpretation-analyze").click(); await expect(page.getByText(/No se encontró evidencia suficiente/)).toBeVisible(); await page.screenshot({ path: path.join(shots, "no-evidence.png") });
  await page.unroute("**/library/investigative-qa/v1"); await page.getByRole("button", { name: /Nueva investigación/ }).first().click(); await page.route("**/library/investigative-qa/v1", async (route) => route.fulfill({ status: 500, json: { detail: "internal" } })); await page.getByTestId("research-question").fill("error recuperable"); await page.getByTestId("research-submit").click(); await expect(page.getByRole("alert")).toBeVisible(); await page.screenshot({ path: path.join(shots, "error.png") });
});
test("captures the tablet source drawer", async ({ page }) => {
  test.setTimeout(90_000); await page.setViewportSize({ width: 820, height: 1180 }); await login(page); await page.getByTestId("research-question").fill("¿Qué se dice sobre la tristeza?"); await page.getByTestId("research-submit").click(); await page.getByTestId("interpretation-analyze").click(); await expect(page.locator(".synthesis")).toBeVisible({ timeout: 30_000 }); await page.screenshot({ path: path.join(shots, "tablet-answer.png"), fullPage: true }); await page.getByRole("button", { name: "Fuentes", exact: true }).click(); await page.screenshot({ path: path.join(shots, "tablet-sources.png") });
});
