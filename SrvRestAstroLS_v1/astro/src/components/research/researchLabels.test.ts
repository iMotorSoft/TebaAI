import { describe, expect, it } from "vitest";
import { relevanceLabels, strengthLabel, warningLabel } from "./researchLabels.ts";

describe("research evidence labels", () => {
  it("separates relation relevance from literal strength", () => {
    expect(relevanceLabels.single_term_literal).toMatch(/un solo concepto/);
    expect(strengthLabel("insufficient")).toBe("Sin evidencia suficiente");
  });

  it("translates known warnings without exposing raw codes", () => {
    expect(warningLabel("pdf_page_null_for_kitzur_chunk")).toBe("La página no está disponible en el registro fuente");
    expect(warningLabel("ai_render_fallback:TimeoutError")).toMatch(/determinística/);
    expect(warningLabel("La búsqueda semántica no estuvo disponible; se utilizó búsqueda literal.")).toMatch(/búsqueda literal/);
    expect(warningLabel("ai_render_failed:ValueError")).toMatch(/validación/);
  });

  it("uses a safe generic label for unknown warnings", () => {
    expect(warningLabel("internal_unknown_code")).not.toContain("internal_unknown_code");
  });
});
