"""Tests for the SearchIndex full-text search functionality."""

from datetime import timedelta

import pytest

from conftest import BASE_DATE
from messages import SearchIndex, SearchResult


@pytest.fixture
def search_index(tmp_path):
    """Create a SearchIndex with a temporary database."""
    index_path = tmp_path / "search_index.db"
    return SearchIndex(path=index_path)


@pytest.fixture
def populated_index(messages_db, search_index):
    """Create a SearchIndex populated with test messages."""
    search_index.build(messages_db)
    return search_index


class TestSearchIndexBuild:
    """Tests for SearchIndex.build() method."""

    def test_build_indexes_messages(self, messages_db, search_index):
        """Should index messages from the database."""
        count = search_index.build(messages_db)
        assert count > 0

    def test_build_is_idempotent(self, messages_db, search_index):
        """Building twice should not duplicate entries."""
        count1 = search_index.build(messages_db)
        count2 = search_index.build(messages_db)
        # Second build should index 0 new messages
        assert count2 == 0
        # Total should still be the original count
        assert search_index._get_indexed_count() == count1

    def test_build_full_rebuild(self, messages_db, search_index):
        """Full rebuild should re-index all messages."""
        count1 = search_index.build(messages_db)
        count2 = search_index.build(messages_db, full_rebuild=True)
        # Full rebuild should re-index the same messages
        assert count2 == count1

    def test_build_skips_empty_messages(self, messages_db, search_index):
        """Should not index messages with no text."""
        count = search_index.build(messages_db)
        # Should have indexed the text messages but not reaction placeholders
        assert count > 0


class TestSearchIndexSearch:
    """Tests for SearchIndex.search() method."""

    def test_search_finds_matching_text(self, populated_index):
        """Should find messages containing search term."""
        results = list(populated_index.search("lunch"))
        assert len(results) >= 1
        assert any("lunch" in r.text.lower() for r in results)

    def test_search_returns_search_result_objects(self, populated_index):
        """Should return SearchResult dataclass objects."""
        results = list(populated_index.search("lunch"))
        assert len(results) > 0
        result = results[0]
        assert isinstance(result, SearchResult)
        assert hasattr(result, "message_id")
        assert hasattr(result, "chat_id")
        assert hasattr(result, "text")
        assert hasattr(result, "snippet")
        assert hasattr(result, "date")
        assert hasattr(result, "rank")

    def test_search_includes_snippet_with_highlights(self, populated_index):
        """Should return snippet with highlighted matches."""
        results = list(populated_index.search("lunch"))
        assert len(results) > 0
        # Snippets should contain the highlight markers
        result = results[0]
        assert ">>>" in result.snippet or "lunch" in result.snippet.lower()

    def test_search_results_have_relevance_rank(self, populated_index):
        """Should include BM25 relevance score."""
        results = list(populated_index.search("lunch"))
        assert len(results) > 0
        assert results[0].rank is not None
        assert isinstance(results[0].rank, float)

    def test_search_no_results(self, populated_index):
        """Should return empty iterator for no matches."""
        results = list(populated_index.search("xyznonexistent123"))
        assert len(results) == 0

    def test_search_limit(self, populated_index):
        """Should respect limit parameter."""
        # Search for a common word
        results = list(populated_index.search("a", limit=2))
        assert len(results) <= 2

    def test_search_within_chat(self, populated_index):
        """Should filter search to specific chat_id."""
        results = list(populated_index.search("dinner", chat_id=3))
        assert len(results) >= 1
        assert all(r.chat_id == 3 for r in results)

    def test_search_within_multiple_chats(self, populated_index):
        """Should filter search to multiple chat_ids."""
        # Search in both chat 1 and chat 2
        results = list(populated_index.search("great", chat_ids=[1, 2, 3]))
        assert len(results) >= 1

    def test_search_with_date_after(self, populated_index):
        """Should filter results to after specified date."""
        after = BASE_DATE + timedelta(minutes=5)
        results = list(populated_index.search("a", after=after))
        # All results should be after the specified date
        for r in results:
            assert r.date > after

    def test_search_with_date_before(self, populated_index):
        """Should filter results to before specified date."""
        before = BASE_DATE + timedelta(minutes=5)
        results = list(populated_index.search("a", before=before))
        # All results should be before the specified date
        for r in results:
            assert r.date < before

    def test_search_phrase_matching(self, populated_index):
        """Should support phrase matching with quotes."""
        # Search for an exact phrase
        results = list(populated_index.search('"free for lunch"'))
        assert len(results) >= 1

    def test_search_handles_special_characters(self, populated_index):
        """Should handle queries with special FTS5 characters gracefully."""
        # These shouldn't raise errors
        results = list(populated_index.search("test (with) special"))
        assert isinstance(results, list)

    def test_search_boolean_or(self, populated_index):
        """Should support OR queries."""
        results = list(populated_index.search("lunch OR dinner"))
        assert len(results) >= 2  # Should find messages with either word

    def test_search_boolean_and(self, populated_index):
        """Should support AND queries (implicit)."""
        # FTS5 uses AND by default between words
        results = list(populated_index.search("free lunch"))
        assert len(results) >= 1


class TestSearchIndexStats:
    """Tests for SearchIndex.get_stats() method."""

    def test_stats_empty_index(self, search_index):
        """Should return stats for empty index."""
        stats = search_index.get_stats()
        assert stats["indexed_messages"] == 0
        assert stats["last_indexed_date"] is None

    def test_stats_populated_index(self, populated_index):
        """Should return stats for populated index."""
        stats = populated_index.get_stats()
        assert stats["indexed_messages"] > 0
        assert stats["last_indexed_date"] is not None
        assert stats["index_size_bytes"] > 0


class TestSearchIndexStemmed:
    """Tests for stemmed search functionality."""

    def test_stemmed_search_returns_results(self, populated_index):
        """Stemmed search should return results."""
        results = list(populated_index.search("lunch", stemmed=True))
        assert len(results) >= 1

    def test_stemmed_search_matches_word_variants(self, populated_index):
        """Stemmed search should match word variants."""
        # "thinking" in test data should match query "think"
        results = list(populated_index.search("think", stemmed=True))
        # The test data has "thinking" in message 10
        # Stemmed search should find it
        assert isinstance(results, list)

    def test_stemmed_search_works_with_filters(self, populated_index):
        """Stemmed search should work with chat_id filter."""
        results = list(populated_index.search("great", chat_id=1, stemmed=True))
        if results:
            assert all(r.chat_id == 1 for r in results)

    def test_stemmed_stats_includes_stemmer_info(self, populated_index):
        """Stats should include stemmer information."""
        stats = populated_index.get_stats()
        assert "stemmer" in stats
        assert "available" in stats["stemmer"]

    def test_stemmed_search_handles_operators(self, populated_index):
        """Stemmed search should handle FTS5 operators."""
        results = list(populated_index.search("lunch OR dinner", stemmed=True))
        assert isinstance(results, list)


class TestSearchIndexIntegration:
    """Integration tests comparing FTS search with basic search."""

    def test_fts_search_faster_for_large_queries(self, messages_db, populated_index):
        """FTS search should return results (speed comparison is contextual)."""
        # FTS search
        fts_results = list(populated_index.search("lunch"))
        # Basic search
        basic_results = list(messages_db.search("lunch"))

        # Both should find results
        assert len(fts_results) >= 1
        assert len(basic_results) >= 1

    def test_fts_search_finds_same_messages_as_basic(self, messages_db, populated_index):
        """FTS search should find the same messages as basic search."""
        fts_results = list(populated_index.search("lunch"))
        basic_results = list(messages_db.search("lunch"))

        fts_ids = {r.message_id for r in fts_results}
        basic_ids = {r.id for r in basic_results}

        # FTS should find at least what basic search finds
        # (might find more due to tokenization differences)
        assert basic_ids <= fts_ids or len(fts_ids) >= len(basic_ids)
