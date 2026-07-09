import { API_BASE_URL, API_ROUTES } from "../global.js";

const BASE = API_BASE_URL.replace(/\/+$/, "");

export interface RelationQARequest {
  question: string;
  concept_a?: string | null;
  concept_b?: string | null;
  language?: "es" | "en" | "he" | "auto";
  top_k?: number;
  use_ai?: boolean;
  include_test_candidates?: boolean;
  knowledge_scope_code?: string;
  evidence_depth?: "compact" | "standard" | "full";
  return_markdown?: boolean;
  debug?: boolean;
}

export interface RelationQAConceptVariants {
  label: string;
  variants: string[];
}

export interface RelationQAConcepts {
  concept_a: RelationQAConceptVariants;
  concept_b: RelationQAConceptVariants;
}

export interface RelationQAAnswer {
  short_conclusion: string;
  editorial_answer_markdown: string;
  literal_relation_found: boolean;
  ai_inference_used: boolean;
  editorial_certainty: "low" | "medium" | "high";
}

export interface RelationQASource {
  source_id: string;
  document_title: string;
  document_status: string;
  page_number: number | null;
  section: string;
  chapter: string;
  subtitle: string;
  language: string;
  chunk_id: string;
  evidence_type: string;
  evidence_types: string[];
  editorial_role: string;
  retrieval_method: string;
  score: number;
  citable: boolean;
  is_final_citation: boolean;
  snippet: string;
  source_refs: Array<Record<string, unknown>>;
  internal_cross_refs: Array<Record<string, unknown>>;
}

export interface RelationQAMethod {
  retrieval: string[];
  llm_model: string;
  embedding_model: string;
  used_pg_as_canonical: boolean;
  used_milvus: boolean;
  used_ai: boolean;
  ai_synthesis_status?: string;
  ai_synthesis_attempts?: number;
  fallback_used?: boolean;
  fallback_reason?: string | null;
  synthesis_mode?: string;
}

export interface RelationQAResponse {
  question: string;
  language: string;
  knowledge_scope_code: string;
  concepts: RelationQAConcepts;
  answer: RelationQAAnswer;
  evidence_summary: Record<string, number>;
  sources: RelationQASource[];
  source_map: RelationQASource[];
  warnings: string[];
  method: RelationQAMethod;
  debug: Record<string, unknown> | null;
}

class RelationQAError extends Error {
  status: number;

  constructor(message: string, status: number) {
    super(message);
    this.name = "RelationQAError";
    this.status = status;
  }
}

export async function askRelationQA(
  accessToken: string,
  request: RelationQARequest,
): Promise<RelationQAResponse> {
  const res = await fetch(`${BASE}${API_ROUTES.relationQa}`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      Authorization: `Bearer ${accessToken}`,
    },
    body: JSON.stringify(request),
  });

  if (!res.ok) {
    const detail = await res
      .json()
      .then((d) => d.detail || d.message || res.statusText)
      .catch(() => res.statusText);
    throw new RelationQAError(detail, res.status);
  }

  return res.json();
}
