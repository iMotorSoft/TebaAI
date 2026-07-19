import { describe, expect, it } from "vitest";
import { composerDirection, detectLanguage, isHebrewText, languageAttribute, normalizeDisplayText, safeSnippet, textDirection } from "./textDirection.ts";

describe("block language and bidi contract", () => {
  it.each([
    ["שלום עולם", "he", "rtl"], ["العربية", "ar", "rtl"], ["La plegaria", "es", "ltr"],
    ["English answer", "en", "ltr"], ["Texto עם עברית", "mixed", "auto"], ["", "unknown", "ltr"],
  ])("detects %s", (text, language, direction) => {
    expect(detectLanguage(text)).toBe(language); expect(textDirection(text)).toBe(direction);
  });
  it("preserves niqqud while producing NFC", () => {
    const nfd = "שָׁלוֹם".normalize("NFD");
    expect(normalizeDisplayText(nfd)).toBe(nfd.normalize("NFC"));
    expect(normalizeDisplayText(nfd)).toMatch(/[\u0591-\u05c7]/u);
  });
  it("removes unsafe bidi controls without reversing content", () => {
    expect(normalizeDisplayText("אב\u202eגד")).toBe("אבגד");
    expect(normalizeDisplayText("אבג")).not.toBe("גבא");
  });
  it("does not switch the composer for one isolated Hebrew character", () => {
    expect(composerDirection("a א")).toBe("ltr"); expect(composerDirection("מה נאמר 2:7?")).toBe("rtl"); expect(composerDirection("")).toBe("ltr");
  });
  it("exposes language only for a single known language", () => {
    expect(languageAttribute("עברית")).toBe("he"); expect(languageAttribute("Texto עברית")).toBeUndefined(); expect(isHebrewText("עברית 2:7")).toBe(true);
  });
  it("clips at Unicode word boundaries without splitting niqqud", () => {
    const result = safeSnippet("שָׁלוֹם עוֹלָם וְעוֹד מִלִּים", 12);
    expect(result).toMatch(/…$/); expect(result.normalize("NFC")).toBe(result); expect(result).not.toMatch(/[\u0591-\u05c7]…$/u);
  });
  it.each([
    ["עברית עם Génesis 2:7", "auto"], ["עברית עם Likutey Moharán II", "auto"], ["עברית (בסוגריים)", "rtl"], ["עברית \"במרכאות\"", "rtl"],
    ["שָׁלוֹם", "rtl"], ["שלום", "rtl"], ["עברית and English", "auto"], ["עברית עם https://example.com", "auto"], ["§ 19 עברית", "rtl"],
  ])("keeps mixed references isolated without reversing: %s", (text, direction) => {
    const normalized = normalizeDisplayText(text); expect(normalized).toMatch(/[\u0590-\u05ff]/u); expect(textDirection(normalized)).toBe(direction); expect(normalized).not.toBe(Array.from(text).reverse().join(""));
  });
});
