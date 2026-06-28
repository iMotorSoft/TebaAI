import { API_BASE_URL, API_ROUTES } from "../global.js";

const BASE = API_BASE_URL.replace(/\/+$/, "");

export interface SearchRequest {
  collection: string;
  query: string;
  mode: "auto" | "fts" | "phrase" | "trigram" | "hybrid";
  top_k: number;
  language: "es" | "en" | "he";
}

export interface SearchResult {
  document_id: string;
  document_title: string;
  author: string | null;
  collection_code: string;
  chunk_id: string;
  chunk_index: number;
  language: string;
  page_start: number | null;
  page_end: number | null;
  chapter: string | null;
  section: string | null;
  match_type: string;
  rank: number | null;
  plain_excerpt: string | null;
  highlighted_excerpt: string;
  content_length: number;
}

export interface SearchResponse {
  query: string;
  collection: string;
  mode: string;
  language: string;
  total: number;
  results: SearchResult[];
}

class SearchError extends Error {
  status: number;
  constructor(message: string, status: number) {
    super(message);
    this.name = "SearchError";
    this.status = status;
  }
}

export async function searchLibrary(
  accessToken: string,
  request: SearchRequest,
): Promise<SearchResponse> {
  const res = await fetch(`${BASE}${API_ROUTES.librarySearch}`, {
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
    throw new SearchError(detail, res.status);
  }

  return res.json();
}

/**
 * Sanitize highlighted_excerpt: only allow <mark> and </mark>, escape everything else.
 */
export function sanitizeHighlighted(html: string): string {
  return html
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/&lt;mark&gt;/g, "<mark>")
    .replace(/&lt;\/mark&gt;/g, "</mark>");
}
