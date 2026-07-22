import { describe, expect, it } from "vitest";
import { deduplicateStructuredMarkdown, renderSafeMarkdown } from "./markdownRenderer.ts";

describe("renderSafeMarkdown", () => {
  it("renders maintained Markdown structures", () => {
    const html = renderSafeMarkdown("# Título\n\n**fuerte** y *énfasis*\n\n- uno\n- dos\n\n> ציטוט 123\n\n`código`\n\n[seguro](https://example.com)");
    expect(html).toContain(">Título</h1>"); expect(html).toContain("<strong>fuerte</strong>"); expect(html).toContain("<ul>"); expect(html).toContain("<blockquote"); expect(html).toContain('rel="noopener noreferrer"');
  });
  it.each(["<script>alert(1)</script>", '<img src=x onerror="alert(1)">', '<iframe srcdoc="x"></iframe>', '<object data="x"></object>', '<embed src="x">', '<div onclick="alert(1)">texto</div>', '[ataque](javascript:alert(1))', '[datos](data:text/html,x)'])("neutralizes %s", (payload) => {
    const html = renderSafeMarkdown(payload); expect(html).not.toMatch(/script|iframe|object|embed|onerror|onclick|javascript:|data:text/i);
  });
  it("supports tables without unsafe attributes", () => { const html = renderSafeMarkdown("| Obra | Página |\n|---|---|\n| LM II | 12 |"); expect(html).toContain("<table>"); expect(html).not.toContain("style="); });
  it("never exposes null page notation", () => { expect(renderSafeMarkdown("page: null")).toContain("página no disponible"); });
  it("assigns trusted Hebrew semantics after sanitization", () => {
    const html = renderSafeMarkdown("> שָׁלוֹם 2:7");
    expect(html).toContain('lang="he"'); expect(html).toContain('dir="rtl"'); expect(html).toContain("research-hebrew-text");
  });
  it("isolates Hebrew inline in mixed Markdown without changing text", () => {
    const source = "Texto español עם עברית y English 2:7"; const html = renderSafeMarkdown(source);
    const template = document.createElement("template"); template.innerHTML = html;
    expect(template.content.textContent?.trim()).toBe(source); expect(html).toContain("<bdi"); expect(html).toContain('dir="auto"');
  });
  it("does not trust direction or language supplied by Markdown HTML", () => {
    const html = renderSafeMarkdown('<blockquote dir="rtl" lang="he" onclick="x()">texto español</blockquote>');
    expect(html).toContain('dir="ltr"'); expect(html).toContain('lang="es"'); expect(html).not.toContain("onclick");
  });
  it("removes sections already represented by structured evidence UI", () => {
    const markdown = "## Síntesis investigativa\n- Claim\n\n## Evidencia principal\n> servir a HaShem por la noche\n\n## Límites\n- Lectura prudente.\n\n## Advertencias\n- technical";
    expect(deduplicateStructuredMarkdown(markdown)).toBe("## Límites\n- Lectura prudente.");
  });
  it("preserves Markdown-only responses", () => {
    const markdown = "## Síntesis investigativa\nTexto sin evidencia estructurada.";
    expect(deduplicateStructuredMarkdown(markdown)).toBe(markdown);
  });
});
