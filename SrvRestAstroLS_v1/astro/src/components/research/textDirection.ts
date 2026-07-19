export type DetectedLanguage = "he" | "ar" | "es" | "en" | "mixed" | "unknown";
export type TextDirection = "rtl" | "ltr" | "auto";

const HEBREW = /[\u0590-\u05ff]/gu;
const ARABIC = /[\u0600-\u06ff\u0750-\u077f\u08a0-\u08ff]/gu;
const LATIN = /[A-Za-zÀ-ÖØ-öø-ÿ]/gu;
const BIDI_CONTROLS = /[\u061c\u200e\u200f\u202a-\u202e\u2066-\u2069]/gu;

const count = (text: string, pattern: RegExp): number => text.match(pattern)?.length ?? 0;

export function normalizeDisplayText(text: string): string {
  return text.replace(BIDI_CONTROLS, "").normalize("NFC");
}

export function detectLanguage(text: string): DetectedLanguage {
  const value = normalizeDisplayText(text).trim();
  if (!value) return "unknown";
  const hebrew = count(value, HEBREW), arabic = count(value, ARABIC), latin = count(value, LATIN);
  if (hebrew > 0 && hebrew > (arabic + latin) * 2) return "he";
  if (arabic > 0 && arabic > (hebrew + latin) * 2) return "ar";
  const active = [hebrew > 0, arabic > 0, latin > 0].filter(Boolean).length;
  if (active > 1) return "mixed";
  if (hebrew) return "he";
  if (arabic) return "ar";
  if (latin) return /[¿¡ñáéíóúü]|\b(el|la|los|las|de|del|que|una?|para|con|página)\b/iu.test(value) ? "es" : "en";
  return "unknown";
}

export function textDirection(text: string): TextDirection {
  const language = detectLanguage(text);
  if (language === "he" || language === "ar") return "rtl";
  if (language === "mixed") return "auto";
  return "ltr";
}

export function languageAttribute(text: string): "he" | "ar" | "es" | "en" | undefined {
  const language = detectLanguage(text);
  return ["he", "ar", "es", "en"].includes(language) ? language as "he" | "ar" | "es" | "en" : undefined;
}

export function isHebrewText(text: string): boolean {
  const normalized = normalizeDisplayText(text);
  return count(normalized, HEBREW) >= Math.max(1, count(normalized, LATIN));
}

export function composerDirection(text: string): TextDirection {
  const normalized = normalizeDisplayText(text);
  const hebrew = count(normalized, HEBREW), arabic = count(normalized, ARABIC), latin = count(normalized, LATIN);
  if (hebrew + arabic < 2) return "ltr";
  return hebrew + arabic >= latin ? "rtl" : "auto";
}

export function safeSnippet(text: string, limit = 160): string {
  const value = normalizeDisplayText(text).trim();
  if (value.length <= limit) return value;
  if (typeof Intl.Segmenter === "function") {
    const segments = [...new Intl.Segmenter(undefined, { granularity: "word" }).segment(value)];
    let result = "";
    for (const segment of segments) {
      if ((result + segment.segment).length > limit) break;
      result += segment.segment;
    }
    return `${result.trimEnd()}…`;
  }
  const graphemes = Array.from(value);
  const candidate = graphemes.slice(0, limit).join("");
  const boundary = candidate.lastIndexOf(" ");
  return `${(boundary > limit / 2 ? candidate.slice(0, boundary) : candidate).trimEnd()}…`;
}
