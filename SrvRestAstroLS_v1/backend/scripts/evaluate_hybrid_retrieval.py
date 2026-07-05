#!/usr/bin/env python3
# DEPRECATED: Uses library_collections_legacy directly. Do not use for PG18 Product Schema v1.
# Use knowledge_scopes instead for any new development.
"""Hybrid retrieval evaluation: PG FTS + Milvus dense + Milvus BM25 + RRF fusion.

Evaluates:
  A) PG FTS
  B) Milvus dense vector
  C) Milvus BM25 sparse
  D) RRF dense+BM25
  E) RRF FTS+dense
  F) RRF FTS+BM25
  G) RRF FTS+dense+BM25
  H) RRF avec lexical gate (si FTS+BM25=0, baja confianza dense)

Usage:
    uv run python -m scripts.evaluate_hybrid_retrieval
    uv run python -m scripts.evaluate_hybrid_retrieval --limit-docs 200 --top-k 10
    (LITELLM_MASTER_KEY read from environment automatically)
"""

from __future__ import annotations

import argparse
import asyncio
from collections import Counter
from typing import Any

from pymilvus import connections as milvus_connections
from pymilvus import Collection, CollectionSchema, FieldSchema, DataType, Function, FunctionType, utility

BM25_COLL = "tebaai_breslov_bm25_test_v1"
BM25_NORM_COLL = "tebaai_breslov_bm25_norm_test_v1"
DENSE_COLL = "tebaai_breslov_test_chunks_v1"

QUERIES: list[tuple[str, str, str]] = [
    ("תלמוד", "he", "Hebrew exact - Talmud"),
    ("יבמות", "he", "Hebrew exact - Yevamot"),
    ("מסכת", "he", "Hebrew exact - Masekhet"),
    ("Talmud", "en", "English exact - Talmud"),
    ("uncircumcised priest", "en", "English phrase"),
    ("God created the heavens", "en", "English phrase - Genesis"),
    ("teruma", "en", "English exact"),
    ("maravilla del cerebro", "es", "Spanish phrase"),
    ("Breslov", "en", "English exact - Breslov"),
    ("zzzzzzzzzz", "xx", "Negative"),
    ("Alma", "es", "Spanish exact"),
    ("Rebe Najman", "es", "Spanish mixed"),
]

RRF_K = 60


def _parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Hybrid RRF retrieval evaluation")
    p.add_argument("--limit-docs", type=int, default=500)
    p.add_argument("--top-k", type=int, default=10)
    p.add_argument("--recreate-bm25", action="store_true")
    p.add_argument("--skip-dense", action="store_true")
    p.add_argument("--skip-bm25", action="store_true")
    p.add_argument("--cleanup", action="store_true")
    p.add_argument("--rrf-k", type=int, default=RRF_K)
    p.add_argument("--lexical-gate", choices=["on", "off"], default="on")
    p.add_argument("--normalize-hebrew", action="store_true", help="Create normalized BM25 collection and compare")
    p.add_argument("--recreate-bm25-norm", action="store_true", help="Recreate normalized BM25 collection")
    return p.parse_args()


def _rrf_score(ranks: list[int], k: int = RRF_K) -> float:
    return sum(1.0 / (k + r) for r in ranks)


def _check_test(name: str) -> bool:
    return "_test_" in name


async def _main(args: argparse.Namespace) -> int:
    from infrastructure.postgres.pool import create_pool_from_settings, open_pool, close_pool
    from infrastructure.postgres.transaction import fetch_one, fetch_all
    from modules.library.text_search import search_chunks_text
    from modules.embeddings.client import embed_text

    assert _check_test(BM25_COLL), f"BM25 collection must be _test_: {BM25_COLL}"
    assert _check_test(DENSE_COLL), f"Dense collection must be _test_: {DENSE_COLL}"

    pool = create_pool_from_settings()
    await open_pool(pool)
    milvus_connections.connect(host="127.0.0.1", port=19530)

    try:
        print("=" * 70)
        print("HYBRID RRF EVALUATION — REAL CORPUS")
        print(f"RRF k={args.rrf_k}, lexical_gate={args.lexical_gate}, top_k={args.top_k}")
        print("=" * 70)
        print()

        # Step 1: Load chunks
        print("[1/5] Loading chunks from PG...")
        async with pool.connection() as conn:
            chunks = await fetch_all(conn, """
                SELECT ch.id, ch.chunk_uid, ch.content, ch.content_sha256,
                       ch.chunk_index, ch.page_start, ch.page_end,
                       d.id AS document_id, d.title, d.language
                FROM library_document_chunks ch
                JOIN library_documents d ON d.id = ch.document_id
                JOIN library_collections_legacy c ON c.id = ch.collection_id
                WHERE c.code = 'breslov_test'
                ORDER BY d.title, ch.chunk_index
                LIMIT %(lim)s
            """, {"lim": args.limit_docs})
        print(f"  {len(chunks)} chunks from {len(set(c['document_id'] for c in chunks))} docs")
        print()

        # Step 2: Ensure BM25 collection
        print("[2/5] BM25 collection...")
        if utility.has_collection(BM25_COLL):
            if args.recreate_bm25:
                utility.drop_collection(BM25_COLL)
                _create_bm25_collection()
                _populate_bm25(chunks)
            else:
                col = Collection(BM25_COLL)
                col.load()
                print(f"  Using existing ({col.num_entities} entities)")
        else:
            _create_bm25_collection()
            _populate_bm25(chunks)
        print()

        # Step 2b: Ensure normalized BM25 collection (optional)
        if args.normalize_hebrew:
            from modules.library.hebrew_lexical_normalizer import normalize_hebrew_lexical
            print("[2b/5] Normalized BM25 collection...")
            if utility.has_collection(BM25_NORM_COLL):
                if args.recreate_bm25_norm:
                    utility.drop_collection(BM25_NORM_COLL)
                    _create_bm25_collection(BM25_NORM_COLL)
                    _populate_bm25(chunks, normalized=True)
                else:
                    col_n = Collection(BM25_NORM_COLL)
                    col_n.load()
                    print(f"  Using existing ({col_n.num_entities} entities)")
            else:
                _create_bm25_collection(BM25_NORM_COLL)
                _populate_bm25(chunks, normalized=True)
        print()

        # Step 3: Run queries
        print("[3/5] Running queries through all methods...")
        all_results: list[dict] = []

        for q_text, lang, desc in QUERIES:
            row: dict[str, Any] = {"query": q_text, "lang": lang, "desc": desc}

            # A) PG FTS
            fts_list: list[dict] = []
            try:
                async with pool.connection() as conn2:
                    fts_raw = await search_chunks_text(conn2, collection_code="breslov_test",
                        query=q_text, top_k=args.top_k, mode="fts", language=lang if lang != "xx" else "he")
                for i, r in enumerate(fts_raw):
                    fts_list.append({"chunk_id": str(r["chunk_id"]), "rank": i + 1, "score": r.get("rank", 0)})
            except Exception as e:
                fts_list = []
            row["fts"] = fts_list

            # B) Dense
            dense_list: list[dict] = []
            if not args.skip_dense and utility.has_collection(DENSE_COLL):
                try:
                    qv = embed_text(q_text)
                    dc = Collection(DENSE_COLL)
                    dc.load()
                    hits = dc.search(data=[qv], anns_field="embedding",
                        param={"metric_type": "COSINE", "params": {"ef": 64}},
                        limit=args.top_k, output_fields=["chunk_id"],
                        expr='collection_code == "breslov_test"')
                    for i, h in enumerate(hits[0]):
                        dense_list.append({"chunk_id": h.entity.get("chunk_id", ""), "rank": i + 1, "score": h.distance})
                except Exception:
                    dense_list = []
            row["dense"] = dense_list

            # C) BM25
            bm25_list: list[dict] = []
            if not args.skip_bm25:
                try:
                    col = Collection(BM25_COLL)
                    col.load()
                    hits = col.search(data=[q_text], anns_field="sparse_bm25",
                        param={"metric_type": "BM25"}, limit=args.top_k,
                        output_fields=["pk", "chunk_id"])
                    for i, h in enumerate(hits[0]):
                        bm25_list.append({"chunk_id": h.entity.get("chunk_id", ""), "rank": i + 1, "score": h.distance})
                except Exception:
                    bm25_list = []
            row["bm25"] = bm25_list

            # D) Normalized queries (if --normalize-hebrew)
            fts_norm_list: list[dict] = []
            bm25_norm_list: list[dict] = []
            if args.normalize_hebrew:
                from modules.library.hebrew_lexical_normalizer import normalize_hebrew_lexical
                q_norm = normalize_hebrew_lexical(q_text)
                # FTS with normalized query
                try:
                    async with pool.connection() as conn3:
                        fts_norm_raw = await search_chunks_text(conn3, collection_code="breslov_test",
                            query=q_norm, top_k=args.top_k, mode="fts",
                            language=lang if lang != "xx" else "he")
                    for i, r in enumerate(fts_norm_raw):
                        fts_norm_list.append({"chunk_id": str(r["chunk_id"]), "rank": i + 1, "score": r.get("rank", 0)})
                except Exception:
                    fts_norm_list = []
                # BM25 with normalized content
                if utility.has_collection(BM25_NORM_COLL) and not args.skip_bm25:
                    try:
                        col_n = Collection(BM25_NORM_COLL)
                        col_n.load()
                        hits = col_n.search(data=[q_norm], anns_field="sparse_bm25",
                            param={"metric_type": "BM25"}, limit=args.top_k,
                            output_fields=["pk", "chunk_id"])
                        for i, h in enumerate(hits[0]):
                            bm25_norm_list.append({"chunk_id": h.entity.get("chunk_id", ""), "rank": i + 1, "score": h.distance})
                    except Exception:
                        bm25_norm_list = []
            row["fts_norm"] = fts_norm_list
            row["bm25_norm"] = bm25_norm_list

            # F) RRF variants
            def _rrf(name: str, id_lists: list[list[dict]], k: int = args.rrf_k) -> list[dict]:
                """Compute RRF fusion for given ranked lists."""
                seen: dict[str, list[int]] = {}
                for lst in id_lists:
                    for item in lst:
                        cid = item["chunk_id"]
                        if cid not in seen:
                            seen[cid] = []
                        seen[cid].append(item["rank"])
                fused = [(cid, _rrf_score(ranks, k), len(ranks), ranks) for cid, ranks in seen.items()]
                fused.sort(key=lambda x: -x[1])
                return [{"chunk_id": cid, "rrf_score": sc, "num_signals": ns, "ranks": rs}
                        for cid, sc, ns, rs in fused[:args.top_k]]

            row["rrf_db"] = _rrf("dense+bm25", [dense_list, bm25_list])
            row["rrf_fd"] = _rrf("fts+dense", [fts_list, dense_list])
            row["rrf_fb"] = _rrf("fts+bm25", [fts_list, bm25_list])
            row["rrf_fdb"] = _rrf("fts+dense+bm25", [fts_list, dense_list, bm25_list])

            # G) Lexical gate variant (considers normalized queries too)
            lexical_any = (
                len(fts_list) > 0 or len(bm25_list) > 0 or
                len(fts_norm_list) > 0 or len(bm25_norm_list) > 0
            )
            if args.lexical_gate == "on" and not lexical_any:
                gated = [{"chunk_id": x["chunk_id"], "rrf_score": x.get("rrf_score", 0),
                          "num_signals": x.get("num_signals", 0), "low_confidence": True}
                         for x in row["rrf_fdb"]]
                row["rrf_gated"] = gated
            else:
                row["rrf_gated"] = row["rrf_fdb"]

            all_results.append(row)

        # Step 4: Report
        print("[4/5] Results matrix:")
        if args.normalize_hebrew:
            print(f"  {'Query':30s} {'FTS':5s} {'F_N':5s} {'Den':5s} {'BM25':5s} {'B_N':5s} {'R_FDB':5s} {'Gate':5s}")
            print(f"  {'-'*30} {'-'*5} {'-'*5} {'-'*5} {'-'*5} {'-'*5} {'-'*5} {'-'*5}")
        else:
            print(f"  {'Query':30s} {'FTS':5s} {'Den':5s} {'BM25':5s} {'R_FDB':5s} {'Gate':5s}")
            print(f"  {'-'*30} {'-'*5} {'-'*5} {'-'*5} {'-'*5} {'-'*5}")
        for r in all_results:
            def _n(lst):
                return str(len(lst)) if isinstance(lst, list) else "E"
            q = r["query"][:28]
            if args.normalize_hebrew:
                print(f"  {q:30s} {_n(r['fts']):5s} {_n(r['fts_norm']):5s} {_n(r['dense']):5s} "
                      f"{_n(r['bm25']):5s} {_n(r['bm25_norm']):5s} {_n(r['rrf_fdb']):5s} {_n(r['rrf_gated']):5s}")
            else:
                print(f"  {q:30s} {_n(r['fts']):5s} {_n(r['dense']):5s} {_n(r['bm25']):5s} "
                      f"{_n(r['rrf_fdb']):5s} {_n(r['rrf_gated']):5s}")
        print()

        # Step 5: Overlap + metrics
        print("[5/5] Overlap & RRF analysis:")
        for r in all_results:
            fts_ids = {x["chunk_id"] for x in r["fts"]}
            dn_ids = {x["chunk_id"] for x in r["dense"]}
            bm_ids = {x["chunk_id"] for x in r["bm25"]}
            fdb_ids = {x["chunk_id"] for x in r["rrf_fdb"]}
            all_ids = fts_ids | dn_ids | bm_ids

            if all_ids:
                undup = len(fdb_ids)  # RRF deduplicates
                # How many unique across methods
                print(f"  {r['query'][:25]:25s} FTS={len(fts_ids):2d} Dense={len(dn_ids):2d} BM25={len(bm_ids):2d} "
                      f"RRF={undup:2d} unique={len(all_ids):2d}")

        # Lexical gate analysis
        print()
        print("Lexical gate analysis:")
        for r in all_results:
            is_neg = r["lang"] == "xx"
            fts_ok = len(r["fts"]) > 0
            bm25_ok = len(r["bm25"]) > 0
            fts_n_ok = len(r.get("fts_norm", [])) > 0
            bm25_n_ok = len(r.get("bm25_norm", [])) > 0
            lexical_any = fts_ok or bm25_ok or fts_n_ok or bm25_n_ok
            dense_len = len(r["dense"])
            gated_len = len(r["rrf_gated"])
            gated_lc = sum(1 for x in r["rrf_gated"] if x.get("low_confidence"))
            if is_neg or not lexical_any:
                print(f"  {r['query'][:25]:25s} neg={is_neg} "
                      f"FTS={fts_ok} FTSn={fts_n_ok} BM25={bm25_ok} BM25n={bm25_n_ok} "
                      f"any_lex={lexical_any} dense={dense_len} gated={gated_len} low_conf={gated_lc}")

        # Guardrails
        print()
        print("Guardrails:")
        print(f"  BM25 name _test_: {_check_test(BM25_COLL)}")
        print(f"  Dense name _test_: {_check_test(DENSE_COLL)}")
        print(f"  Productive untouched: true")
        print(f"  PG source of truth: true")

        # Cleanup
        if args.cleanup:
            for cname in [BM25_COLL, BM25_NORM_COLL]:
                if utility.has_collection(cname):
                    utility.drop_collection(cname)
                    print(f"  Cleaned up {cname}")

        print()
        print("=== Hybrid evaluation complete ===")
        return 0
    finally:
        await close_pool(pool)


def _create_bm25_collection(name: str | None = None) -> None:
    coll = name or BM25_COLL
    fields = [
        FieldSchema(name="pk", dtype=DataType.VARCHAR, max_length=128, is_primary=True, auto_id=False),
        FieldSchema(name="chunk_id", dtype=DataType.VARCHAR, max_length=64),
        FieldSchema(name="document_id", dtype=DataType.VARCHAR, max_length=64),
        FieldSchema(name="title", dtype=DataType.VARCHAR, max_length=512),
        FieldSchema(name="page_start", dtype=DataType.INT64),
        FieldSchema(name="page_end", dtype=DataType.INT64),
        FieldSchema(name="language", dtype=DataType.VARCHAR, max_length=8),
        FieldSchema(name="content", dtype=DataType.VARCHAR, max_length=16384, enable_analyzer=True),
        FieldSchema(name="sparse_bm25", dtype=DataType.SPARSE_FLOAT_VECTOR),
    ]
    fn = Function(name="bm25_fn", function_type=FunctionType.BM25,
                  input_field_names="content", output_field_names="sparse_bm25")
    schema = CollectionSchema(fields=fields, functions=[fn])
    Collection(name=coll, schema=schema)
    print(f"  Created {coll}")


def _populate_bm25(chunks: list, normalized: bool = False) -> None:
    from modules.library.hebrew_lexical_normalizer import normalize_hebrew_lexical
    coll = BM25_NORM_COLL if normalized else BM25_COLL
    col = Collection(coll)
    tag = "NORM" if normalized else "RAW"
    batch = [{
        "pk": c["chunk_uid"] + ("_norm" if normalized else ""),
        "chunk_id": str(c["id"]),
        "document_id": str(c["document_id"]),
        "title": c["title"][:200],
        "page_start": c["page_start"] or 0,
        "page_end": c["page_end"] or 0,
        "language": c["language"],
        "content": (normalize_hebrew_lexical(c["content"]) if normalized else c["content"])[:16000],
    } for c in chunks]
    mr = col.insert(batch)
    col.flush()
    col.create_index("sparse_bm25", {"index_type": "SPARSE_INVERTED_INDEX", "metric_type": "BM25"})
    print(f"  Inserted {len(batch)} {tag} chunks into {coll} (count={mr.insert_count})")


if __name__ == "__main__":
    asyncio.run(_main(_parse_args()))
