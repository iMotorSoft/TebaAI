import { expect, test, type Page } from "@playwright/test";

const email = process.env.TEBAAI_E2E_ADMIN_EMAIL;
const password = process.env.TEBAAI_E2E_ADMIN_PASSWORD;

async function login(page: Page): Promise<void> {
  await page.goto("/login");
  await page.fill("#login-email", email!);
  await page.fill("#login-password", password!);
  await page.getByRole("button", { name: "Ingresar" }).click();
  await expect(page.getByTestId("research-question")).toBeVisible({ timeout: 15_000 });
}

async function research(page: Page, question: string): Promise<Record<string, any>> {
  await page.getByTestId("research-question").fill(question);
  await page.getByTestId("research-submit").click();
  await expect(page.getByTestId("interpretation-card")).toBeVisible();
  const analyzed = page.waitForResponse((response) => {
    if (!response.url().endsWith("/library/investigative-qa/v1")) return false;
    try {
      return response.request().postDataJSON()?.phase === "analyze";
    } catch {
      return false;
    }
  });
  await page.getByTestId("interpretation-analyze").click();
  const response = await analyzed;
  expect(response.ok()).toBe(true);
  await expect(page.getByTestId("research-result-heading")).toBeVisible({ timeout: 120_000 });
  return response.json();
}

test.describe("grounded investigative intents against DEV", () => {
  test.skip(!email || !password, "TEBAAI_E2E_ADMIN_EMAIL/PASSWORD are required");

  test.beforeEach(async ({ page }) => {
    await login(page);
  });

  test("preserves Salmos 19 as a complete biblical reference", async ({ page }) => {
    const body = await research(page, "salmo 19");
    expect(body.intent).toBe("biblical_reference_lookup");
    expect(body.primary_evidence_ids).not.toHaveLength(0);
    const primary = body.hits.filter((hit: any) => body.primary_evidence_ids.includes(hit.hit_id));
    expect(primary.every((hit: any) => /salmo 19/i.test(hit.display_snippet ?? ""))).toBe(true);
    expect(primary.some((hit: any) => /proverbios 25:19/i.test(hit.display_snippet ?? ""))).toBe(false);
  });

  test("labels blood and speech as a mediated adjacent evidence chain", async ({ page }) => {
    const body = await research(page, "dame la relación entre sangre y el habla");
    const evidence = body.claims[0].evidence_ids.map(
      (id: string) => body.hits.find((hit: any) => hit.hit_id === id),
    );
    expect(new Set(evidence.map((hit: any) => hit.pdf_page))).toEqual(new Set([207, 208]));
    expect(evidence.every((hit: any) => hit.relation_type === "mediated_explicit_chain")).toBe(true);
    expect(evidence.every((hit: any) => hit.literal_relation === false)).toBe(true);
  });

  test("discovers grounded scorpion neighbors with visible literals", async ({ page }) => {
    const body = await research(page, "el término escorpión con qué está relacionado");
    expect(body.intent).toBe("discover_relations");
    expect(body.relations.length).toBeGreaterThan(0);
    for (const relation of body.relations) {
      const hit = body.hits.find((candidate: any) => candidate.hit_id === relation.primary_evidence_id);
      expect(hit.display_snippet).toMatch(/escorpi|עקרב/i);
      expect(relation.literal_subject_present).toBe(true);
      expect(relation.literal_related_concept_present).toBe(true);
    }
  });

  test("resolves Azamra as a multilingual named Breslov teaching", async ({ page }) => {
    const body = await research(page, "azamra");
    expect(body.intent).toBe("named_teaching_lookup");
    expect(body.named_topic.canonical_id).toBe("teaching.azamra");
    expect(body.named_topic.variants_searched).toEqual(
      expect.arrayContaining(["Azamra", "Azamrá", "אזמרה", "אֲזַמְּרָה", "I will sing", "cantaré"]),
    );
    expect(body.primary_evidence_ids).not.toHaveLength(0);
  });
});
