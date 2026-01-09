"""Tests for the EmbeddingIndex semantic search functionality."""

import pytest

from messages.embeddings import (
    EMBEDDINGS_AVAILABLE,
    EmbeddingIndex,
    SemanticSearchResult,
    _cosine_similarity,
    _deserialize_embedding,
    _serialize_embedding,
    get_available_models,
    is_available,
)


class TestEmbeddingUtils:
    """Tests for embedding utility functions."""

    def test_serialize_deserialize_embedding(self):
        """Should correctly round-trip embeddings through serialization."""
        original = [0.1, 0.2, 0.3, -0.5, 0.0, 1.0]
        serialized = _serialize_embedding(original)
        deserialized = _deserialize_embedding(serialized)

        assert len(deserialized) == len(original)
        for a, b in zip(original, deserialized):
            assert abs(a - b) < 1e-6  # Float precision

    def test_cosine_similarity_identical(self):
        """Identical vectors should have similarity of 1."""
        vec = [1.0, 2.0, 3.0]
        assert abs(_cosine_similarity(vec, vec) - 1.0) < 1e-6

    def test_cosine_similarity_orthogonal(self):
        """Orthogonal vectors should have similarity of 0."""
        vec_a = [1.0, 0.0, 0.0]
        vec_b = [0.0, 1.0, 0.0]
        assert abs(_cosine_similarity(vec_a, vec_b)) < 1e-6

    def test_cosine_similarity_opposite(self):
        """Opposite vectors should have similarity of -1."""
        vec_a = [1.0, 2.0, 3.0]
        vec_b = [-1.0, -2.0, -3.0]
        assert abs(_cosine_similarity(vec_a, vec_b) - (-1.0)) < 1e-6

    def test_cosine_similarity_zero_vector(self):
        """Zero vector should return 0 similarity."""
        vec_a = [0.0, 0.0, 0.0]
        vec_b = [1.0, 2.0, 3.0]
        assert _cosine_similarity(vec_a, vec_b) == 0.0

    def test_is_available(self):
        """Should return boolean indicating availability."""
        assert isinstance(is_available(), bool)
        assert is_available() == EMBEDDINGS_AVAILABLE

    def test_get_available_models(self):
        """Should return list of model info dictionaries."""
        models = get_available_models()
        assert isinstance(models, list)
        assert len(models) > 0

        for model in models:
            assert "name" in model
            assert "size_mb" in model
            assert "description" in model
            assert "dimensions" in model


@pytest.fixture
def embedding_index(tmp_path):
    """Create an EmbeddingIndex with a temporary database."""
    index_path = tmp_path / "embedding_index.db"
    return EmbeddingIndex(path=index_path)


class TestEmbeddingIndexSchema:
    """Tests for EmbeddingIndex schema and initialization."""

    def test_creates_database(self, embedding_index):
        """Should create the database file."""
        # Access conn to trigger database creation
        _ = embedding_index.conn
        assert embedding_index.path.exists()

    def test_stats_empty_index(self, embedding_index):
        """Should return stats for empty index."""
        stats = embedding_index.get_stats()
        assert stats["indexed_messages"] == 0
        assert stats["embedding_dimension"] is None
        assert stats["model_available"] == EMBEDDINGS_AVAILABLE


@pytest.mark.skipif(not EMBEDDINGS_AVAILABLE, reason="sentence-transformers not installed")
class TestEmbeddingIndexWithModel:
    """Tests that require sentence-transformers to be installed."""

    @pytest.fixture
    def populated_index(self, messages_db, tmp_path):
        """Create an EmbeddingIndex populated with test messages."""
        index_path = tmp_path / "embedding_index.db"
        index = EmbeddingIndex(path=index_path)
        index.build(messages_db)
        return index

    def test_build_indexes_messages(self, messages_db, embedding_index):
        """Should index messages from the database."""
        count = embedding_index.build(messages_db)
        assert count > 0

    def test_build_is_idempotent(self, messages_db, embedding_index):
        """Building twice should not duplicate entries."""
        count1 = embedding_index.build(messages_db)
        count2 = embedding_index.build(messages_db)
        # Second build should index 0 new messages
        assert count2 == 0
        # Total should still be the original count
        assert embedding_index._get_indexed_count() == count1

    def test_build_full_rebuild(self, messages_db, embedding_index):
        """Full rebuild should re-index all messages."""
        count1 = embedding_index.build(messages_db)
        count2 = embedding_index.build(messages_db, full_rebuild=True)
        # Full rebuild should re-index the same messages
        assert count2 == count1

    def test_search_returns_results(self, populated_index):
        """Semantic search should return results."""
        results = list(populated_index.search("lunch"))
        assert len(results) >= 1

    def test_search_returns_semantic_search_result(self, populated_index):
        """Should return SemanticSearchResult objects."""
        results = list(populated_index.search("lunch"))
        assert len(results) > 0
        result = results[0]
        assert isinstance(result, SemanticSearchResult)
        assert hasattr(result, "message_id")
        assert hasattr(result, "chat_id")
        assert hasattr(result, "text")
        assert hasattr(result, "date")
        assert hasattr(result, "similarity")

    def test_search_similarity_scores(self, populated_index):
        """Results should have similarity scores between 0 and 1."""
        results = list(populated_index.search("lunch"))
        assert len(results) > 0
        for result in results:
            assert 0 <= result.similarity <= 1

    def test_search_ordered_by_similarity(self, populated_index):
        """Results should be ordered by similarity (highest first)."""
        results = list(populated_index.search("meeting"))
        if len(results) > 1:
            similarities = [r.similarity for r in results]
            assert similarities == sorted(similarities, reverse=True)

    def test_search_limit(self, populated_index):
        """Should respect limit parameter."""
        results = list(populated_index.search("the", limit=2))
        assert len(results) <= 2

    def test_search_within_chat(self, populated_index):
        """Should filter search to specific chat_id."""
        results = list(populated_index.search("dinner", chat_id=3, min_similarity=0.1))
        if results:
            assert all(r.chat_id == 3 for r in results)

    def test_search_min_similarity_filter(self, populated_index):
        """Should filter results below min_similarity threshold."""
        # High threshold should return fewer results
        high_threshold = list(populated_index.search("lunch", min_similarity=0.8))
        low_threshold = list(populated_index.search("lunch", min_similarity=0.1))

        # Low threshold should return at least as many results
        assert len(low_threshold) >= len(high_threshold)

        # All results should meet their respective thresholds
        for result in high_threshold:
            assert result.similarity >= 0.8
        for result in low_threshold:
            assert result.similarity >= 0.1

    def test_stats_after_indexing(self, populated_index):
        """Stats should reflect indexed data."""
        stats = populated_index.get_stats()
        assert stats["indexed_messages"] > 0
        assert stats["embedding_dimension"] is not None
        assert stats["embedding_dimension"] > 0
        assert stats["model_name"] is not None


class TestEmbeddingIndexWithoutModel:
    """Tests for behavior when sentence-transformers is not available."""

    @pytest.mark.skipif(EMBEDDINGS_AVAILABLE, reason="Test requires sentence-transformers to NOT be installed")
    def test_build_raises_without_model(self, messages_db, embedding_index):
        """Should raise RuntimeError when trying to build without model."""
        with pytest.raises(RuntimeError, match="sentence-transformers not installed"):
            embedding_index.build(messages_db)

    @pytest.mark.skipif(EMBEDDINGS_AVAILABLE, reason="Test requires sentence-transformers to NOT be installed")
    def test_search_raises_without_model(self, embedding_index):
        """Should raise RuntimeError when trying to search without model."""
        with pytest.raises(RuntimeError, match="sentence-transformers not installed"):
            list(embedding_index.search("test"))
