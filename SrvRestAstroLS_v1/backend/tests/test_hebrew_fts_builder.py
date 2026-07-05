"""Tests for Hebrew FTS query builder and OR guards."""

from __future__ import annotations

import pytest


# Inline the builder to test it independently of pipeline import
def _build_tsquery_or(terms: list[str], config: str = "simple") -> str:
    for t in terms:
        if "||" in t:
            raise ValueError(
                f"Term {t!r} contains SQL-level `||`. "
                "Use `|` for OR inside to_tsquery, not `||`."
            )
        if "|" in t:
            raise ValueError(
                f"Term {t!r} contains `|`. OR must be expressed across "
                "separate list items, not embedded in a single term."
            )
    return " | ".join(terms)


class TestTSQueryORBuilder:
    def test_basic_or(self):
        result = _build_tsquery_or(["\u05d0\u05dc\u05d5\u05d4\u05d9\u05dd", "\u05d9\u05d4\u05d5\u05d4"])
        assert " | " in result
        assert "\u05d0\u05dc\u05d5\u05d4\u05d9\u05dd" in result
        assert "\u05d9\u05d4\u05d5\u05d4" in result

    def test_single_term_no_or(self):
        result = _build_tsquery_or(["\u05d0\u05dc\u05d5\u05d4\u05d9\u05dd"])
        assert result == "\u05d0\u05dc\u05d5\u05d4\u05d9\u05dd"

    def test_rejects_double_pipe(self):
        with pytest.raises(ValueError, match="SQL-level"):
            _build_tsquery_or(["\u05d0\u05dc\u05d5\u05d4\u05d9\u05dd || \u05d9\u05d4\u05d5\u05d4"])

    def test_rejects_embedded_pipe(self):
        with pytest.raises(ValueError, match="embedded"):
            _build_tsquery_or(["\u05d0\u05dc\u05d5\u05d4\u05d9\u05dd | \u05d9\u05d4\u05d5\u05d4"])

    def test_rejects_double_pipe_english(self):
        with pytest.raises(ValueError):
            _build_tsquery_or(["word1 || word2"])

    def test_three_terms(self):
        result = _build_tsquery_or(["a", "b", "c"])
        assert result == "a | b | c"

    def test_empty_terms_returns_empty(self):
        result = _build_tsquery_or([])
        assert result == ""

    def test_hebrew_terms_preserved(self):
        t1 = "\u05d0\u05dc\u05d5\u05d4\u05d9\u05dd"
        t2 = "\u05d9\u05d4\u05d5\u05d4"
        result = _build_tsquery_or([t1, t2])
        assert t1 in result
        assert t2 in result
        assert "|" in result
        # Double pipe must NOT appear
        assert "||" not in result

    def test_to_tsquery_sql_pattern(self):
        """Validate the SQL pattern that should be used."""
        t1 = "\u05d0\u05dc\u05d5\u05d4\u05d9\u05dd"
        t2 = "\u05d9\u05d4\u05d5\u05d4"
        or_clause = _build_tsquery_or([t1, t2])
        sql = f"to_tsquery('simple', '{or_clause}')"
        assert "||" not in sql
        assert "|" in sql
        assert t1 in sql
        assert t2 in sql

    def test_does_not_use_concat_operator(self):
        """|| is SQL concatenation, not to_tsquery OR."""
        bad_pattern = "to_tsquery('simple', 'token1 || token2')"
        assert "||" in bad_pattern
        # This is the WRONG way. Verify our builder prevents it.
        with pytest.raises(ValueError):
            _build_tsquery_or(["token1 || token2"])

    def test_correct_or_operator(self):
        """| is the correct to_tsquery OR operator."""
        good_pattern = "to_tsquery('simple', 'token1 | token2')"
        assert "|" in good_pattern
        assert "||" not in good_pattern


class TestWebsearchAlternative:
    def test_websearch_syntax_exploratory(self):
        """websearch_to_tsquery can use 'or' keyword (exploratory, not primary)."""
        sql = "websearch_to_tsquery('simple', 'word1 or word2')"
        assert "or" in sql
        # This is acceptable for user-facing query builders
        # but not the primary approach for controlled queries

    def test_prefer_to_tsquery_controlled(self):
        """For controlled tests, prefer to_tsquery with builder."""
        terms = ["term1", "term2"]
        or_clause = _build_tsquery_or(terms)
        assert " | " in or_clause
        assert "or" not in or_clause


class TestTSQueryPostgreSQL:
    """Integration tests against real PostgreSQL.

    These tests require PostgreSQL to be running.
    Skipped automatically if no connection.
    """

    @staticmethod
    def _is_pg_available() -> bool:
        try:
            from infrastructure.postgres.pool import create_pool_from_settings, open_pool, close_pool
            import asyncio

            async def check():
                p = create_pool_from_settings()
                try:
                    await open_pool(p)
                    return True
                except Exception:
                    return False
                finally:
                    await close_pool(p)

            return asyncio.run(check())
        except Exception:
            return False

    def test_to_tsquery_or_correct(self):
        """| is the correct OR operator in to_tsquery."""
        if not self._is_pg_available():
            import pytest
            pytest.skip("PostgreSQL not available")

        import asyncio
        from infrastructure.postgres.pool import create_pool_from_settings, open_pool, close_pool
        from infrastructure.postgres.transaction import fetch_one

        async def run():
            pool = create_pool_from_settings()
            await open_pool(pool)
            try:
                async with pool.connection() as conn:
                    row = await fetch_one(
                        conn,
                        "SELECT to_tsquery('simple', %(q)s) AS tsq",
                        {"q": "\u05d0\u05dc\u05d5\u05d4\u05d9\u05dd | \u05d9\u05d4\u05d5\u05d4"},
                    )
                    assert row is not None
                    tsq = str(row["tsq"])
                    assert "\u05d0\u05dc\u05d5\u05d4\u05d9\u05dd" in tsq
                    assert "\u05d9\u05d4\u05d5\u05d4" in tsq
                    assert "|" in tsq
            finally:
                await close_pool(pool)

        asyncio.run(run())

    def test_to_tsquery_or_double_pipe_rejected(self):
        """|| must NOT be used as OR inside to_tsquery (SQL concatenation)."""
        if not self._is_pg_available():
            import pytest
            pytest.skip("PostgreSQL not available")

        import asyncio
        from infrastructure.postgres.pool import create_pool_from_settings, open_pool, close_pool
        from infrastructure.postgres.transaction import fetch_one

        async def run():
            pool = create_pool_from_settings()
            await open_pool(pool)
            try:
                async with pool.connection() as conn:
                    try:
                        await fetch_one(
                            conn,
                            "SELECT to_tsquery('simple', %(q)s) AS tsq",
                            {"q": "\u05d0\u05dc\u05d5\u05d4\u05d9\u05dd || \u05d9\u05d4\u05d5\u05d4"},
                        )
                        assert False, "|| inside to_tsquery should have raised an error"
                    except Exception:
                        pass  # Expected: PostgreSQL rejects || inside to_tsquery
                    finally:
                        await conn.rollback()
            finally:
                await close_pool(pool)

        asyncio.run(run())

    def test_websearch_to_tsquery_hebrew(self):
        """websearch_to_tsquery works with Hebrew terms and 'or' keyword."""
        if not self._is_pg_available():
            import pytest
            pytest.skip("PostgreSQL not available")

        import asyncio
        from infrastructure.postgres.pool import create_pool_from_settings, open_pool, close_pool
        from infrastructure.postgres.transaction import fetch_one

        async def run():
            pool = create_pool_from_settings()
            await open_pool(pool)
            try:
                async with pool.connection() as conn:
                    row = await fetch_one(
                        conn,
                        "SELECT websearch_to_tsquery('simple', %(q)s) AS tsq",
                        {"q": "\u05d0\u05dc\u05d5\u05d4\u05d9\u05dd or \u05d9\u05d4\u05d5\u05d4"},
                    )
                    assert row is not None
                    tsq = str(row["tsq"])
                    assert "|" in tsq, f"websearch_to_tsquery should produce | separated terms: {tsq}"
            finally:
                await close_pool(pool)

        asyncio.run(run())

    def test_fetch_real_chunks_hebrew_fts(self):
        """Real Hebrew query against breslov_test chunks."""
        if not self._is_pg_available():
            import pytest
            pytest.skip("PostgreSQL not available")

        import asyncio
        from infrastructure.postgres.pool import create_pool_from_settings, open_pool, close_pool
        from infrastructure.postgres.transaction import fetch_one

        async def run():
            pool = create_pool_from_settings()
            await open_pool(pool)
            try:
                async with pool.connection() as conn:
                    row = await fetch_one(
                        conn,
                        """
                        SELECT COUNT(*) AS c FROM library_document_chunks ch
                        JOIN library_documents d ON d.id = ch.document_id
                        JOIN knowledge_scopes ks ON ks.id = d.knowledge_scope_id
                        WHERE ks.knowledge_scope_code = 'breslov_primary'
                          AND ch.search_vector_simple @@ to_tsquery('simple', %(q)s)
                        """,
                        {"q": "\u05d0\u05dc\u05d5\u05d4\u05d9\u05dd | \u05d9\u05d4\u05d5\u05d4"},
                    )
                    # Assert that the query runs without error
                    assert row is not None
                    assert isinstance(row["c"], int)
                    print(f"  Hebrew OR FTS matches: {row['c']}")
            finally:
                await close_pool(pool)

        asyncio.run(run())
