"""Breslov Research Conversation Analyzer.

Analyzes user queries via LiteLLM to produce structured conversation plans.
Falls back to deterministic analysis when LiteLLM is unavailable.
"""

from __future__ import annotations

import json
import re
from typing import Any

import httpx

from globalVar import (
    LITELLM_API_KEY,
    LITELLM_BASE_URL,
    LITELLM_TIMEOUT_SECONDS,
    RESEARCH_CONVERSATION_MODEL,
)
from modules.library.research_schemas import (
    ConversationAnalysisResult,
    ResearchIntent,
    ResearchMode,
    RetrievalMode,
    RetrievalStrategy,
    SafetyFlags,
)

FALLBACK_TOPIC_MAP: dict[str, list[str]] = {
    "tristeza": ["tristeza", "triste", "depresión", "melancolía", "desánimo"],
    "miedo": ["miedo", "temor", "angustia", "ansiedad", "temor"],
    "tzadik": ["tzadik", "tzaddik", "justo", "rebe najmán"],
    "oracion": ["oración", "plegaria", "hitbodedut", "tefilá"],
    "alegria": ["alegría", "alegria", "simjá", "felicidad", "gozo"],
    "fe": ["fe", "emuna", "creencia", "confianza"],
    "desesperacion": ["desesperación", "desesperacion", "desánimo", "desaliento"],
    "puente": ["puente angosto", "puente muy angosto", "angosto"],
}

LANGUAGE_PATTERNS: dict[str, str] = {
    "es": r"\b(qué|cuál|dónde|cómo|por qué|qué es|dame|busco|necesito|tristeza|alegría|miedo|fe|alma|dios|plegaria|oración|libro|fuente|página|cita)\b",
    "en": r"\b(what|where|how|why|give me|find|show|sadness|fear|joy|faith|god|prayer|book|source|page|quote)\b",
}

INTENT_PATTERNS: dict[str, str] = {
    "find_sources": r"\b(dónde|dame|buscar|fuentes|qué libro|en qué|find|sources|where)\b",
    "locate_literal": r"\b(literalmente|literal|aparece|dice textual|cita exacta|exactamente|literal|exact quote|verbatim)\b",
    "explain_concept": r"\b(qué es|qué significa|explica|cómo|why|how|mean|explain|concept|significa)\b",
    "list_books": r"\b(qué libros|qué otros libros|list|libros|en qué|books)\b",
    "evidence_check": r"\b(es cita|es interpretación|es literal|es remez|cita|interpretación|paráfrasis|evidence|quote|paraphrase)\b",
    "compare_sources": r"\b(diferencia|relación|compara|comparing|relationship|difference|similitud)\b",
}


class ResearchConversationAnalyzer:
    """Analyze a user query for research intent, language, and retrieval strategy.

    Uses LiteLLM for structured analysis when available.
    Falls back to deterministic rule-based analysis when LiteLLM is unavailable.
    """

    def __init__(self) -> None:
        self.model = RESEARCH_CONVERSATION_MODEL or "gpt5.5-nano"

    def analyze(self, query: str) -> ConversationAnalysisResult:
        try:
            return self._analyze_via_litellm(query)
        except Exception:
            return self._analyze_deterministic(query)

    def _analyze_via_litellm(self, query: str) -> ConversationAnalysisResult:
        if not LITELLM_API_KEY:
            return self._analyze_deterministic(query)

        url = f"{LITELLM_BASE_URL}/v1/chat/completions"
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {LITELLM_API_KEY}",
        }
        payload = {
            "model": self.model,
            "messages": [
                {
                    "role": "system",
                    "content": (
                        "You are a research conversation analyzer for a Breslov bibliographic assistant. "
                        "Analyze the user query and return ONLY valid JSON with these fields:\n"
                        "  \"language\": \"es\" | \"en\" | \"he\" | \"unknown\"\n"
                        "  \"intent\": \"find_sources\" | \"explain_concept\" | \"compare_sources\" | "
                        "\"locate_literal\" | \"list_books\" | \"evidence_check\" | \"out_of_scope\" | \"unclear\"\n"
                        "  \"research_mode\": \"bibliographic\" | \"conceptual\" | \"comparative\" | "
                        "\"literal\" | \"thematic\" | \"interpretive\"\n"
                        "  \"topic_terms\": [<key terms from query>]\n"
                        "  \"expanded_terms\": [<related search terms>]\n"
                        "  \"requested_documents\": [<specific book titles if mentioned>]\n"
                        "  \"requires_literal_check\": true|false\n"
                        "  \"requires_cross_book_search\": true|false\n"
                        "  \"requires_evidence_levels\": true|false\n"
                        "  \"requires_limitations\": true|false\n"
                        "  \"retrieval_mode\": \"hybrid\" | \"vector\" | \"fts\" | \"literal\"\n"
                        "  \"safety_flags\": {\"may_need_interpretive_label\": true|false, "
                        "\"risk_of_false_quote\": true|false}\n"
                        "Do not include any text outside the JSON object."
                    ),
                },
                {"role": "user", "content": query},
            ],
            "temperature": 0.1,
            "max_tokens": 300,
        }

        with httpx.Client(timeout=LITELLM_TIMEOUT_SECONDS) as client:
            resp = client.post(url, json=payload, headers=headers)

        if resp.status_code != 200:
            return self._analyze_deterministic(query)

        data = resp.json()
        content = data.get("choices", [{}])[0].get("message", {}).get("content", "")
        if not content:
            return self._analyze_deterministic(query)

        parsed = self._parse_llm_json(content)
        if parsed is None:
            return self._analyze_deterministic(query)

        return self._llm_dict_to_result(parsed, query)

    def _parse_llm_json(self, content: str) -> dict[str, Any] | None:
        content = content.strip()
        if content.startswith("```"):
            lines = content.splitlines()
            content = "\n".join(lines[1:-1]) if len(lines) > 2 else content
        try:
            return json.loads(content)
        except json.JSONDecodeError:
            match = re.search(r"\{.*\}", content, re.DOTALL)
            if match:
                try:
                    return json.loads(match.group(0))
                except json.JSONDecodeError:
                    return None
            return None

    def _llm_dict_to_result(
        self, d: dict[str, Any], query: str
    ) -> ConversationAnalysisResult:
        intent_str = d.get("intent", "unclear")
        try:
            intent = ResearchIntent(intent_str)
        except ValueError:
            intent = ResearchIntent.unclear

        mode_str = d.get("research_mode", "bibliographic")
        try:
            mode = ResearchMode(mode_str)
        except ValueError:
            mode = ResearchMode.bibliographic

        ret_mode_str = d.get("retrieval_mode", "hybrid")
        try:
            ret_mode = RetrievalMode(ret_mode_str)
        except ValueError:
            ret_mode = RetrievalMode.hybrid

        safety = d.get("safety_flags", {})
        if isinstance(safety, dict):
            safety_flags = SafetyFlags(
                may_need_interpretive_label=safety.get("may_need_interpretive_label", False),
                risk_of_false_quote=safety.get("risk_of_false_quote", False),
            )
        else:
            safety_flags = SafetyFlags()

        return ConversationAnalysisResult(
            user_query=query,
            language=d.get("language", "unknown"),
            intent=intent,
            research_mode=mode,
            topic_terms=d.get("topic_terms", []),
            expanded_terms=d.get("expanded_terms", []),
            requested_documents=d.get("requested_documents", []),
            requires_literal_check=d.get("requires_literal_check", False),
            requires_cross_book_search=d.get("requires_cross_book_search", False),
            requires_evidence_levels=d.get("requires_evidence_levels", True),
            requires_limitations=d.get("requires_limitations", True),
            retrieval_strategy=RetrievalStrategy(
                mode=ret_mode,
                top_k=20,
                expanded_terms=d.get("expanded_terms", []),
            ),
            safety_flags=safety_flags,
            model_used=self.model,
            analysis_fallback=False,
        )

    def _analyze_deterministic(self, query: str) -> ConversationAnalysisResult:
        q = query.lower().strip()

        language = self._detect_language(q)
        intent = self._detect_intent(q)
        mode = self._detect_mode(intent, q)
        topic_terms = self._extract_topic_terms(q)
        expanded_terms = self._expand_terms(topic_terms)
        requested_docs = self._detect_requested_documents(q)
        ret_mode = self._detect_retrieval_mode(intent, q)

        return ConversationAnalysisResult(
            user_query=query,
            language=language,
            intent=intent,
            research_mode=mode,
            topic_terms=topic_terms,
            expanded_terms=expanded_terms or [query],
            requested_documents=requested_docs,
            requires_literal_check=intent == ResearchIntent.locate_literal,
            requires_cross_book_search=intent in (
                ResearchIntent.list_books, ResearchIntent.compare_sources,
            ),
            retrieval_strategy=RetrievalStrategy(
                mode=ret_mode,
                top_k=20,
                expanded_terms=expanded_terms or [query],
            ),
            analysis_fallback=True,
        )

    def _detect_language(self, q: str) -> str:
        es_score = len(re.findall(LANGUAGE_PATTERNS["es"], q))
        en_score = len(re.findall(LANGUAGE_PATTERNS["en"], q))
        if es_score > en_score:
            return "es"
        if en_score > es_score:
            return "en"
        return "es"

    def _detect_intent(self, q: str) -> ResearchIntent:
        scores: dict[ResearchIntent, int] = {}
        for intent_name, pattern in INTENT_PATTERNS.items():
            matches = len(re.findall(pattern, q))
            if matches > 0:
                try:
                    intent = ResearchIntent(intent_name)
                    scores[intent] = matches
                except ValueError:
                    pass
        if not scores:
            return ResearchIntent.find_sources
        return max(scores, key=scores.get)

    def _detect_mode(self, intent: ResearchIntent, q: str) -> ResearchMode:
        if intent == ResearchIntent.locate_literal:
            return ResearchMode.literal
        if intent == ResearchIntent.compare_sources:
            return ResearchMode.comparative
        if intent == ResearchIntent.evidence_check:
            return ResearchMode.thematic
        if intent == ResearchIntent.explain_concept:
            return ResearchMode.conceptual
        if intent == ResearchIntent.list_books:
            return ResearchMode.bibliographic
        return ResearchMode.bibliographic

    def _extract_topic_terms(self, q: str) -> list[str]:
        words = re.findall(r"[a-zA-ZáéíóúñüäëïöÁÉÍÓÚÑÜ]+", q)
        stopwords = {
            "qué", "que", "es", "en", "un", "una", "el", "la", "los", "las",
            "de", "del", "por", "con", "para", "dónde", "cómo", "qué",
            "dame", "busco", "sobre", "entre", "what", "is", "the", "a",
            "an", "in", "on", "at", "for", "of", "to", "and", "or",
            "give", "find", "show", "does", "are", "can", "you",
        }
        return [w for w in words if w.lower() not in stopwords][:5]

    def _expand_terms(self, terms: list[str]) -> list[str]:
        expanded: list[str] = list(terms)
        for term in terms:
            term_lower = term.lower()
            for key, vals in FALLBACK_TOPIC_MAP.items():
                if term_lower == key or term_lower in vals:
                    expanded.extend(vals)
                    break
        seen: set[str] = set()
        return [t for t in expanded if not (t.lower() in seen or seen.add(t.lower()))]

    def _detect_requested_documents(self, q: str) -> list[str]:
        known_docs = [
            "kitzur", "cruzando el puente", "el alma del rebe najmán",
            "el jardín de las almas", "kokhavey ohr", "la potencia de la plegaria",
            "likutey halajot", "un día en la vida",
        ]
        found: list[str] = []
        for doc in known_docs:
            if doc.lower() in q:
                found.append(doc)
        return found

    def _detect_retrieval_mode(
        self, intent: ResearchIntent, q: str
    ) -> RetrievalMode:
        if intent == ResearchIntent.locate_literal:
            return RetrievalMode.literal
        if re.search(r"\bliteral\b|\bliteralmente\b|\bexactamente\b|\bexacto\b", q):
            return RetrievalMode.literal
        if re.search(r"\bfts\b", q):
            return RetrievalMode.fts
        return RetrievalMode.hybrid
