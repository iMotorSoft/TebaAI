import { describe, expect, it } from "vitest";
import { makeAnalyzeRequest, makeInterpretRequest, makeRequest, normalizeInterpretationResponse, normalizeResearchResponse, selectInitialEvidence, WORKS } from "./investigativeQaClient.ts";
const base = { status: "ok", answer_text: "texto", conversation: { conversation_id: null, turn_id: null }, hits: [], evidence_matrix: [], cross_corpus_matrix: [] };
const hit = (id: string, relevance = "single_term_literal") => ({ hit_id: id, work_code: "kitzur", work_title: "Kitzur", pdf_page: null, printed_page: null, quote: "texto canónico", snippet: "…texto canónico", evidence_type: "literal_same_page", literal_strength: "strong", evidence_strength: relevance === "direct_relation" ? "strong" : "insufficient", relation_relevance: relevance, matched_terms: ["sangre"], matched_concepts: ["sangre"], is_primary: relevance === "direct_relation", source_layer: "unknown", warnings: [] });
describe("research contract", () => {
  it("normalizes optional arrays and preserves null", () => { const r = normalizeResearchResponse(base); expect(r.hits).toEqual([]); expect(r.warnings).toEqual([]); expect(r.conversation.conversation_id).toBeNull(); expect(r.answer_markdown).toBe("texto"); });
  it("rejects unknown states and missing answers", () => { expect(() => normalizeResearchResponse({ ...base, status: "broken" })).toThrow(); expect(() => normalizeResearchResponse({ ...base, answer_text: undefined })).toThrow(); });
  it("rejects malformed structured evidence", () => { expect(() => normalizeResearchResponse({ ...base, hits: [{ quote: "missing identity" }] })).toThrow(/evidencia incompatible/); expect(() => normalizeResearchResponse({ ...base, evidence_matrix: [{ work_code: "lh", hits: "2" }] })).toThrow(/matriz incompatible/); });
  it("allowlists values and truncates history", () => { const history = Array.from({ length: 20 }, (_, i) => ({ question: String(i) })); const r = makeRequest("q", { works: ["lh", "bad"], languages: ["es", "xx" as never], thematic: false, maxHits: 7 }, history, null, null); expect(r.works).toEqual(["lh"]); expect(r.languages).toEqual(["es"]); expect(r.max_hits_per_work).toBe(10); expect(r.conversation.history).toHaveLength(15); expect(r.include_audit).toBe(false); });
  it("prevents empty filters", () => { const r = makeRequest("q", { works: [], languages: [], thematic: true, maxHits: 5 }, [], null, null); expect(r.works).toEqual([...WORKS]); expect(r.languages).toEqual(["es"]); });
  it("selects explicit primary evidence instead of the first literal hit", () => { const r = normalizeResearchResponse({ ...base, hits: [hit("noise"), hit("primary", "direct_relation")], claims: [{ claim_id: "claim_1", text: "relación", strength: "strong", evidence_ids: ["primary"], primary_evidence_id: "primary" }], primary_evidence_ids: ["primary"], evidence_counts: { primary: 1, contextual: 0, additional_literal: 1 } }); expect(selectInitialEvidence(r)).toBe("primary"); });
  it("rejects invented claim evidence IDs", () => { expect(() => normalizeResearchResponse({ ...base, hits: [hit("real")], claims: [{ claim_id: "claim_1", text: "relación", evidence_ids: ["invented"], primary_evidence_id: "invented" }], primary_evidence_ids: ["invented"] })).toThrow(/trazabilidad/); });
  it("rejects a primary ID that is not associated with its claim", () => { expect(() => normalizeResearchResponse({ ...base, hits: [hit("one"), hit("two")], claims: [{ claim_id: "claim_1", text: "relación", evidence_ids: ["one"], primary_evidence_id: "two" }], primary_evidence_ids: ["two"] })).toThrow(/trazabilidad/); });
  it("never promotes contextual evidence when no primary passed validation", () => { const r = normalizeResearchResponse({ ...base, hits: [hit("noise"), hit("context", "same_fragment_both_terms")] }); expect(selectInitialEvidence(r)).toBeNull(); });
  it("rejects insufficient evidence declared as primary", () => { expect(() => normalizeResearchResponse({ ...base, status: "ok", hits: [hit("noise")], claims: [{ claim_id: "bad", text: "no probado", strength: "insufficient", evidence_ids: ["noise"], primary_evidence_id: "noise" }], primary_evidence_ids: ["noise"] })).toThrow(/principal/); });
  it("preserves literal intent and physical PDF traceability", () => { const source = { ...hit("lmi-node", "direct_relation"), work_code: "lmi", work_title: "Likutey Moharán I — edición española", pdf_page: 96, printed_page: 76, document_id: "document", page_anchor_id: "anchor", physical_file_name: "physical.pdf", source_sha256: "abc", section: "LIKUTEY MOHARÁN #2:7", literal_match_kind: "no_niqqud", language_match: "exact", retrieval_tier: 0 }; const r = normalizeResearchResponse({ ...base, intent: "literal_lookup", hits: [source], claims: [{ claim_id: "literal", text: "Se encontró", strength: "strong", evidence_ids: ["lmi-node"], primary_evidence_id: "lmi-node" }], primary_evidence_ids: ["lmi-node"], evidence_counts: { primary: 1, contextual: 0, additional_literal: 0 } }); expect(r.intent).toBe("literal_lookup"); expect(r.hits[0]).toMatchObject({ document_id: "document", page_anchor_id: "anchor", pdf_page: 96, printed_page: 76, section: "LIKUTEY MOHARÁN #2:7" }); });
  it("preserves the validated multilingual interpretation and fallback audit", () => { const interpretation = { language: "he", secondary_languages: [], intent: "concept_lookup", instruction_language: "he", instruction: "איפה נמצא", query_subjects: [{ kind: "concept", raw: "העקרב", normalized: "עקרב", language: "he", script: "hebrew", variants: [{ value: "העקרב", kind: "exact" }, { value: "עקרב", kind: "definite_article_removed" }] }], literal_phrases: [], relations: [], requested_works: [], confidence: 0.95, ai_used: false, fallback_used: true }; const r = normalizeResearchResponse({ ...base, intent: "concept_lookup", interpretation }); expect(r.interpretation).toEqual(interpretation); expect(r.interpretation?.query_subjects[0]).toMatchObject({ raw: "העקרב", normalized: "עקרב" }); expect(r.interpretation?.fallback_used).toBe(true); });
  it("keeps raw audit text separate from the sanitized display snippet", () => {
    const source = { ...hit("lh", "direct_relation"), snippet: "\u0080<#>raw corrupto", paragraph_text: "", display_snippet: "Texto limpio: servir a HaShem por la noche", raw_snippet: "\u0080<#>raw corrupto", snippet_sanitized: true };
    const r = normalizeResearchResponse({ ...base, hits: [source], claims: [{ claim_id: "literal", text: "Se encontró", strength: "strong", evidence_ids: ["lh"], primary_evidence_id: "lh" }], primary_evidence_ids: ["lh"] });
    expect(r.hits[0].display_snippet).toBe("Texto limpio: servir a HaShem por la noche");
    expect(r.hits[0].paragraph_text).toBe("");
    expect(r.hits[0].raw_snippet).toContain("<#>");
  });
  it("preserves named-topic identity and strong direct match invariants", () => {
    const source = { ...hit("tisha", "direct_relation"), work_code: "lm_xv", work_title: "Likutey Moharán XV KDP", pdf_page: 262, physical_pdf_page: 262, printed_page: 248, section: "LIKUTEY MOHARÁN II #85:2", literal_match_kind: "named_topic_alias", match_kind: "named_topic_alias", direct_support: true, match_strength: "strong", single_term: false, canonical_topic_id: "jewish_calendar.tisha_beav", matched_variant: "Tisha beAv" };
    const named_topic = { canonical_id: "jewish_calendar.tisha_beav", canonical_label: "Tishá BeAv", topic_type: "jewish_calendar_observance", matched_alias: "Tisha B'Av", alias_match_kind: "exact_alias", match_language: "en", match_script: "Latin", variants_searched: ["Tisha B'Av", "Tisha beAv", "9 de Av", "תשעה באב"] };
    const r = normalizeResearchResponse({ ...base, named_topic, query_understanding: { original_query: "Tisha B'Av", intent: "concept_lookup", operation: "find_named_topic", subject_type: "named_topic", subject_raw: "Tisha B'Av", subject_canonical: "Tishá BeAv", ai_used: false, ai_accepted: false, fallback_used: true, requires_clarification: false }, hits: [source], claims: [{ claim_id: "topic", text: "Interpreté la consulta", strength: "strong", evidence_ids: ["tisha"], primary_evidence_id: "tisha" }], primary_evidence_ids: ["tisha"] });
    expect(r.named_topic?.canonical_label).toBe("Tishá BeAv");
    expect(r.query_understanding?.subject_raw).toBe("Tisha B'Av");
    expect(r.hits[0]).toMatchObject({ literal_match_kind: "named_topic_alias", direct_support: true, match_strength: "strong", single_term: false });
  });
});

describe("pre-retrieval interpretation confirmation", () => {
  const interpretation = {
    phase: "interpretation" as const, status: "awaiting_confirmation" as const,
    interpretation_id: "stable-id", conversation_id: "conversation-id",
    original_query: "tisha beav",
    display_interpretation: "Interpreté que desea investigar referencias sobre Tishá BeAv.",
    query_understanding: {
      original_query: "tisha beav", intent: "concept_lookup" as const,
      operation: "find_named_topic",
      instruction_span: null, subject_span: "tisha beav",
      subject: { raw: "tisha beav", canonical: "Tishá BeAv", normalized: "tisha beav", subject_type: "named_topic" },
      typo_resolution: null, reason_codes: [],
      confidence: .98, ai_used: true, fallback_used: false,
    },
    actions: ["analyze", "modify"] as ["analyze", "modify"],
    warnings: [], expires_at: null, execution: { retrieval_executed: false },
  };
  const filters = { works: ["lm_xv"], languages: ["es"] as ("es" | "en" | "he")[], thematic: true, maxHits: 10 };

  it("accepts exactly analyze and modify", () => {
    expect(normalizeInterpretationResponse(interpretation).actions).toEqual(["analyze", "modify"]);
    expect(() => normalizeInterpretationResponse({ ...interpretation, actions: ["continue", "modify"] })).toThrow();
    expect(() => normalizeInterpretationResponse({ ...interpretation, actions: ["analyze", "modify", "cancel"] })).toThrow();
  });

  it("separates interpret and analyze payloads", () => {
    const interpret = makeInterpretRequest("tisha beav", filters, [], "conversation-id");
    expect(interpret.phase).toBe("interpret");
    expect(interpret.interpretation_id).toBeUndefined();
    const analyze = makeAnalyzeRequest(interpretation, filters, []);
    expect(analyze.phase).toBe("analyze");
    expect(analyze.interpretation_id).toBe("stable-id");
    expect(analyze.idempotency_key).toBe("analysis:stable-id");
  });

  it("marks the previous interpretation as superseded", () => {
    const request = makeInterpretRequest("relación entre Tishá BeAv y los veintiún días", filters, [], "conversation-id", "old-id");
    expect(request.supersedes_interpretation_id).toBe("old-id");
  });

  it("preserves validated relational spans without accepting extra actions", () => {
    const relational = normalizeInterpretationResponse({
      ...interpretation,
      original_query: "azamra la relaciones que tiene",
      display_interpretation: "Interpreté que desea investigar con qué conceptos se relaciona Azamra.",
      query_understanding: {
        ...interpretation.query_understanding,
        original_query: "azamra la relaciones que tiene",
        intent: "concept_cooccurrence",
        operation: "find_related_concepts",
        instruction_span: "la relaciones que tiene",
        subject_span: "azamra",
        subject: { raw: "azamra", canonical: "Azamra", normalized: "azamra", subject_type: "conceptual_term" },
        typo_resolution: { applied: true, original_fragment: "la relaciones", interpreted_as: "las relaciones", reason: "article_number_agreement", confidence: "high" },
        reason_codes: ["open_relational_query_single_subject"],
      },
    });
    expect(relational.query_understanding.subject).toMatchObject({ raw: "azamra", canonical: "Azamra" });
    expect(relational.actions).toEqual(["analyze", "modify"]);
  });
});
