export const evidenceLabels: Record<string, string> = {
  validated_fine_zone_quote: "Cita literal validada",
  validated_nominal_reference: "Referencia nominal literal",
  validated_numbered_note: "Nota numerada validada",
  resolved_investigative_reference: "Resolución investigativa",
  cross_work_literal_parallel: "Paralelo literal entre obras",
  thematic_parallel: "Paralelo temático",
  remesh_or_derash_candidate: "Posible relación interpretativa",
  literal_same_page: "Cita literal recuperada",
  canonical_markdown: "Fragmento canónico recuperado",
};

export const relevanceLabels: Record<string, string> = {
  direct_relation: "Respaldo directo del claim",
  same_fragment_both_terms: "Ambos conceptos en el mismo fragmento",
  same_page_both_terms: "Ambos conceptos en la misma página",
  same_section_relation: "Relación en la misma sección",
  single_term_literal: "Coincidencia literal de un solo concepto",
  thematic_parallel: "Paralelo temático",
  inferred_relation: "Relación inferida",
  unrelated_literal_noise: "Coincidencia literal no relacionada",
};

export const relationTypeLabels: Record<string, string> = {
  direct_literal: "Relación literal directa",
  direct_paraphrase: "Relación directa parafraseada",
  mediated_explicit_chain: "Cadena explícita mediada",
  same_fragment_cooccurrence: "Coocurrencia en el mismo fragmento",
  same_page: "Coocurrencia en la misma página",
  same_section: "Relación en la misma sección",
  thematic_parallel: "Paralelo temático",
  AI_grounded_inference: "Inferencia IA sustentada",
  none: "No corresponde relación",
};

export const warningLabels: Record<string, string> = {
  pdf_page_null_for_kitzur_chunk: "La página no está disponible en el registro fuente",
  ai_render_rejected_grounding_validation: "La redacción automática no superó la validación de evidencia",
  "ai_render_fallback:litellm_key_missing": "Se utilizó una respuesta determinística segura",
  ai_disabled: "La redacción automática estuvo deshabilitada para esta consulta",
};

export function warningLabel(code: string): string {
  if (warningLabels[code]) return warningLabels[code];
  if (
    code.startsWith("La búsqueda semántica no estuvo disponible")
    || code.startsWith("La búsqueda literal no estuvo disponible")
    || code.startsWith("La redacción automática no estuvo disponible")
    || code.startsWith("La interpretación avanzada no estuvo disponible")
  ) return code;
  if (code.startsWith("ai_render_failed:")) {
    return "La redacción automática fue rechazada por la validación; se muestran las fuentes recuperadas";
  }
  if (code.startsWith("ai_render_fallback:")) return "Se utilizó una respuesta determinística segura";
  if (code.startsWith("ai_interpretation_fallback:")) return "La interpretación automática no estuvo disponible; se conservaron los términos de la consulta";
  return "La consulta contiene una limitación técnica registrada en los detalles";
}

export function strengthLabel(value: string): string {
  return value === "strong" ? "Fuerte" : value === "medium" ? "Media" : value === "weak" ? "Débil" : "Sin evidencia suficiente";
}

export const languageMatchLabels: Record<string, string> = {
  exact: "Idioma consultado",
  primary: "Idioma prioritario",
  secondary: "Traducción / ampliación",
  fallback: "Otro idioma",
};

export const literalMatchKindLabels: Record<string, string> = {
  exact_phrase: "Coincidencia literal exacta",
  normalized: "Coincidencia normalizada",
  no_niqqud: "Coincidencia sin niqqud",
  single_term: "Término individual",
  semantic: "Coincidencia semántica",
  named_topic_exact: "Tema nominal exacto",
  named_topic_normalized: "Tema nominal normalizado",
  named_topic_alias: "Alias nominal",
  named_topic_translation: "Equivalente traducido",
  named_topic_hebrew_equivalent: "Equivalente hebreo",
  named_topic_partial: "Tema nominal parcial",
  structural_heading_exact: "Coincidencia exacta con título de sección",
  structural_heading_normalized: "Encabezado estructural normalizado",
  structural_heading_accent_folded: "Encabezado estructural sin distinción de acentos",
  structural_heading_all_tokens_ordered: "Todos los términos del encabezado en orden",
  structural_heading_all_tokens_proximity: "Términos del encabezado en proximidad",
  structural_heading_partial: "Coincidencia parcial con encabezado",
  none: "",
};

export const sourceLayerLabels: Record<string, string> = {
  rebbe_lesson_text: "Texto original de la lección",
  biblical_quote_in_lesson: "Cita bíblica dentro de la lección",
  rabbinic_quote_in_lesson: "Cita rabínica dentro de la lección",
  editorial_translation: "Traducción editorial",
  editorial_commentary: "Comentario editorial",
  editorial_note: "Nota editorial",
  footnote: "Pie de página",
  source_reference: "Referencia de fuente",
  section_heading: "Encabezado de sección",
  page_heading: "Encabezado de página",
  introduction: "Introducción",
  unknown: "Capa editorial no confirmada; requiere revisión",
};

export const sourceLayerConfidenceLabels: Record<string, string> = {
  high: "alta", medium: "media", low: "baja",
};

export function languageMatchLabel(value: string): string {
  return languageMatchLabels[value] ?? "Otro idioma";
}

export function literalKindLabel(value: string): string {
  return literalMatchKindLabels[value] ?? "";
}

export const attributionLabels: Record<string, string> = {
  confirmed_author_text: "Cita textual del autor confirmada",
  confirmed_translated_author_text: "Traducción del texto original del autor",
  editorial_paraphrase: "Paráfrasis editorial",
  editorial_commentary: "Comentario editorial",
  translator_note: "Nota del traductor",
  footnote_reference: "Referencia en nota al pie",
  not_confirmed: "No confirmada como formulación textual del autor original",
  not_applicable: "No corresponde atribución al autor",
};
