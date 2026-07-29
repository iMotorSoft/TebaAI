import { expect, test, type Page } from "@playwright/test";

const adminEmail = process.env.TEBAAI_E2E_ADMIN_EMAIL ?? "";
const adminPassword = process.env.TEBAAI_E2E_ADMIN_PASSWORD ?? "";
const guestEmail = process.env.TEBAAI_E2E_GUEST_EMAIL ?? "guest@tebaai.live";
const guestPassword = process.env.TEBAAI_E2E_GUEST_PASSWORD ?? "";
const endpoint = "/library/investigative-qa/v1";

async function login(page: Page, email: string, password: string) {
  await page.goto("/login");
  await page.fill("#login-email", email);
  await page.fill("#login-password", password);
  await page.getByRole("button", { name: "Ingresar" }).click();
  await expect(page).toHaveURL(/\/research\/?$/);
}

async function ask(page: Page, question: string) {
  const responsePromise = page.waitForResponse((response) =>
    response.url().endsWith(endpoint)
    && response.request().method() === "POST"
    && !response.request().postDataJSON()?.phase
  );
  await page.getByTestId("research-question").fill(question);
  await page.getByTestId("research-submit").click();
  const response = await responsePromise;
  expect(response.status()).toBe(200);
  const body = await response.json();
  await expect(page.getByTestId("research-result-heading")).toBeVisible({
    timeout: 120_000,
  });
  return body;
}

test.describe("simple grounded RAG DEV gate", () => {
  test.skip(!adminEmail || !adminPassword, "admin E2E credentials are required");

  test("admin runs the four critical queries with canonical evidence", async ({ page }) => {
    test.setTimeout(240_000);
    await login(page, adminEmail, adminPassword);
    for (const question of [
      "Relación sangre y habla",
      "salmo 19",
      "el término escorpión con qué está relacionado",
      "azamra",
    ]) {
      const body = await ask(page, question);
      expect(body.pipeline).toBe("simple_rag");
      expect(body.original_query).toBe(question);
      expect(["complete", "partial", "degraded"]).toContain(body.research_status);
      expect(body.answer_markdown.length).toBeGreaterThan(0);
      expect(body.evidence.length).toBeGreaterThan(0);
      expect(body.evidence[0]).toEqual(expect.objectContaining({
        evidence_id: expect.any(String),
        chunk_id: expect.any(String),
        work: expect.any(String),
        language: expect.any(String),
        markdown: expect.any(String),
      }));
      expect(body.retrieval.semantic_status).toBe("ok");
      expect(body.retrieval.literal_status).toBe("ok");
      if (question === "Relación sangre y habla") {
        expect(body.evidence.some((item: { pdf_page: number | null }) =>
          item.pdf_page === 207 || item.pdf_page === 208
        )).toBe(true);
      }
      await page.locator(".desktop-action").filter({
        hasText: "Nueva investigación",
      }).click();
    }
    await page.getByRole("button", { name: "Cerrar sesión" }).first().click();
    await expect(page).toHaveURL(/\/login\/?$/);
  });

  test("admin resolves equivalent Hebrew PDF forms to the same canonical source", async ({ page }) => {
    test.setTimeout(240_000);
    await login(page, adminEmail, adminPassword);
    let canonical: { document_id: string; pdf_page: number; section: string } | null = null;
    for (const question of [
      "וּמִצְרַיִם נָסִים לִקְרָאתוֹ",
      "ומצרים נסים לקראתו",
      "וּמ ִ צְ ר ַ יִם נָ סִ ים לִ ק ְר ָ אתו",
    ]) {
      const body = await ask(page, question);
      expect(body.original_query).toBe(question);
      expect(body.research_status).toBe("complete");
      expect(body.retrieval.literal_hits).toBeGreaterThan(0);
      expect(body.retrieval.primary_match_type).toBe("hebrew_exact_normalized");
      const primary = body.hits.find((hit: { is_primary: boolean }) => hit.is_primary);
      expect(primary).toEqual(expect.objectContaining({
        work_title: "Likutey Moharán I",
        pdf_page: 14,
        printed_page: 4,
        section: "Torá 7:1",
        match_kind: "hebrew_exact_normalized",
      }));
      expect(primary.quote.replace(/[^א-ת]/gu, "")).toContain("ומצריםנסיםלקראתו");
      const identity = {
        document_id: primary.document_id,
        pdf_page: primary.pdf_page,
        section: primary.section,
      };
      if (canonical) expect(identity).toEqual(canonical);
      else canonical = identity;
      const sources = page.locator('aside[aria-label="Fuentes del turno"]');
      await expect(sources.getByText("Coincidencia normalizada", { exact: false })).toBeVisible();
      await expect(sources.getByText("Torá 7:1", { exact: false })).toBeVisible();
      await page.locator(".desktop-action").filter({
        hasText: "Nueva investigación",
      }).click();
    }
    await page.getByRole("button", { name: "Cerrar sesión" }).first().click();
    await expect(page).toHaveURL(/\/login\/?$/);
  });

  test("mobile RTL keeps answer and source panel usable", async ({ page }) => {
    test.setTimeout(120_000);
    await page.setViewportSize({ width: 390, height: 844 });
    await login(page, adminEmail, adminPassword);
    const body = await ask(page, "וּמִצְרַיִם נָסִים לִקְרָאתוֹ");
    expect(body.original_query).toBe("וּמִצְרַיִם נָסִים לִקְרָאתוֹ");
    expect(body.hits[0].work_title).toBe("Likutey Moharán I");
    await expect(page.locator(".user-turn h2")).toHaveAttribute("dir", "rtl");
    await page.getByRole("button", { name: "Fuentes", exact: true }).click();
    await expect(page.locator('aside[aria-label="Fuentes del turno"]')).toBeVisible();
    await expect(page.getByRole("button", { name: "Cerrar fuentes" })).toBeVisible();
  });

  test("degraded state explains the failed and fallback layers", async ({ page }) => {
    await login(page, adminEmail, adminPassword);
    await page.route(`**${endpoint}`, async (route) => {
      await route.fulfill({
        status: 200,
        json: {
          pipeline: "simple_rag",
          status: "partial",
          research_status: "degraded",
          original_query: "consulta degradada",
          answer_text: "Respuesta desde búsqueda literal.",
          answer_markdown: "Respuesta desde búsqueda literal. [ev-aaaaaaaaaaaaaaaa]",
          summary: "1 fuente principal.",
          conversation: { conversation_id: null, turn_id: null },
          works_consulted: ["kitzur"],
          hits: [{
            hit_id: "ev-aaaaaaaaaaaaaaaa",
            evidence_id: "ev-aaaaaaaaaaaaaaaa",
            work_code: "kitzur",
            work_title: "KITZUR",
            pdf_page: 10,
            printed_page: null,
            quote: "Markdown canónico",
            snippet: "Markdown canónico",
            evidence_type: "canonical_markdown",
            literal_strength: "strong",
            evidence_strength: "strong",
            relation_relevance: "direct_relation",
            matched_terms: [],
            matched_concepts: [],
            is_primary: true,
            source_layer: "unknown",
            warnings: [],
          }],
          claims: [{
            claim_id: "claim",
            text: "Respuesta grounded",
            strength: "strong",
            evidence_ids: ["ev-aaaaaaaaaaaaaaaa"],
            primary_evidence_id: "ev-aaaaaaaaaaaaaaaa",
          }],
          relations: [],
          primary_evidence_ids: ["ev-aaaaaaaaaaaaaaaa"],
          evidence_counts: { primary: 1, contextual: 0, additional_literal: 0 },
          evidence_matrix: [{
            work_code: "kitzur",
            hits: 1,
            primary_hits: 1,
            contextual_hits: 0,
            additional_literal_hits: 0,
          }],
          cross_corpus_matrix: [],
          warnings: [
            "La búsqueda semántica no estuvo disponible; se utilizó búsqueda literal.",
          ],
          not_found: [],
          execution: {},
          retrieval: { semantic_status: "failed", literal_status: "ok" },
          processing: { fallback_used: true },
        },
      });
    });
    await ask(page, "consulta degradada");
    await expect(page.locator('[data-research-status="degraded"]')).toBeVisible();
    await expect(page.getByText(/búsqueda semántica no estuvo disponible/i)).toBeVisible();
  });
});

test.describe("simple RAG guest read-only", () => {
  test.skip(!guestPassword, "guest E2E credentials are required");

  test("guest can research, cannot administer, and can logout", async ({ page }) => {
    test.setTimeout(120_000);
    await login(page, guestEmail, guestPassword);
    const body = await ask(page, "ומצרים נסים לקראתו");
    expect(body.evidence.length).toBeGreaterThan(0);
    expect(body.hits.some((hit: { work_title: string; section: string }) =>
      hit.work_title === "Likutey Moharán I" && hit.section === "Torá 7:1"
    )).toBe(true);
    await page.goto("/admin/users");
    await expect(page).toHaveURL(/\/research\/?$/);
    await expect(page.getByRole("button", { name: "Crear usuario" })).toHaveCount(0);
    await page.getByRole("button", { name: "Cerrar sesión" }).first().click();
    await expect(page).toHaveURL(/\/login\/?$/);
  });
});
