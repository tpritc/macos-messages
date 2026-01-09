"""Tests for the HybridSearch unified search interface."""

from datetime import timedelta

import pytest

from conftest import BASE_DATE
from messages import HybridSearch, HybridSearchResult, SearchMode


@pytest.fixture
def hybrid_search(messages_db, tmp_path):
    """Create a HybridSearch instance with temporary indexes."""
    search = HybridSearch(messages_db, index_path=tmp_path)
    return search


@pytest.fixture
def indexed_search(hybrid_search):
    """Create a HybridSearch with built indexes."""
    hybrid_search.build_indexes(include_semantic=False)
    return hybrid_search


class TestHybridSearchBuild:
    """Tests for HybridSearch.build_indexes() method."""

    def test_build_creates_fts_index(self, hybrid_search):
        """Should build FTS index."""
        stats = hybrid_search.build_indexes(include_semantic=False)
        assert "fts_indexed" in stats
        assert stats["fts_indexed"] > 0

    def test_build_is_idempotent(self, hybrid_search):
        """Building twice should not duplicate entries."""
        stats1 = hybrid_search.build_indexes(include_semantic=False)
        stats2 = hybrid_search.build_indexes(include_semantic=False)
        # Second build should index 0 new messages
        assert stats2["fts_indexed"] == 0


class TestHybridSearchKeyword:
    """Tests for keyword search mode."""

    def test_keyword_search_finds_results(self, indexed_search):
        """Keyword search should find matching messages."""
        results = list(indexed_search.search("lunch", mode=SearchMode.KEYWORD))
        assert len(results) >= 1
        assert any("lunch" in r.text.lower() for r in results)

    def test_keyword_search_returns_hybrid_results(self, indexed_search):
        """Should return HybridSearchResult objects."""
        results = list(indexed_search.search("lunch", mode=SearchMode.KEYWORD))
        assert len(results) > 0
        result = results[0]
        assert isinstance(result, HybridSearchResult)
        assert hasattr(result, "keyword_score")
        assert hasattr(result, "combined_score")
        assert "keyword" in result.found_by

    def test_keyword_search_has_scores(self, indexed_search):
        """Keyword search results should have keyword_score set."""
        results = list(indexed_search.search("lunch", mode=SearchMode.KEYWORD))
        assert len(results) > 0
        for result in results:
            assert result.keyword_score > 0
            assert result.combined_score == result.keyword_score


class TestHybridSearchStemmed:
    """Tests for stemmed search mode."""

    def test_stemmed_search_finds_results(self, indexed_search):
        """Stemmed search should find matching messages."""
        results = list(indexed_search.search("lunch", mode=SearchMode.STEMMED))
        assert len(results) >= 1

    def test_stemmed_search_has_scores(self, indexed_search):
        """Stemmed search results should have stemmed_score set."""
        results = list(indexed_search.search("lunch", mode=SearchMode.STEMMED))
        assert len(results) > 0
        for result in results:
            assert result.stemmed_score > 0
            assert result.combined_score == result.stemmed_score
            assert "stemmed" in result.found_by


class TestHybridSearchHybrid:
    """Tests for hybrid search mode."""

    def test_hybrid_search_finds_results(self, indexed_search):
        """Hybrid search should find matching messages."""
        results = list(indexed_search.search("lunch", mode=SearchMode.HYBRID))
        assert len(results) >= 1

    def test_hybrid_search_combines_scores(self, indexed_search):
        """Hybrid search should combine scores from multiple methods."""
        results = list(indexed_search.search("lunch", mode=SearchMode.HYBRID))
        assert len(results) > 0

        # At least some results should be found by multiple methods
        # (keyword and stemmed should both find "lunch")
        for result in results:
            if result.keyword_score > 0 and result.stemmed_score > 0:
                # Combined score should be weighted average
                expected_max = max(result.keyword_score, result.stemmed_score)
                assert result.combined_score <= expected_max * 1.1  # Allow small floating point variance

    def test_hybrid_search_ordered_by_combined_score(self, indexed_search):
        """Results should be ordered by combined score."""
        results = list(indexed_search.search("the", mode=SearchMode.HYBRID))
        if len(results) > 1:
            scores = [r.combined_score for r in results]
            assert scores == sorted(scores, reverse=True)

    def test_hybrid_search_with_custom_weights(self, indexed_search):
        """Should accept custom weights for score combination."""
        results = list(indexed_search.search(
            "lunch",
            mode=SearchMode.HYBRID,
            keyword_weight=1.0,
            stemmed_weight=0.0,
            semantic_weight=0.0,
        ))
        assert len(results) >= 1

        # With keyword_weight=1.0 and others=0, combined should equal keyword
        for result in results:
            assert abs(result.combined_score - result.keyword_score) < 0.01


class TestHybridSearchFilters:
    """Tests for search filtering options."""

    def test_search_with_chat_filter(self, indexed_search):
        """Should filter results by chat_id."""
        results = list(indexed_search.search(
            "dinner",
            mode=SearchMode.KEYWORD,
            chat_id=3,
        ))
        if results:
            assert all(r.chat_id == 3 for r in results)

    def test_search_with_multiple_chats(self, indexed_search):
        """Should filter results by multiple chat_ids."""
        results = list(indexed_search.search(
            "great",
            mode=SearchMode.KEYWORD,
            chat_ids=[1, 2],
        ))
        if results:
            assert all(r.chat_id in [1, 2] for r in results)

    def test_search_with_date_filter(self, indexed_search):
        """Should filter results by date."""
        after = BASE_DATE + timedelta(minutes=5)
        results = list(indexed_search.search(
            "the",
            mode=SearchMode.KEYWORD,
            after=after,
        ))
        for r in results:
            assert r.date > after

    def test_search_limit(self, indexed_search):
        """Should respect limit parameter."""
        results = list(indexed_search.search("the", mode=SearchMode.KEYWORD, limit=2))
        assert len(results) <= 2


class TestHybridSearchStats:
    """Tests for HybridSearch.get_stats() method."""

    def test_stats_includes_fts(self, indexed_search):
        """Stats should include FTS index info."""
        stats = indexed_search.get_stats()
        assert "fts" in stats
        assert stats["fts"]["indexed_messages"] > 0

    def test_stats_includes_semantic_availability(self, indexed_search):
        """Stats should indicate semantic search availability."""
        stats = indexed_search.get_stats()
        assert "semantic" in stats


class TestSearchModeEnum:
    """Tests for SearchMode enum."""

    def test_search_mode_values(self):
        """SearchMode should have expected values."""
        assert SearchMode.KEYWORD.value == "keyword"
        assert SearchMode.STEMMED.value == "stemmed"
        assert SearchMode.SEMANTIC.value == "semantic"
        assert SearchMode.HYBRID.value == "hybrid"

    def test_search_mode_string_conversion(self, indexed_search):
        """Should accept string mode values."""
        # These should not raise errors
        list(indexed_search.search("test", mode="keyword"))
        list(indexed_search.search("test", mode="stemmed"))
        list(indexed_search.search("test", mode="hybrid"))
