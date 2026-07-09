import { test, expect } from "@playwright/test";

const ADMIN_EMAIL = process.env.TEBAAI_E2E_ADMIN_EMAIL ?? "";
const ADMIN_PASSWORD = process.env.TEBAAI_E2E_ADMIN_PASSWORD ?? "";

const AI_OK_FIXTURE = {
  question: "Dónde se habla de ruaj y habla/palabra",
  language: "es",
  knowledge_scope_code: "breslov_primary",
  concepts: {
    concept_a: { label: "ruaj", variants: ["ruaj", "espíritu", "רוח"] },
    concept_b: { label: "habla", variants: ["habla", "palabra", "דיבור"] },
  },
  answer: {
    short_conclusion: "No se encontró una relación literal directa.",
    editorial_answer_markdown:
      "> **Sin relación literal:** la síntesis siguiente es editorial.\n\nSe encontró coocurrencia...",
    literal_relation_found: false,
    ai_inference_used: true,
    editorial_certainty: "low",
  },
  evidence_summary: { literal_phrase: 3, cooccurrence_same_chunk: 5 },
  sources: [],
  source_map: [],
  warnings: ["no_literal_relation"],
  method: {
    retrieval: ["postgresql_fts_websearch", "milvus_dense_cosine"],
    llm_model: "openai_gpt-5.4-nano",
    embedding_model: "openai_text_embedding_3_small",
    used_pg_as_canonical: true,
    used_milvus: true,
    used_ai: true,
    ai_synthesis_status: "ok",
    ai_synthesis_attempts: 1,
    fallback_used: false,
    fallback_reason: null,
    synthesis_mode: "ai",
  },
  debug: null,
};

const FALLBACK_FIXTURE = {
  question: "Qué fuentes relacionan alegría y plegaria",
  language: "es",
  knowledge_scope_code: "breslov_primary",
  concepts: {
    concept_a: { label: "alegría", variants: ["alegría", "simjá", "שמחה"] },
    concept_b: { label: "plegaria", variants: ["plegaria", "tefilá", "תפילה"] },
  },
  answer: {
    short_conclusion: "No se encontró una relación literal directa.",
    editorial_answer_markdown:
      "No se encontró una relación literal directa.\n\n---\nSíntesis determinística...",
    literal_relation_found: false,
    ai_inference_used: false,
    editorial_certainty: "low",
  },
  evidence_summary: { literal_phrase: 1, cooccurrence_same_chunk: 19 },
  sources: [
    {
      source_id: "src_test",
      document_title: "Test",
      page_number: 1,
      evidence_type: "biblical_citation",
      snippet: "test",
      retrieval_method: "fts",
      chunk_id: "abc",
      score: 0.8,
      citable: true,
      is_final_citation: true,
    },
  ],
  source_map: [],
  warnings: [
    "no_literal_relation",
    "ai_response_parse_failed: deterministic editorial fallback used",
    "deterministic_fallback: la síntesis editorial automática no pudo completarse",
  ],
  method: {
    retrieval: ["postgresql_fts_websearch"],
    llm_model: "",
    embedding_model: "openai_text_embedding_3_small",
    used_pg_as_canonical: true,
    used_milvus: false,
    used_ai: false,
    ai_synthesis_status: "failed",
    ai_synthesis_attempts: 2,
    fallback_used: true,
    fallback_reason: "llm_json_parse_error",
    synthesis_mode: "deterministic_fallback",
  },
  debug: null,
};

const EMPTY_METHOD_FIXTURE = {
  question: "test",
  language: "es",
  knowledge_scope_code: "breslov_primary",
  concepts: { concept_a: { label: "A", variants: [] }, concept_b: { label: "B", variants: [] } },
  answer: {
    short_conclusion: "Sin evidencia.",
    editorial_answer_markdown: "",
    literal_relation_found: false,
    ai_inference_used: false,
    editorial_certainty: "low",
  },
  evidence_summary: {},
  sources: [],
  source_map: [],
  warnings: [],
  method: {},
  debug: null,
};

async function doLogin(page: typeof test.prototype.page) {
  await page.goto("/login", { waitUntil: "networkidle" });
  await page.waitForTimeout(1000);
  await page.fill("#login-email", ADMIN_EMAIL);
  await page.fill("#login-password", ADMIN_PASSWORD);
  await page.getByRole("button", { name: "Ingresar" }).click();
  await expect(page.locator("text=Sesión iniciada")).toBeVisible({ timeout: 15000 });
}

async function waitForForm(page: typeof test.prototype.page) {
  const textarea = page.locator("textarea.textarea");
  await expect(textarea).toBeVisible({ timeout: 15000 });
  return textarea;
}

test.describe("Relation QA synthesis mode indicator", () => {
  test.skip(!ADMIN_EMAIL || !ADMIN_PASSWORD, "TEBAAI_E2E_ADMIN_EMAIL/PASSWORD not set");

  test("shows AI synthesis mode when synthesis_mode=ai", async ({ page }) => {
    await doLogin(page);

    // Only intercept POST (API calls), not GET (page navigation)
    await page.route("**/library/relation-qa", async (route) => {
      if (route.request().method() === "POST") {
        await route.fulfill({ json: AI_OK_FIXTURE });
      } else {
        await route.continue();
      }
    });

    await page.goto("/library/relation-qa", { waitUntil: "networkidle" });

    const textarea = await waitForForm(page);
    await textarea.fill("test question");
    await page.locator("button.btn-primary", { hasText: "Consultar" }).click();

    await expect(page.locator("text=Modo de síntesis")).toBeVisible({ timeout: 10000 });
    await expect(page.locator("text=Síntesis IA")).toBeVisible();
    await expect(page.locator("text=Estado: ok")).toBeVisible();
    await expect(page.locator("text=Intentos: 1")).toBeVisible();
  });

  test("shows deterministic fallback mode when fallback_used=true", async ({ page }) => {
    await doLogin(page);

    await page.route("**/library/relation-qa", async (route) => {
      if (route.request().method() === "POST") {
        await route.fulfill({ json: FALLBACK_FIXTURE });
      } else {
        await route.continue();
      }
    });

    await page.goto("/library/relation-qa", { waitUntil: "networkidle" });

    const textarea = await waitForForm(page);
    await textarea.fill("test question");
    await page.locator("button.btn-primary", { hasText: "Consultar" }).click();

    await expect(page.locator("text=Modo de síntesis")).toBeVisible({ timeout: 10000 });
    await expect(page.locator("text=Fallback determinístico")).toBeVisible();
    await expect(page.locator("text=Estado IA: failed")).toBeVisible();
    await expect(page.locator("text=Intentos: 2")).toBeVisible();
    await expect(page.locator("text=Motivo: llm_json_parse_error")).toBeVisible();
  });

  test("does not break when method has no synthesis fields", async ({ page }) => {
    await doLogin(page);

    await page.route("**/library/relation-qa", async (route) => {
      if (route.request().method() === "POST") {
        await route.fulfill({ json: EMPTY_METHOD_FIXTURE });
      } else {
        await route.continue();
      }
    });

    await page.goto("/library/relation-qa", { waitUntil: "networkidle" });

    const textarea = await waitForForm(page);
    await textarea.fill("test question");
    await page.locator("button.btn-primary", { hasText: "Consultar" }).click();

    await expect(page.getByRole("heading", { name: "Modo de síntesis" })).toBeVisible({ timeout: 10000 });
    await expect(page.locator("text=Modo de síntesis no informado")).toBeVisible();
  });
});
