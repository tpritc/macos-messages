"""Hybrid search combining multiple search strategies.

This module provides a unified search interface that combines:
- Full-text search (FTS5) for exact keyword matching
- Stemmed search for word variant matching
- Semantic search for meaning-based similarity

The hybrid approach provides the best of all worlds:
- Fast keyword search when you know exactly what you're looking for
- Flexible matching when you don't remember exact words
- Semantic understanding for natural language queries

Usage:
    from messages import get_db
    from messages.hybrid_search import HybridSearch

    db = get_db()
    search = HybridSearch(db)
    search.build_indexes()  # Build all indexes

    # Search using all methods combined
    results = search.search("meeting tomorrow", mode="hybrid")

    # Or use specific search modes
    results = search.search("lunch", mode="keyword")
    results = search.search("running", mode="stemmed")
    results = search.search("What time should we meet?", mode="semantic")
"""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import TYPE_CHECKING, Iterator, Optional

from .models import apple_time_to_datetime

if TYPE_CHECKING:
    from .db import MessagesDB


class SearchMode(Enum):
    """Available search modes."""

    KEYWORD = "keyword"  # FTS5 exact keyword matching
    STEMMED = "stemmed"  # Stemmed word variant matching
    SEMANTIC = "semantic"  # Embedding-based semantic search
    HYBRID = "hybrid"  # Combination of all methods


@dataclass
class HybridSearchResult:
    """A search result with combined scoring from multiple methods."""

    message_id: int
    chat_id: int
    text: str
    date: datetime
    is_from_me: bool

    # Individual scores from different methods (0-1 scale, higher is better)
    keyword_score: float = 0.0
    stemmed_score: float = 0.0
    semantic_score: float = 0.0

    # Combined score
    combined_score: float = 0.0

    # Which methods found this result
    found_by: list[str] = field(default_factory=list)

    # Snippet from keyword search (if available)
    snippet: Optional[str] = None


class HybridSearch:
    """Unified search interface combining multiple search strategies.

    This class orchestrates FTS5, stemmed, and semantic search to provide
    the most relevant results for any query type.
    """

    def __init__(
        self,
        db: "MessagesDB",
        *,
        index_path: Optional[Path | str] = None,
        embedding_model: str = "all-MiniLM-L6-v2",
    ):
        """Initialize hybrid search.

        Args:
            db: MessagesDB instance for database access
            index_path: Base path for index files. Defaults to app data directory.
            embedding_model: Model name for semantic search embeddings.
        """
        self.db = db
        self._index_path = Path(index_path) if index_path else self._get_default_path()
        self._embedding_model = embedding_model

        self._search_index: Optional["SearchIndex"] = None
        self._embedding_index: Optional["EmbeddingIndex"] = None

    def _get_default_path(self) -> Path:
        """Get the default path for indexes."""
        app_support = Path.home() / "Library" / "Application Support" / "macos-messages"
        app_support.mkdir(parents=True, exist_ok=True)
        return app_support

    @property
    def search_index(self) -> "SearchIndex":
        """Get or create the FTS/stemmed search index."""
        if self._search_index is None:
            from .search_index import SearchIndex

            self._search_index = SearchIndex(
                path=self._index_path / "search_index.db"
            )
        return self._search_index

    @property
    def embedding_index(self) -> "EmbeddingIndex":
        """Get or create the embedding index."""
        if self._embedding_index is None:
            from .embeddings import EmbeddingIndex

            self._embedding_index = EmbeddingIndex(
                path=self._index_path / "embedding_index.db",
                model_name=self._embedding_model,
            )
        return self._embedding_index

    def build_indexes(
        self,
        *,
        include_semantic: bool = True,
        full_rebuild: bool = False,
        progress_callback: Optional[callable] = None,
    ) -> dict:
        """Build all search indexes.

        Args:
            include_semantic: Whether to build semantic index (requires sentence-transformers)
            full_rebuild: If True, rebuild all indexes from scratch
            progress_callback: Optional callback(stage, indexed, total) for progress

        Returns:
            Dictionary with indexing statistics
        """
        stats = {}

        # Build FTS/stemmed index
        if progress_callback:
            progress_callback("fts", 0, None)

        fts_count = self.search_index.build(
            self.db,
            full_rebuild=full_rebuild,
            progress_callback=lambda i, t: progress_callback("fts", i, t) if progress_callback else None,
        )
        stats["fts_indexed"] = fts_count

        # Build semantic index if available and requested
        if include_semantic:
            from .embeddings import EMBEDDINGS_AVAILABLE

            if EMBEDDINGS_AVAILABLE:
                if progress_callback:
                    progress_callback("semantic", 0, None)

                semantic_count = self.embedding_index.build(
                    self.db,
                    full_rebuild=full_rebuild,
                    progress_callback=lambda i, t: progress_callback("semantic", i, t) if progress_callback else None,
                )
                stats["semantic_indexed"] = semantic_count
            else:
                stats["semantic_indexed"] = 0
                stats["semantic_available"] = False

        return stats

    def search(
        self,
        query: str,
        *,
        mode: SearchMode | str = SearchMode.HYBRID,
        chat_id: Optional[int] = None,
        chat_ids: Optional[list[int]] = None,
        after: Optional[datetime] = None,
        before: Optional[datetime] = None,
        limit: int = 50,
        keyword_weight: float = 0.4,
        stemmed_weight: float = 0.3,
        semantic_weight: float = 0.3,
    ) -> Iterator[HybridSearchResult]:
        """Search messages using the specified mode.

        Args:
            query: Search query
            mode: Search mode (keyword, stemmed, semantic, or hybrid)
            chat_id: Limit search to specific chat
            chat_ids: Limit search to multiple chats
            after: Only messages after this date
            before: Only messages before this date
            limit: Maximum results (default 50)
            keyword_weight: Weight for keyword search in hybrid mode (0-1)
            stemmed_weight: Weight for stemmed search in hybrid mode (0-1)
            semantic_weight: Weight for semantic search in hybrid mode (0-1)

        Yields:
            HybridSearchResult objects ordered by combined score
        """
        # Convert string mode to enum
        if isinstance(mode, str):
            mode = SearchMode(mode.lower())

        # Collect results from different methods based on mode
        results_by_id: dict[int, HybridSearchResult] = {}

        if mode in (SearchMode.KEYWORD, SearchMode.HYBRID):
            self._add_keyword_results(
                query, results_by_id,
                chat_id=chat_id, chat_ids=chat_ids,
                after=after, before=before,
                limit=limit * 2,  # Get more to allow for merging
            )

        if mode in (SearchMode.STEMMED, SearchMode.HYBRID):
            self._add_stemmed_results(
                query, results_by_id,
                chat_id=chat_id, chat_ids=chat_ids,
                after=after, before=before,
                limit=limit * 2,
            )

        if mode in (SearchMode.SEMANTIC, SearchMode.HYBRID):
            self._add_semantic_results(
                query, results_by_id,
                chat_id=chat_id, chat_ids=chat_ids,
                after=after, before=before,
                limit=limit * 2,
            )

        # Calculate combined scores for hybrid mode
        if mode == SearchMode.HYBRID:
            for result in results_by_id.values():
                result.combined_score = (
                    result.keyword_score * keyword_weight +
                    result.stemmed_score * stemmed_weight +
                    result.semantic_score * semantic_weight
                )
        else:
            # For single-mode searches, use the appropriate score
            for result in results_by_id.values():
                if mode == SearchMode.KEYWORD:
                    result.combined_score = result.keyword_score
                elif mode == SearchMode.STEMMED:
                    result.combined_score = result.stemmed_score
                elif mode == SearchMode.SEMANTIC:
                    result.combined_score = result.semantic_score

        # Sort by combined score and yield top results
        sorted_results = sorted(
            results_by_id.values(),
            key=lambda r: r.combined_score,
            reverse=True,
        )

        for result in sorted_results[:limit]:
            yield result

    def _add_keyword_results(
        self,
        query: str,
        results_by_id: dict[int, HybridSearchResult],
        **kwargs,
    ) -> None:
        """Add keyword search results to the results dictionary."""
        try:
            for result in self.search_index.search(query, stemmed=False, **kwargs):
                # Convert BM25 score to 0-1 scale (BM25 is lower=better)
                # Typical BM25 scores range from -10 to 0
                score = max(0, min(1, (10 + result.rank) / 10)) if result.rank else 0.5

                if result.message_id in results_by_id:
                    results_by_id[result.message_id].keyword_score = score
                    results_by_id[result.message_id].found_by.append("keyword")
                    if result.snippet:
                        results_by_id[result.message_id].snippet = result.snippet
                else:
                    results_by_id[result.message_id] = HybridSearchResult(
                        message_id=result.message_id,
                        chat_id=result.chat_id,
                        text=result.text,
                        date=result.date,
                        is_from_me=result.is_from_me,
                        keyword_score=score,
                        found_by=["keyword"],
                        snippet=result.snippet,
                    )
        except Exception:
            # If FTS search fails, continue with other methods
            pass

    def _add_stemmed_results(
        self,
        query: str,
        results_by_id: dict[int, HybridSearchResult],
        **kwargs,
    ) -> None:
        """Add stemmed search results to the results dictionary."""
        try:
            for result in self.search_index.search(query, stemmed=True, **kwargs):
                # Convert BM25 score to 0-1 scale
                score = max(0, min(1, (10 + result.rank) / 10)) if result.rank else 0.5

                if result.message_id in results_by_id:
                    results_by_id[result.message_id].stemmed_score = score
                    if "stemmed" not in results_by_id[result.message_id].found_by:
                        results_by_id[result.message_id].found_by.append("stemmed")
                else:
                    results_by_id[result.message_id] = HybridSearchResult(
                        message_id=result.message_id,
                        chat_id=result.chat_id,
                        text=result.text,
                        date=result.date,
                        is_from_me=result.is_from_me,
                        stemmed_score=score,
                        found_by=["stemmed"],
                        snippet=result.snippet,
                    )
        except Exception:
            # If stemmed search fails, continue with other methods
            pass

    def _add_semantic_results(
        self,
        query: str,
        results_by_id: dict[int, HybridSearchResult],
        **kwargs,
    ) -> None:
        """Add semantic search results to the results dictionary."""
        from .embeddings import EMBEDDINGS_AVAILABLE

        if not EMBEDDINGS_AVAILABLE:
            return

        try:
            # Remove stemmed parameter if present (not supported by semantic search)
            kwargs.pop("stemmed", None)

            for result in self.embedding_index.search(query, min_similarity=0.2, **kwargs):
                # Similarity is already 0-1 scale
                score = result.similarity

                if result.message_id in results_by_id:
                    results_by_id[result.message_id].semantic_score = score
                    if "semantic" not in results_by_id[result.message_id].found_by:
                        results_by_id[result.message_id].found_by.append("semantic")
                else:
                    results_by_id[result.message_id] = HybridSearchResult(
                        message_id=result.message_id,
                        chat_id=result.chat_id,
                        text=result.text,
                        date=result.date,
                        is_from_me=result.is_from_me,
                        semantic_score=score,
                        found_by=["semantic"],
                    )
        except Exception:
            # If semantic search fails (e.g., index not built), continue
            pass

    def get_stats(self) -> dict:
        """Get statistics about all search indexes.

        Returns:
            Dictionary with combined statistics
        """
        from .embeddings import EMBEDDINGS_AVAILABLE

        stats = {
            "fts": self.search_index.get_stats(),
        }

        if EMBEDDINGS_AVAILABLE:
            try:
                stats["semantic"] = self.embedding_index.get_stats()
            except Exception:
                stats["semantic"] = {"available": False, "error": "Index not built"}
        else:
            stats["semantic"] = {"available": False}

        return stats

    def close(self) -> None:
        """Close all index connections."""
        if self._search_index:
            self._search_index.close()
        if self._embedding_index:
            self._embedding_index.close()
