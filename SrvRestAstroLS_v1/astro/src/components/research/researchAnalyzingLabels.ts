/**
 * Analyse status labels — ES / EN / HE
 * Used by the research composer during submission.
 * Language is detected from the user's query text.
 */
export const analyzingMessages: Record<string, Record<string, string>> = {
  es: {
    "action.analyzing": "Analizando…",
    "status.searching": "Buscando fuentes y preparando la respuesta…",
    "status.verifying": "Verificando las fuentes recuperadas…",
    "status.organizing": "Organizando la respuesta investigativa…",
  },
  en: {
    "action.analyzing": "Analyzing…",
    "status.searching": "Searching the sources and preparing the answer…",
    "status.verifying": "Verifying the retrieved sources…",
    "status.organizing": "Organizing the research response…",
  },
  he: {
    "action.analyzing": "מנתח…",
    "status.searching": "מחפש מקורות ומכין את התשובה…",
    "status.verifying": "בודק את המקורות שנמצאו…",
    "status.organizing": "מסדר את התשובה המחקרית…",
  },
};

export function getAnalyzingLabel(lang: string, key: string): string {
  return analyzingMessages[lang]?.[key] ?? analyzingMessages.es[key] ?? key;
}
