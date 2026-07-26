import { expect, test } from "@playwright/test";
import path from "node:path";
import fs from "node:fs";
import { fulfillConfirmationPhases } from "./research-confirmation-helpers";

const email = process.env.TEBAAI_E2E_ADMIN_EMAIL;
const password = process.env.TEBAAI_E2E_ADMIN_PASSWORD;
const screenshots = path.resolve(import.meta.dirname, "../../../data/reports/breslov/2026-07-16-research-workspace-v1/screenshots");

test.skip(!email || !password, "requires configured E2E administrator credentials");

test("blood-speech claims open their explicit primary evidence", async ({ page }) => {
  test.setTimeout(120_000);
  await page.setViewportSize({ width: 1536, height: 1024 });
  await page.goto("/login");
  await expect(page.locator("astro-island:not([ssr])")).toBeAttached();
  await page.fill("#login-email", email!);
  await page.fill("#login-password", password!);
  await page.getByRole("button", { name: "Ingresar" }).click();
  await expect(page.getByTestId("research-question")).toBeVisible();

  const responsePromise = page.waitForResponse((response) => response.url().endsWith("/library/investigative-qa/v1") && response.request().method() === "POST" && response.request().postDataJSON()?.phase === "analyze");
  await page.getByTestId("research-question").fill("la relacion entre sangre y el habla");
  await page.getByTestId("research-submit").click(); await page.getByTestId("interpretation-analyze").click();
  const response = await responsePromise;
  expect(response.status()).toBe(200);
  const payload = await response.json();
  expect(payload.primary_evidence_ids.length).toBeGreaterThan(0);
  expect(payload.claims.every((claim: { evidence_ids: string[]; primary_evidence_id: string }) => claim.evidence_ids.includes(claim.primary_evidence_id))).toBe(true);
  expect(payload.primary_evidence_ids.every((id: string) => payload.hits.some((hit: { hit_id: string }) => hit.hit_id === id))).toBe(true);

  const active = page.locator(".source-detail");
  const firstClaim = payload.claims.find((claim: { primary_evidence_id: string }) => claim.primary_evidence_id === payload.primary_evidence_ids[0]);
  const firstPrimary = payload.hits.find((hit: { hit_id: string }) => hit.hit_id === payload.primary_evidence_ids[0]);
  const strengthLabels: Record<string, string> = { strong: "Fuerte", medium: "Media", weak: "Débil", insufficient: "Insuficiente" };
  expect(firstPrimary.evidence_strength).toBe(firstClaim.strength);
  await expect(active).toHaveAttribute("data-evidence-id", payload.primary_evidence_ids[0], { timeout: 30_000 });
  await expect(active).not.toContainText(/shamir|herramientas de hierro/i);
  await expect(active).toContainText("Respaldo directo del claim");
  await expect(active).toContainText(strengthLabels[firstClaim.strength]);
  await expect(page.getByText("pdf page null for kitzur chunk", { exact: false })).toHaveCount(0);
  await expect(page.getByText("La página no está disponible en el registro fuente", { exact: true }).first()).toBeVisible();
  expect(payload.hits[0].matched_concepts.map((value: string) => value.normalize("NFD").replace(/\p{Diacritic}/gu, ""))).toEqual(expect.arrayContaining(["sangre", "habla"]));
  expect(payload.hits[0].snippet.startsWith("iduría")).toBe(false);
  await page.screenshot({ path: path.join(screenshots, "blood-speech-after.png"), fullPage: true });
  await page.locator(".primary-evidence").screenshot({ path: path.join(screenshots, "primary-evidence.png") });
  await active.screenshot({ path: path.join(screenshots, "snippet-boundary.png") });
  const translatedWarning = page.getByText("La página no está disponible en el registro fuente", { exact: true }).first();
  await translatedWarning.screenshot({ path: path.join(screenshots, "warning-translated.png") });
  const additional = page.locator(".sources .additional-matches");
  await additional.scrollIntoViewIfNeeded();
  await additional.locator("summary").click();
  await additional.screenshot({ path: path.join(screenshots, "additional-literal-matches.png") });

  if (payload.claims.length > 1) {
    const secondClaim = page.locator(".claim-list li").nth(1);
    const secondClaimButton = secondClaim.getByRole("button", { name: /Ver fuente de:/ });
    const secondPrimary = payload.claims[1].primary_evidence_id;
    await secondClaimButton.click();
    await expect(active).toHaveAttribute("data-evidence-id", secondPrimary);
    await page.screenshot({ path: path.join(screenshots, "claim-source-selected.png"), fullPage: true });
  }

  await page.setViewportSize({ width: 390, height: 844 });
  await page.locator(".claim-list li").first().getByRole("button", { name: /Ver fuente de:/ }).click();
  await expect(page.locator(".sources.open")).toBeVisible();
  await expect(page.locator(".sources.open .source-detail")).toHaveAttribute("data-evidence-id", payload.claims[0].primary_evidence_id);
  await page.screenshot({ path: path.join(screenshots, "mobile-source-selection.png"), fullPage: false });
});

test("records the original mismatched primary source for the before report", async ({ page }) => {
  const beforePath = path.resolve(import.meta.dirname, "../../../data/reports/breslov/2026-07-16-research-workspace-v1/blood_speech_case_before.json");
  const before = JSON.parse(fs.readFileSync(beforePath, "utf8"));
  const first = before.hits[0];
  first.snippet = first.quote;
  first.literal_strength = "strong";
  first.evidence_strength = "strong";
  first.relation_relevance = "direct_relation";
  first.matched_concepts = ["sangre"];
  first.is_primary = true;
  before.claims = [{ claim_id: "before_claim", text: "La relación entre sangre y habla", strength: "strong", evidence_ids: [first.hit_id], primary_evidence_id: first.hit_id }];
  before.primary_evidence_ids = [first.hit_id];
  before.evidence_counts = { primary: 1, contextual: 0, additional_literal: before.hits.length - 1 };
  await page.route("**/library/investigative-qa/v1", (route) => fulfillConfirmationPhases(route, before));
  await page.goto("/login");
  await expect(page.locator("astro-island:not([ssr])")).toBeAttached();
  await page.fill("#login-email", email!);
  await page.fill("#login-password", password!);
  await page.getByRole("button", { name: "Ingresar" }).click();
  await page.getByTestId("research-question").fill("la relacion entre sangre y el habla");
  await page.getByTestId("research-submit").click(); await page.getByTestId("interpretation-analyze").click();
  await expect(page.locator(".source-detail")).toContainText(/shamir/i);
  await page.screenshot({ path: path.join(screenshots, "blood-speech-before.png"), fullPage: true });
});
