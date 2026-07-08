"""Breslov Research Service — full orchestration from query to answer.

Flow:
  user_query
  → conversation_analysis (LiteLLM or deterministic)
  → retrieval_plan
  → product retrieval (Milvus productive + FTS)
  → PG canonical resolution
  → evidence classification
  → research_answer
"""

from __future__ import annotations

import asyncio
import re
from datetime import datetime
from typing import Any

from modules.library.conversation_analyzer import ResearchConversationAnalyzer
from modules.library.research_schemas import (
    ConversationAnalysisField,
    ConversationAnalysisResult,
    EvidenceClassification,
    EvidenceLevel,
    ResearchAnswer,
    SourceMapEntry,
)

DIRECT_QUOTE_PATTERNS = re.compile(
    r"(Likutei|Likutey|Likutei Moharán|Likutei Moharan|Likutey Halajot|"
    r"Sijot Haran|Sefer HaMidot|"
    r"Rebe Najmán (dice|dijo|enseña|escribe|afirma|explica)|"
    r"Rabí Natán (dice|dijo|escribe|explica)|"
    r"enseña el Rebe Najmán|"
    r"dice el Rebe|"
    r"como dice|"
    r"como está escrito|"
    r"dijo el Rebe)",
    re.IGNORECASE,
)


class BreslovResearchService:
    """Full research conversation orchestration for Breslov corpus."""

    def __init__(
        self,
        scope_code: str = "breslov_primary",
        productive_collection: str = "tebaai_breslov_chunks_v1",
    ) -> None:
        self.scope_code = scope_code
        self.productive_collection = productive_collection
        self.conversation_analyzer = ResearchConversationAnalyzer()

    async def research(
        self,
        query: str,
        top_k: int = 20,
        document_id: str | None = None,
    ) -> ResearchAnswer:
        analysis = self.conversation_analyzer.analyze(query)

        retrieval_results = await self._execute_retrieval(
            analysis, top_k=top_k, document_id=document_id
        )

        classified = self._classify_results(
            retrieval_results, analysis.expanded_terms
        )

        source_map = self._build_source_map(classified)
        evidence_counts = self._count_evidence(classified)
        limitations = self._build_limitations(
            analysis, classified, len(source_map)
        )
        answer_summary = self._build_summary(
            query, analysis, evidence_counts, len(source_map)
        )

        return ResearchAnswer(
            query=query,
            conversation_analysis=ConversationAnalysisField(
                language=analysis.language,
                intent=analysis.intent.value,
                research_mode=analysis.research_mode.value,
                topic_terms=analysis.topic_terms,
                model_used=analysis.model_used,
                analysis_fallback=analysis.analysis_fallback,
            ),
            answer_summary=answer_summary,
            source_map=source_map,
            evidence_counts=evidence_counts,
            documents_found=len({s.document_id for s in source_map}),
            chunks_found=len(source_map),
            limitations=limitations,
            answer_generated_at=datetime.utcnow().isoformat(),
        )

    async def _execute_retrieval(
        self,
        analysis: ConversationAnalysisResult,
        top_k: int = 20,
        document_id: str | None = None,
    ) -> list[dict[str, Any]]:
        from infrastructure.postgres.pool import (
            close_pool,
            create_pool_from_settings,
            open_pool,
        )

        pool = create_pool_from_settings()
        await open_pool(pool)

        try:
            all_results: list[dict[str, Any]] = []
            seen_ids: set[str] = set()
            search_terms = (
                analysis.expanded_terms[:5]
                if analysis.expanded_terms
                else [analysis.user_query]
            )

            async with pool.connection() as conn:
                for term in search_terms:
                    fts_results = await self._search_fts(
                        conn, term, top_k=top_k
                    )
                    for r in fts_results:
                        cid = str(r.get("chunk_id", ""))
                        if cid and cid not in seen_ids:
                            seen_ids.add(cid)
                            all_results.append(r)

                for term in search_terms:
                    vec_results = self._search_vector(term, top_k=top_k)
                    for hit in vec_results:
                        cid = hit.get("chunk_id", "")
                        if not cid or cid in seen_ids:
                            continue
                        seen_ids.add(cid)
                        pg_data = await self._enrich_from_pg(conn, cid)
                        if pg_data:
                            hit["content"] = pg_data["content"]
                            hit["document_title"] = pg_data.get(
                                "document_title", hit.get("title", "")
                            )
                            hit["author"] = pg_data.get("author")
                            hit["page_start"] = hit.get("page_start") or pg_data.get(
                                "page_start"
                            )
                            hit["page_end"] = hit.get("page_end") or pg_data.get(
                                "page_end"
                            )
                            hit["chunk_index"] = pg_data.get("chunk_index", 0)
                            hit["_vector_score"] = hit.get("distance", 0.0)
                            all_results.append(hit)

            if document_id:
                all_results = [
                    r
                    for r in all_results
                    if str(r.get("document_id", "")) == document_id
                ]

            return all_results
        finally:
            await close_pool(pool)

    async def _search_fts(
        self, conn, query: str, top_k: int = 20
    ) -> list[dict]:
        from modules.library.text_search import search_chunks_text
        return await search_chunks_text(
            conn,
            knowledge_scope_code=self.scope_code,
            query=query,
            top_k=top_k,
            mode="auto",
        )

    def _search_vector(self, query: str, top_k: int = 20) -> list[dict[str, Any]]:
        from modules.embeddings.client import embed_text
        from infrastructure.milvus.client import (
            create_connection,
            ensure_collection,
            search_vectors,
        )
        try:
            create_connection()
            query_vec = embed_text(query)
            if not query_vec:
                return []
            ensure_collection(self.productive_collection, dimension=len(query_vec))
            hits = search_vectors(
                collection_name=self.productive_collection,
                query_embedding=query_vec,
                top_k=top_k,
                expr=f'collection_code == "{self.scope_code}"',
                output_fields=[
                    "chunk_id",
                    "document_id",
                    "title",
                    "content_preview",
                    "chunk_index",
                    "content_sha256",
                    "page_start",
                    "page_end",
                    "language",
                ],
            )
            return hits
        except Exception:
            return []

    async def _enrich_from_pg(self, conn, chunk_id: str) -> dict[str, Any]:
        from infrastructure.postgres.transaction import fetch_one
        row = await fetch_one(
            conn,
            """
            SELECT d.id AS document_id, d.title AS document_title, d.author,
                   ch.chunk_index, ch.content, ch.content_length,
                   ch.page_start, ch.page_end, ch.chapter, ch.section,
                   ch.reference_label
            FROM library_document_chunks ch
            JOIN library_documents d ON d.id = ch.document_id
            WHERE ch.id = %(chunk_id)s
            """,
            {"chunk_id": chunk_id},
        )
        return dict(row) if row else {}

    def _classify_results(
        self,
        results: list[dict[str, Any]],
        expanded_terms: list[str],
    ) -> list[dict[str, Any]]:
        for r in results:
            content = r.get("content", r.get("content_preview", ""))
            vec_score = r.get("_vector_score")
            ev = self._classify_evidence(
                content, expanded_terms, vector_score=vec_score
            )
            r["_evidence"] = ev
        return results

    def _classify_evidence(
        self,
        content: str,
        query_terms: list[str],
        vector_score: float | None = None,
    ) -> EvidenceClassification:
        content_lower = content.lower()

        if DIRECT_QUOTE_PATTERNS.search(content):
            if self._any_term_in(content_lower, query_terms):
                return EvidenceClassification(
                    evidence_type=EvidenceLevel.direct_quote,
                    confidence="high",
                    notes="Contiene cita directa de fuente Breslov con términos de búsqueda.",
                )
            return EvidenceClassification(
                evidence_type=EvidenceLevel.direct_quote,
                confidence="medium",
                notes="Contiene cita directa de fuente Breslov. Los términos no aparecen literalmente en el fragmento.",
            )

        matching_terms = [t for t in query_terms if t.lower() in content_lower]
        if matching_terms:
            return EvidenceClassification(
                evidence_type=EvidenceLevel.literal,
                confidence="high",
                notes=f"Términos literales encontrados: {', '.join(matching_terms[:5])}.",
            )

        if vector_score is not None and vector_score > 0.65:
            return EvidenceClassification(
                evidence_type=EvidenceLevel.strong_thematic_reference,
                confidence="medium",
                notes=f"Similitud vectorial alta ({vector_score:.2f}). Relación temática sin términos exactos.",
            )

        if vector_score is not None and vector_score > 0.45:
            return EvidenceClassification(
                evidence_type=EvidenceLevel.remez_derash_inference,
                confidence="low",
                notes="Similitud vectorial moderada. Posible relación conceptual, no explícita.",
            )

        if vector_score is not None and vector_score > 0.35:
            return EvidenceClassification(
                evidence_type=EvidenceLevel.remez_derash_inference,
                confidence="low",
                notes="Similitud vectorial baja. Relación remota. No considerar cita.",
            )

        return EvidenceClassification(
            evidence_type=EvidenceLevel.not_found,
            confidence="none",
            notes="No hay evidencia suficiente en este fragmento.",
        )

    @staticmethod
    def _any_term_in(text: str, terms: list[str]) -> bool:
        return any(t.lower() in text for t in terms)

    def _build_source_map(
        self, results: list[dict[str, Any]]
    ) -> list[SourceMapEntry]:
        seen: set[str] = set()
        entries: list[SourceMapEntry] = []
        for r in results:
            cid = str(r.get("chunk_id", ""))
            if not cid or cid in seen:
                continue
            seen.add(cid)
            ev = r.get("_evidence", EvidenceClassification())
            content = r.get("content", "")
            entries.append(
                SourceMapEntry(
                    document_title=r.get("document_title", r.get("title", "")),
                    document_id=str(r.get("document_id", "")),
                    page_start=r.get("page_start"),
                    page_end=r.get("page_end"),
                    chunk_id=cid,
                    chunk_index=r.get("chunk_index", 0),
                    evidence=ev,
                    canonical_excerpt=self._excerpt(content, 300),
                    explanation=ev.notes if isinstance(ev, EvidenceClassification) else "",
                    limitations=self._entry_limitations(r, ev),
                )
            )
        return entries

    @staticmethod
    def _excerpt(content: str, max_len: int = 300) -> str:
        if not content:
            return ""
        return content[:max_len] + ("..." if len(content) > max_len else "")

    @staticmethod
    def _entry_limitations(
        r: dict[str, Any], ev: EvidenceClassification
    ) -> list[str]:
        limitations: list[str] = []
        if ev.evidence_type in (
            EvidenceLevel.remez_derash_inference,
            EvidenceLevel.not_found,
        ):
            limitations.append("No es una cita directa ni referencia explícita.")
        if r.get("page_start") is None:
            limitations.append("Sin referencia de página específica.")
        return limitations

    @staticmethod
    def _count_evidence(results: list[dict[str, Any]]) -> dict[str, int]:
        counts: dict[str, int] = {}
        for r in results:
            ev = r.get("_evidence", EvidenceClassification())
            et = ev.evidence_type.value if isinstance(ev, EvidenceClassification) else "unknown"
            counts[et] = counts.get(et, 0) + 1
        return counts

    def _build_limitations(
        self,
        analysis: ConversationAnalysisResult,
        results: list[dict[str, Any]],
        doc_count: int,
    ) -> list[str]:
        limitations: list[str] = [
            "Resultados basados en el corpus Breslov ES/EN actual (8 documentos, 5102 fragmentos).",
        ]
        if not results:
            limitations.append("No se encontraron resultados suficientes en el corpus.")
            return limitations

        has_literal = any(
            r.get("_evidence", EvidenceClassification()).evidence_type
            in (EvidenceLevel.literal, EvidenceLevel.direct_quote)
            for r in results
        )
        has_inference = any(
            r.get("_evidence", EvidenceClassification()).evidence_type
            == EvidenceLevel.remez_derash_inference
            for r in results
        )

        if not has_literal:
            limitations.append("No se encontraron citas literales. Los resultados son temáticos o inferenciales.")
        if has_inference:
            limitations.append("Algunos resultados son inferencia (remez/derash) y no deben citarse como fuentes directas.")
        if doc_count <= 1:
            limitations.append("Resultados limitados a un solo documento. Una búsqueda transversal en todo el corpus puede dar más resultados.")

        if analysis.analysis_fallback:
            limitations.append("El análisis conversacional usó el modo determinístico de respaldo (LiteLLM no disponible para análisis generativo).")

        return limitations

    @staticmethod
    def _build_summary(
        query: str,
        analysis: ConversationAnalysisResult,
        evidence_counts: dict[str, int],
        source_count: int,
    ) -> str:
        total = sum(evidence_counts.values())
        if total == 0:
            return (
                f"No se encontraron resultados para su consulta en el corpus Breslov "
                f"ES/EN actual (8 documentos, 5102 fragmentos). "
                f"Considere reformular la pregunta o explorar términos relacionados."
            )

        parts: list[str] = []
        parts.append(
            f"Se encontraron {total} fragmentos relevantes en "
            f"{source_count} documento(s) del corpus Breslov ES/EN."
        )

        lit = evidence_counts.get("literal", 0)
        dq = evidence_counts.get("direct_quote", 0)
        th = evidence_counts.get("strong_thematic_reference", 0)
        rz = evidence_counts.get("remez_derash_inference", 0)

        if dq:
            parts.append(f"{dq} contienen citas directas de fuentes Breslov.")
        if lit:
            parts.append(f"{lit} contienen términos literales de búsqueda.")
        if th:
            parts.append(f"{th} abordan el tema sin términos exactos.")
        if rz:
            parts.append(f"{rz} tienen relación conceptual remota (inferencia/remez).")

        return " ".join(parts)
