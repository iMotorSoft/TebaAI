import { API_BASE_URL, API_ROUTES } from "../global.js";

export const WORKS = ["kitzur", "lmi", "lmii", "lh", "lm_xv", "potencia_plegaria"] as const;
export type Language = "es" | "en" | "he";
export interface ResearchRequest { question: string; phase?: "legacy" | "interpret" | "analyze"; interpretation_id?: string; supersedes_interpretation_id?: string; idempotency_key?: string; conversation: { conversation_id: string | null; turn_id: string | null; history: Array<{ question: string }> }; works: string[]; languages: Language[]; include_thematic: boolean; include_audit: false; min_evidence: "literal"; max_hits_per_work: number; return_markdown: true; return_json: true; ai: { enabled: true; model: "openai_gpt-5.4-nano" }; }
export type ResearchStatus = "complete" | "partial" | "degraded" | "no_evidence";
export type RelationRelevance = "direct_relation" | "same_fragment_both_terms" | "same_page_both_terms" | "same_section_relation" | "single_term_literal" | "thematic_parallel" | "inferred_relation" | "unrelated_literal_noise";
export const SOURCE_LAYERS = ["rebbe_lesson_text", "biblical_quote_in_lesson", "rabbinic_quote_in_lesson", "editorial_translation", "editorial_commentary", "editorial_note", "footnote", "source_reference", "section_heading", "page_heading", "introduction", "unknown"] as const;
export type SourceLayer = typeof SOURCE_LAYERS[number];
export interface ParallelText { language: Language; source_layer: SourceLayer; text: string; linked_to_evidence_id: string; link_type: "parallel_translation"; physical_pdf_page: number | null; printed_page: number | null; }
export type AuthorQuoteStatus = "confirmed_author_text" | "confirmed_translated_author_text" | "editorial_paraphrase" | "editorial_commentary" | "translator_note" | "footnote_reference" | "not_confirmed" | "not_applicable";
export type LiteralMatchKind = "none" | "exact_phrase" | "normalized" | "no_niqqud" | "single_term" | "semantic" | "named_topic_exact" | "named_topic_normalized" | "named_topic_alias" | "named_topic_translation" | "named_topic_hebrew_equivalent" | "named_topic_partial" | "structural_heading_exact" | "structural_heading_normalized" | "structural_heading_accent_folded" | "structural_heading_all_tokens_ordered" | "structural_heading_all_tokens_proximity" | "structural_heading_partial";
export type RelationType = "direct_literal" | "direct_paraphrase" | "mediated_explicit_chain" | "same_fragment_cooccurrence" | "same_page" | "same_section" | "thematic_parallel" | "AI_grounded_inference" | "none";
export interface Hit { hit_id: string; work_code: string; work_title: string; pdf_page: number | null; physical_pdf_page: number | null; printed_page: number | null; embedded_page_marker?: string | null; quote: string; snippet: string; match_text: string; sentence_text: string; paragraph_text: string; context_before: string; context_after: string; language: Language; direction: "ltr" | "rtl"; display_quote?: string | null; display_snippet?: string | null; display_normalization?: string | null; evidence_type: string; literal_strength: "strong" | "medium" | "weak"; evidence_strength: "strong" | "medium" | "weak" | "insufficient"; relation_relevance: RelationRelevance; relation_type: RelationType; relation_strength: "high" | "medium" | "low" | "none"; literal_relation: boolean; inference_required: boolean; matched_terms: string[]; matched_concepts: string[]; is_primary: boolean; source_layer: SourceLayer; source_layer_confidence: "high" | "medium" | "low"; source_layer_rationale: string; is_original_language: boolean; is_primary_language_match: boolean; is_translation: boolean; is_editorial_commentary: boolean; parallel_texts: ParallelText[]; search_record_type?: string; zone_type?: string | null; relation_level?: string; language_match: "exact" | "primary" | "secondary" | "fallback"; literal_match_kind: LiteralMatchKind; match_kind?: string; direct_support?: boolean; match_strength?: "strong" | "medium" | "weak" | "insufficient"; single_term?: boolean; canonical_topic_id?: string | null; matched_variant?: string | null; match_language?: string | null; match_script?: "Latin" | "Hebrew" | null; retrieval_tier: number; warnings: string[]; document_id?: string | null; physical_file_name?: string | null; source_sha256?: string | null; page_anchor_id?: string | null; content_node_id?: string | null; associated_chunk_id?: string | null; heading_original?: string | null; heading_normalized?: string | null; parent_zone_id?: string | null; evidence_id?: string | null; section?: string | null; author_quote_status?: AuthorQuoteStatus; attribution_label?: string; raw_snippet?: string; snippet_sanitized?: boolean; sanitization_reason_codes?: string[]; }
export interface Claim { claim_id: string; text: string; strength: "strong" | "medium" | "weak" | "insufficient"; evidence_ids: string[]; primary_evidence_id: string; }
export interface EvidenceCounts { primary: number; contextual: number; additional_literal: number; }
export interface MatrixRow { work_code: string; hits: number; primary_hits?: number; contextual_hits?: number; additional_literal_hits?: number; concept?: string; evidence_type?: string; evidence_strength?: string; pdf_page?: number | null; relation_type?: string; }
export type ResearchIntent = "literal_lookup" | "concept_lookup" | "concept_cooccurrence" | "discover_relations" | "relation_query" | "biblical_reference_lookup" | "named_teaching_lookup" | "translation_or_explanation" | "reference_lookup" | "structural_reference_lookup" | "location_lookup" | "follow_up" | "source_layer_question" | "book_scope_query" | "source_request" | "comparison_query" | "unknown";
export interface InterpretedSubject { kind: "concept" | "reference" | "named_topic"; raw: string; normalized: string; language: string; script: string; variants: Array<{ value: string; kind: string }>; subject_type?: string | null; topic_type?: string | null; canonical?: string | null; canonical_id?: string | null; }
export interface QueryInterpretation { language: string; secondary_languages: string[]; intent: ResearchIntent; instruction_language: string; instruction?: string | null; instruction_span?: string | null; subject_span?: string | null; query_subjects: InterpretedSubject[]; literal_phrases: Array<{ raw?: string; text?: string; normalized?: string; search_normalized?: string; language: string }>; relations: Array<{ left: InterpretedSubject; right: InterpretedSubject; relation_type: string }>; biblical_reference?: { book: "Psalms"; book_label: string; chapter: number; verse_start: number | null; verse_end: number | null; language: Language; variants: string[] } | null; requested_works: string[]; confidence: number; ai_used: boolean; fallback_used: boolean; }
export interface SuggestionAlternative { label: string; type: string; }
export interface RelatedConcept { label: string; relation_type: string; }
export interface QueryResolution { original_query: string; normalized_query: string; exact_match: boolean; suggestion_applied: boolean; suggested_query: string | null; suggestion_type: string | null; confidence: number | null; alternatives: SuggestionAlternative[]; related_concepts: RelatedConcept[]; }
export interface QueryUnderstanding { original_query: string; intent: ResearchIntent; operation: string | null; subject_type: string | null; subject_raw: string | null; subject_canonical: string | null; ai_used: boolean; ai_accepted: boolean; fallback_used: boolean; requires_clarification: boolean; }
export interface ConfirmableQueryUnderstanding {
  original_query: string;
  intent: ResearchIntent;
  operation: string;
  instruction_span: string | null;
  subject_span: string | null;
  subject: { raw: string; canonical: string; normalized: string; subject_type: string };
  typo_resolution: { applied: boolean; original_fragment: string; interpreted_as: string; reason: string; confidence: string } | null;
  reason_codes: string[];
  confidence: number;
  ai_used: boolean;
  fallback_used: boolean;
}
export interface InterpretationResponse {
  phase: "interpretation";
  status: "awaiting_confirmation";
  interpretation_id: string;
  conversation_id: string;
  original_query: string;
  display_interpretation: string;
  query_understanding: ConfirmableQueryUnderstanding;
  actions: ["analyze", "modify"];
  warnings: string[];
  expires_at: number | null;
  execution: Record<string, unknown>;
}
export interface NamedTopic { canonical_id: string; canonical_label: string; topic_type: string; matched_alias: string; alias_match_kind: string; match_language: string; match_script: "Latin" | "Hebrew"; variants_searched: string[]; }
export interface ValidatedRelation { related_concept: string; statement: string; relation_type: RelationType; strength: "high" | "medium" | "low"; evidence_ids: string[]; primary_evidence_id: string; literal_subject_present: boolean; literal_related_concept_present: boolean; inference_required: boolean; }
export interface ResearchResponse { status: "ok" | "partial" | "no_evidence"; research_status: ResearchStatus; original_query: string; pipeline?: string; intent?: ResearchIntent; target_evidence_id?: string | null; same_primary_evidence?: boolean | null; interpretation?: QueryInterpretation; query_resolution?: QueryResolution; query_understanding?: QueryUnderstanding; named_topic?: NamedTopic | null; answer_text: string; answer_markdown: string; summary: string; conversation: { conversation_id: string | null; turn_id: string | null; resolved_context?: string[] }; works_consulted: string[]; hits: Hit[]; claims: Claim[]; relations: ValidatedRelation[]; primary_evidence_ids: string[]; evidence_counts: EvidenceCounts; evidence_matrix: MatrixRow[]; cross_corpus_matrix: MatrixRow[]; warnings: string[]; not_found: string[]; execution: Record<string, unknown>; retrieval?: Record<string, unknown>; processing?: Record<string, unknown>; }
const array = <T>(value: unknown): T[] => Array.isArray(value) ? value as T[] : [];
const string = (value: unknown, fallback = ""): string => typeof value === "string" ? value : fallback;
const relevance = ["direct_relation", "same_fragment_both_terms", "same_page_both_terms", "same_section_relation", "single_term_literal", "thematic_parallel", "inferred_relation", "unrelated_literal_noise"];
const relationTypes: RelationType[] = ["direct_literal", "direct_paraphrase", "mediated_explicit_chain", "same_fragment_cooccurrence", "same_page", "same_section", "thematic_parallel", "AI_grounded_inference", "none"];
const legacyRetrievalLayers = ["chunk", "page_literal", "fine_zone", "main_text_spanish", "main_text_hebrew", "mixed_hebrew_spanish", "note_or_source_candidate", "note_source_unit", "nominal_reference"];
const safeText = (value: unknown): string => string(value).replace(/<\/?(?:script|iframe|object|embed|style)\b[^>]*>/gi, "");
function normalizeHits(value: unknown): Hit[] {
  return array<unknown>(value).map((item) => {
    if (!item || typeof item !== "object") throw new Error("La respuesta contiene una evidencia incompatible.");
    const hit = item as Record<string, unknown>;
    if (typeof hit.hit_id !== "string" || typeof hit.work_code !== "string" || typeof hit.work_title !== "string" || typeof hit.quote !== "string" || !["strong", "medium", "weak", "insufficient"].includes(String(hit.evidence_strength))) throw new Error("La respuesta contiene una evidencia incompatible.");
    if (hit.pdf_page != null && typeof hit.pdf_page !== "number") throw new Error("La respuesta contiene una página incompatible.");
    const sourceLayer = SOURCE_LAYERS.includes(hit.source_layer as SourceLayer) ? hit.source_layer as SourceLayer : legacyRetrievalLayers.includes(String(hit.source_layer)) ? "unknown" : null;
    if (!sourceLayer) throw new Error("La respuesta contiene una capa editorial incompatible.");
    const confidence = ["high", "medium", "low"].includes(String(hit.source_layer_confidence)) ? hit.source_layer_confidence as Hit["source_layer_confidence"] : "low";
    const relationRelevance = typeof hit.relation_relevance === "string" && relevance.includes(hit.relation_relevance) ? hit.relation_relevance : "single_term_literal";
    const languageMatch = ["exact", "primary", "secondary", "fallback"].includes(String(hit.language_match)) ? hit.language_match : "fallback";
    const literalMatchKind = ["none", "exact_phrase", "normalized", "no_niqqud", "single_term", "semantic", "named_topic_exact", "named_topic_normalized", "named_topic_alias", "named_topic_translation", "named_topic_hebrew_equivalent", "named_topic_partial", "structural_heading_exact", "structural_heading_normalized", "structural_heading_accent_folded", "structural_heading_all_tokens_ordered", "structural_heading_all_tokens_proximity", "structural_heading_partial"].includes(String(hit.literal_match_kind)) ? hit.literal_match_kind : "none";
    const evidenceText = string(hit.display_snippet || hit.paragraph_text || hit.snippet || hit.quote);
    const inferredLanguage: Language = (evidenceText.match(/[\u0590-\u05ff]/gu)?.length ?? 0) >= 10 ? "he" : "es";
    const language = ["es", "en", "he"].includes(String(hit.language)) ? hit.language as Language : inferredLanguage;
    const parallelTexts = array<Record<string, unknown>>(hit.parallel_texts).map((parallel) => {
      if (!["es", "en", "he"].includes(String(parallel.language)) || !SOURCE_LAYERS.includes(parallel.source_layer as SourceLayer) || parallel.link_type !== "parallel_translation" || parallel.linked_to_evidence_id !== hit.hit_id) throw new Error("La respuesta contiene un texto paralelo incompatible.");
      return { ...parallel, text: safeText(parallel.text), physical_pdf_page: parallel.physical_pdf_page == null ? null : Number(parallel.physical_pdf_page), printed_page: parallel.printed_page == null ? null : Number(parallel.printed_page) } as ParallelText;
    });
    return {
      ...hit,
      source_layer: sourceLayer,
      quote: safeText(hit.quote), snippet: safeText(hit.snippet || hit.quote),
      match_text: safeText(hit.match_text), sentence_text: safeText(hit.sentence_text),
      paragraph_text: safeText(hit.paragraph_text),
      context_before: safeText(hit.context_before), context_after: safeText(hit.context_after),
      literal_strength: ["strong", "medium", "weak"].includes(String(hit.literal_strength)) ? hit.literal_strength : "strong",
      relation_relevance: relationRelevance, language_match: languageMatch, literal_match_kind: literalMatchKind,
      relation_type: relationTypes.includes(hit.relation_type as RelationType) ? hit.relation_type : "none",
      relation_strength: ["high", "medium", "low", "none"].includes(String(hit.relation_strength)) ? hit.relation_strength : "none",
      literal_relation: hit.literal_relation === true,
      inference_required: hit.inference_required === true,
      retrieval_tier: typeof hit.retrieval_tier === "number" ? hit.retrieval_tier : 99,
      matched_terms: array<string>(hit.matched_terms), matched_concepts: array<string>(hit.matched_concepts),
      is_primary: hit.is_primary === true, is_original_language: hit.is_original_language === true,
      is_primary_language_match: hit.is_primary_language_match === true, is_translation: hit.is_translation === true,
      is_editorial_commentary: hit.is_editorial_commentary === true,
      pdf_page: hit.pdf_page == null ? null : hit.pdf_page,
      physical_pdf_page: hit.physical_pdf_page == null ? (hit.pdf_page == null ? null : hit.pdf_page) : Number(hit.physical_pdf_page),
      printed_page: hit.printed_page == null ? null : Number(hit.printed_page),
      language, direction: language === "he" ? "rtl" : "ltr", source_layer_confidence: confidence,
      source_layer_rationale: string(hit.source_layer_rationale, "insufficient_structural_evidence"),
      parallel_texts: parallelTexts, warnings: array<string>(hit.warnings),
      author_quote_status: (["confirmed_author_text", "confirmed_translated_author_text", "editorial_paraphrase", "editorial_commentary", "translator_note", "footnote_reference", "not_confirmed", "not_applicable"].includes(String(hit.author_quote_status)) ? hit.author_quote_status : "not_confirmed") as AuthorQuoteStatus,
      attribution_label: string(hit.attribution_label),
      raw_snippet: string(hit.raw_snippet),
      snippet_sanitized: hit.snippet_sanitized === true,
      sanitization_reason_codes: array<string>(hit.sanitization_reason_codes),
    } as Hit;
  });
}
function normalizeMatrix(value: unknown): MatrixRow[] { return array<unknown>(value).map((item) => { if (!item || typeof item !== "object") throw new Error("La respuesta contiene una matriz incompatible."); const row = item as Record<string, unknown>; if (typeof row.work_code !== "string" || typeof row.hits !== "number") throw new Error("La respuesta contiene una matriz incompatible."); return row as unknown as MatrixRow; }); }
function normalizeClaims(value: unknown, hits: Hit[]): Claim[] { const allowed = new Set(hits.map((hit) => hit.hit_id)); const ids = new Set<string>(); return array<unknown>(value).map((item) => { if (!item || typeof item !== "object") throw new Error("La respuesta contiene un claim incompatible."); const claim = item as Record<string, unknown>; const claimId = string(claim.claim_id); const text = string(claim.text); const evidenceIds = array<unknown>(claim.evidence_ids).map((id) => string(id)); const primary = string(claim.primary_evidence_id); if (!claimId || ids.has(claimId) || !text || !evidenceIds.length || evidenceIds.some((id) => !allowed.has(id)) || !evidenceIds.includes(primary)) throw new Error("La trazabilidad entre afirmaciones y fuentes es incompatible."); ids.add(claimId); return { claim_id: claimId, text, strength: ["strong", "medium", "weak", "insufficient"].includes(String(claim.strength)) ? claim.strength as Claim["strength"] : "weak", evidence_ids: [...new Set(evidenceIds)], primary_evidence_id: primary }; }); }
export function normalizeResearchResponse(value: unknown): ResearchResponse {
  if (!value || typeof value !== "object") throw new Error("La respuesta de investigación no tiene un formato compatible.");
  const raw = value as Record<string, unknown>; const status = raw.status;
  if (status !== "ok" && status !== "partial" && status !== "no_evidence") throw new Error("La respuesta de investigación no indica un estado válido.");
  const conversation = raw.conversation && typeof raw.conversation === "object" ? raw.conversation as Record<string, unknown> : {};
  const answerText = string(raw.answer_text); const answerMarkdown = string(raw.answer_markdown, answerText);
  if (status !== "no_evidence" && !answerMarkdown) throw new Error("La respuesta de investigación no contiene texto renderizable.");
  const hits = normalizeHits(raw.hits); const claims = normalizeClaims(raw.claims, hits); const allowed = new Set(hits.map((hit) => hit.hit_id)); const primaryIds = array<unknown>(raw.primary_evidence_ids).map((id) => string(id)); const primaryHits = primaryIds.map((id) => hits.find((hit) => hit.hit_id === id)); if (primaryIds.some((id) => !allowed.has(id)) || primaryHits.some((hit) => !hit || hit.evidence_strength === "insufficient") || claims.some((claim) => !primaryIds.includes(claim.primary_evidence_id) || claim.strength === "insufficient") || (status === "no_evidence" && primaryIds.length > 0)) throw new Error("La selección de evidencia principal es incompatible."); const counts = raw.evidence_counts && typeof raw.evidence_counts === "object" ? raw.evidence_counts as Record<string, unknown> : {}; const evidenceCounts = { primary: Number(counts.primary ?? primaryIds.length), contextual: Number(counts.contextual ?? 0), additional_literal: Number(counts.additional_literal ?? 0) }; if (Object.values(evidenceCounts).some((count) => !Number.isInteger(count) || count < 0)) throw new Error("El resumen de evidencias es incompatible.");
  const intents = ["literal_lookup", "concept_lookup", "concept_cooccurrence", "discover_relations", "relation_query", "biblical_reference_lookup", "named_teaching_lookup", "translation_or_explanation", "reference_lookup", "structural_reference_lookup", "location_lookup", "follow_up", "source_layer_question", "book_scope_query", "source_request", "comparison_query", "unknown"] as const;
  const intent = intents.includes(raw.intent as typeof intents[number]) ? raw.intent as ResearchResponse["intent"] : undefined;
  const interpretation = raw.interpretation && typeof raw.interpretation === "object" ? raw.interpretation as QueryInterpretation : undefined;
  const queryResolution = raw.query_resolution && typeof raw.query_resolution === "object" ? raw.query_resolution as QueryResolution : undefined;
  const relations = array<Record<string, unknown>>(raw.relations).map((relation) => { const evidenceIds = array<string>(relation.evidence_ids); const primary = string(relation.primary_evidence_id); if (!string(relation.related_concept) || !string(relation.statement) || !relationTypes.includes(relation.relation_type as RelationType) || evidenceIds.some((id) => !allowed.has(id)) || !evidenceIds.includes(primary)) throw new Error("La relación validada es incompatible."); return { ...relation, evidence_ids: evidenceIds, primary_evidence_id: primary } as ValidatedRelation; });
  const rawResearchStatus = string(raw.research_status);
  const researchStatus: ResearchStatus = ["complete", "partial", "degraded", "no_evidence"].includes(rawResearchStatus)
    ? rawResearchStatus as ResearchStatus
    : status === "ok" ? "complete" : status;
  return { status, research_status: researchStatus, original_query: string(raw.original_query, string(raw.question)), pipeline: string(raw.pipeline) || undefined, intent, target_evidence_id: typeof raw.target_evidence_id === "string" ? raw.target_evidence_id : null, same_primary_evidence: typeof raw.same_primary_evidence === "boolean" ? raw.same_primary_evidence : null, interpretation, query_resolution: queryResolution, query_understanding: raw.query_understanding && typeof raw.query_understanding === "object" ? raw.query_understanding as QueryUnderstanding : undefined, named_topic: raw.named_topic && typeof raw.named_topic === "object" ? raw.named_topic as NamedTopic : null, answer_text: answerText, answer_markdown: answerMarkdown, summary: string(raw.summary), conversation: { conversation_id: typeof conversation.conversation_id === "string" ? conversation.conversation_id : null, turn_id: typeof conversation.turn_id === "string" ? conversation.turn_id : null, resolved_context: array<string>(conversation.resolved_context) }, works_consulted: array<string>(raw.works_consulted), hits, claims, relations, primary_evidence_ids: [...new Set(primaryIds)], evidence_counts: evidenceCounts, evidence_matrix: normalizeMatrix(raw.evidence_matrix), cross_corpus_matrix: normalizeMatrix(raw.cross_corpus_matrix), warnings: array<string>(raw.warnings), not_found: array<string>(raw.not_found), execution: raw.execution && typeof raw.execution === "object" ? raw.execution as Record<string, unknown> : {}, retrieval: raw.retrieval && typeof raw.retrieval === "object" ? raw.retrieval as Record<string, unknown> : undefined, processing: raw.processing && typeof raw.processing === "object" ? raw.processing as Record<string, unknown> : undefined };
}
export function selectInitialEvidence(response: ResearchResponse): string | null { return response.primary_evidence_ids[0] ?? null; }
export function makeRequest(question: string, filters: { works: string[]; languages: Language[]; thematic: boolean; maxHits: number }, history: Array<{ question: string }>, conversationId: string | null, turnId: string | null): ResearchRequest { const works = filters.works.filter((w) => (WORKS as readonly string[]).includes(w)); const languages = filters.languages.filter((l): l is Language => ["es", "en", "he"].includes(l)); return { question, conversation: { conversation_id: conversationId, turn_id: turnId, history: history.slice(-15) }, works: works.length ? works : [...WORKS], languages: languages.length ? languages : ["es"], include_thematic: filters.thematic, include_audit: false, min_evidence: "literal", max_hits_per_work: [5, 10, 20].includes(filters.maxHits) ? filters.maxHits : 10, return_markdown: true, return_json: true, ai: { enabled: true, model: "openai_gpt-5.4-nano" } }; }
export async function askInvestigativeQa(token: string, request: ResearchRequest, signal?: AbortSignal): Promise<ResearchResponse> { const r = await fetch(`${API_BASE_URL.replace(/\/+$/, "")}${API_ROUTES.investigativeQa}`, { method: "POST", headers: { "Content-Type": "application/json", Authorization: `Bearer ${token}` }, body: JSON.stringify(request), signal }); if (!r.ok) throw new Error(r.status === 401 ? "Tu sesión expiró. Iniciá sesión nuevamente." : "No se pudo completar la investigación. Podés reintentar."); return normalizeResearchResponse(await r.json()); }

export function normalizeInterpretationResponse(value: unknown): InterpretationResponse {
  if (!value || typeof value !== "object") throw new Error("La interpretación no tiene un formato compatible.");
  const raw = value as Record<string, unknown>;
  const understanding = raw.query_understanding;
  const actions = array<unknown>(raw.actions);
  if (
    raw.phase !== "interpretation"
    || raw.status !== "awaiting_confirmation"
    || typeof raw.interpretation_id !== "string"
    || typeof raw.conversation_id !== "string"
    || typeof raw.original_query !== "string"
    || typeof raw.display_interpretation !== "string"
    || !understanding
    || typeof understanding !== "object"
    || actions.length !== 2
    || actions[0] !== "analyze"
    || actions[1] !== "modify"
  ) {
    throw new Error("La interpretación no tiene un contrato confirmable válido.");
  }
  return {
    phase: "interpretation",
    status: "awaiting_confirmation",
    interpretation_id: raw.interpretation_id,
    conversation_id: raw.conversation_id,
    original_query: safeText(raw.original_query),
    display_interpretation: safeText(raw.display_interpretation),
    query_understanding: understanding as ConfirmableQueryUnderstanding,
    actions: ["analyze", "modify"],
    warnings: array<string>(raw.warnings),
    expires_at: typeof raw.expires_at === "number" ? raw.expires_at : null,
    execution: raw.execution && typeof raw.execution === "object" ? raw.execution as Record<string, unknown> : {},
  };
}

export function makeInterpretRequest(
  question: string,
  filters: { works: string[]; languages: Language[]; thematic: boolean; maxHits: number },
  history: Array<{ question: string }>,
  conversationId: string,
  supersedesInterpretationId?: string,
): ResearchRequest {
  return {
    ...makeRequest(question, filters, history, conversationId, null),
    phase: "interpret",
    ...(supersedesInterpretationId ? { supersedes_interpretation_id: supersedesInterpretationId } : {}),
  };
}

export function makeAnalyzeRequest(
  interpretation: InterpretationResponse,
  filters: { works: string[]; languages: Language[]; thematic: boolean; maxHits: number },
  history: Array<{ question: string }>,
): ResearchRequest {
  return {
    ...makeRequest(
      interpretation.original_query,
      filters,
      history,
      interpretation.conversation_id,
      null,
    ),
    phase: "analyze",
    interpretation_id: interpretation.interpretation_id,
    idempotency_key: `analysis:${interpretation.interpretation_id}`,
  };
}

async function postConfirmationPhase(
  token: string,
  request: ResearchRequest,
  signal?: AbortSignal,
): Promise<unknown> {
  const response = await fetch(
    `${API_BASE_URL.replace(/\/+$/, "")}${API_ROUTES.investigativeQa}`,
    {
      method: "POST",
      headers: { "Content-Type": "application/json", Authorization: `Bearer ${token}` },
      body: JSON.stringify(request),
      signal,
    },
  );
  if (!response.ok) {
    throw new Error(
      response.status === 401
        ? "Tu sesión expiró. Inicia sesión nuevamente."
        : "No se pudo completar la investigación. Puede reintentar.",
    );
  }
  return response.json();
}

export async function interpretInvestigativeQuery(
  token: string,
  request: ResearchRequest,
  signal?: AbortSignal,
): Promise<InterpretationResponse> {
  return normalizeInterpretationResponse(await postConfirmationPhase(token, request, signal));
}

export async function analyzeConfirmedQuery(
  token: string,
  request: ResearchRequest,
  signal?: AbortSignal,
): Promise<ResearchResponse> {
  return normalizeResearchResponse(await postConfirmationPhase(token, request, signal));
}
