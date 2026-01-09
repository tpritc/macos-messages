"""Full-text search index for Messages using SQLite FTS5.

This module provides a persistent search index that enables fast full-text search
across messages. The index is stored separately from the Messages database to
allow read-only access to the original data while maintaining a local index.

The index supports:
- Full-text search with FTS5 (tokenization, boolean queries, phrase matching)
- Stemmed search using Snowball stemmer (matches word variants)
- Incremental updates (only index new messages)
- Relevance ranking with BM25

Usage:
    from messages import get_db
    from messages.search_index import SearchIndex

    db = get_db()
    index = SearchIndex()
    index.build(db)  # Build or update the index

    # Basic search (exact word matching)
    results = index.search("dinner plans")

    # Stemmed search (matches "running", "runner", "runs" for "run")
    results = index.search("running", stemmed=True)

    for result in results:
        print(f"Message {result.message_id}: {result.snippet}")
"""

import sqlite3
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING, Iterator, Optional

from .models import apple_time_to_datetime

if TYPE_CHECKING:
    from .db import MessagesDB


# Default index location in user's data directory
def get_default_index_path() -> Path:
    """Get the default path for the search index.

    Uses ~/Library/Application Support/macos-messages/ on macOS.
    """
    app_support = Path.home() / "Library" / "Application Support" / "macos-messages"
    app_support.mkdir(parents=True, exist_ok=True)
    return app_support / "search_index.db"


@dataclass
class SearchResult:
    """A search result with relevance information."""

    message_id: int
    chat_id: int
    text: str
    snippet: str  # Highlighted snippet showing match context
    date: datetime
    is_from_me: bool
    rank: float  # BM25 relevance score (lower is more relevant)


class SearchIndex:
    """Full-text search index using SQLite FTS5.

    The index maintains a copy of message text in an FTS5 virtual table
    for fast full-text search. It tracks which messages have been indexed
    to support incremental updates.
    """

    def __init__(self, path: Optional[Path | str] = None):
        """Initialize the search index.

        Args:
            path: Path to the index database. Defaults to app data directory.
        """
        self.path = Path(path) if path else get_default_index_path()
        self._conn: Optional[sqlite3.Connection] = None

    @property
    def conn(self) -> sqlite3.Connection:
        """Get database connection, creating if needed."""
        if self._conn is None:
            self._conn = sqlite3.connect(str(self.path))
            self._conn.row_factory = sqlite3.Row
            self._init_schema()
        return self._conn

    def _init_schema(self) -> None:
        """Create the index schema if it doesn't exist."""
        cursor = self.conn.cursor()

        # Create FTS5 virtual table for full-text search
        # We use unicode61 tokenizer for good Unicode support
        # Using content table for snippet support
        cursor.execute("""
            CREATE VIRTUAL TABLE IF NOT EXISTS messages_fts USING fts5(
                text,
                tokenize='unicode61 remove_diacritics 2'
            )
        """)

        # Create a separate FTS5 table for stemmed text
        # This enables matching word variants (run/running/runs)
        cursor.execute("""
            CREATE VIRTUAL TABLE IF NOT EXISTS messages_fts_stemmed USING fts5(
                text,
                tokenize='unicode61 remove_diacritics 2'
            )
        """)

        # Metadata table to track indexed messages
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS indexed_messages (
                message_id INTEGER PRIMARY KEY,
                chat_id INTEGER NOT NULL,
                date INTEGER NOT NULL,
                is_from_me INTEGER NOT NULL,
                text TEXT,
                fts_rowid INTEGER NOT NULL,
                fts_stemmed_rowid INTEGER
            )
        """)

        # Index for faster lookups
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_indexed_messages_date
            ON indexed_messages(date)
        """)

        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_indexed_messages_chat
            ON indexed_messages(chat_id)
        """)

        # Track index metadata
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS index_metadata (
                key TEXT PRIMARY KEY,
                value TEXT
            )
        """)

        self.conn.commit()

    def _get_last_indexed_date(self) -> Optional[int]:
        """Get the date of the most recently indexed message (Apple timestamp)."""
        cursor = self.conn.execute(
            "SELECT MAX(date) FROM indexed_messages"
        )
        row = cursor.fetchone()
        return row[0] if row and row[0] else None

    def _get_indexed_count(self) -> int:
        """Get the number of indexed messages."""
        cursor = self.conn.execute("SELECT COUNT(*) FROM indexed_messages")
        return cursor.fetchone()[0]

    def build(
        self,
        db: "MessagesDB",
        *,
        full_rebuild: bool = False,
        progress_callback: Optional[callable] = None,
    ) -> int:
        """Build or update the search index from the Messages database.

        Args:
            db: MessagesDB instance to read messages from
            full_rebuild: If True, rebuild the entire index from scratch
            progress_callback: Optional callback(indexed, total) for progress updates

        Returns:
            Number of messages indexed
        """
        if full_rebuild:
            self._clear_index()

        # Get all message IDs already indexed
        cursor = self.conn.execute("SELECT message_id FROM indexed_messages")
        indexed_ids = {row[0] for row in cursor}

        # Query all messages from the Messages database
        # We read directly from the database for efficiency
        messages_cursor = db.conn.execute("""
            SELECT m.ROWID, m.text, m.attributedBody, m.date, m.is_from_me,
                   cmj.chat_id
            FROM message m
            JOIN chat_message_join cmj ON m.ROWID = cmj.message_id
            WHERE (m.associated_message_type IS NULL OR m.associated_message_type = 0)
              AND (m.text IS NOT NULL AND m.text != '')
            ORDER BY m.date ASC
        """)

        indexed_count = 0
        batch = []
        batch_size = 1000

        for row in messages_cursor:
            message_id = row["ROWID"]

            # Skip already indexed messages
            if message_id in indexed_ids:
                continue

            text = row["text"]
            if not text:
                # Try to extract from attributedBody
                from .db import _extract_text_from_attributed_body
                text = _extract_text_from_attributed_body(row["attributedBody"])

            if not text:
                continue

            batch.append({
                "message_id": message_id,
                "chat_id": row["chat_id"],
                "date": row["date"],
                "is_from_me": row["is_from_me"],
                "text": text,
            })

            if len(batch) >= batch_size:
                self._index_batch(batch)
                indexed_count += len(batch)
                if progress_callback:
                    progress_callback(indexed_count, None)
                batch = []

        # Index remaining batch
        if batch:
            self._index_batch(batch)
            indexed_count += len(batch)

        return indexed_count

    def _index_batch(self, messages: list[dict]) -> None:
        """Index a batch of messages."""
        from .text_processing import process_text_for_index, STEMMER_AVAILABLE

        cursor = self.conn.cursor()

        for msg in messages:
            # Insert into FTS5 table (plain text)
            cursor.execute(
                "INSERT INTO messages_fts(text) VALUES (?)",
                (msg["text"],)
            )
            fts_rowid = cursor.lastrowid

            # Insert into stemmed FTS5 table
            fts_stemmed_rowid = None
            if STEMMER_AVAILABLE:
                stemmed_text = process_text_for_index(msg["text"])
                cursor.execute(
                    "INSERT INTO messages_fts_stemmed(text) VALUES (?)",
                    (stemmed_text,)
                )
                fts_stemmed_rowid = cursor.lastrowid

            # Insert into metadata table
            cursor.execute(
                """INSERT INTO indexed_messages
                   (message_id, chat_id, date, is_from_me, text, fts_rowid, fts_stemmed_rowid)
                   VALUES (?, ?, ?, ?, ?, ?, ?)""",
                (msg["message_id"], msg["chat_id"], msg["date"],
                 msg["is_from_me"], msg["text"], fts_rowid, fts_stemmed_rowid)
            )

        self.conn.commit()

    def _clear_index(self) -> None:
        """Clear the entire index."""
        cursor = self.conn.cursor()
        # Drop and recreate FTS tables for clean rebuild
        cursor.execute("DROP TABLE IF EXISTS messages_fts")
        cursor.execute("""
            CREATE VIRTUAL TABLE messages_fts USING fts5(
                text,
                tokenize='unicode61 remove_diacritics 2'
            )
        """)
        cursor.execute("DROP TABLE IF EXISTS messages_fts_stemmed")
        cursor.execute("""
            CREATE VIRTUAL TABLE messages_fts_stemmed USING fts5(
                text,
                tokenize='unicode61 remove_diacritics 2'
            )
        """)
        cursor.execute("DELETE FROM indexed_messages")
        self.conn.commit()

    def search(
        self,
        query: str,
        *,
        chat_id: Optional[int] = None,
        chat_ids: Optional[list[int]] = None,
        after: Optional[datetime] = None,
        before: Optional[datetime] = None,
        limit: int = 50,
        stemmed: bool = False,
    ) -> Iterator[SearchResult]:
        """Search the index using full-text search.

        Args:
            query: Search query (supports FTS5 syntax: AND, OR, NOT, "phrases")
            chat_id: Limit search to specific chat
            chat_ids: Limit search to multiple chats
            after: Only messages after this date
            before: Only messages before this date
            limit: Maximum results (default 50)
            stemmed: If True, use stemmed search for better word variant matching

        Yields:
            SearchResult objects ordered by relevance
        """
        from .models import datetime_to_apple_time

        # Process query for stemmed search if requested
        search_query = query
        if stemmed:
            from .text_processing import process_query_for_search, STEMMER_AVAILABLE
            if STEMMER_AVAILABLE:
                search_query = process_query_for_search(query)

        # Choose the appropriate FTS table
        fts_table = "messages_fts_stemmed" if stemmed else "messages_fts"
        fts_rowid_col = "fts_stemmed_rowid" if stemmed else "fts_rowid"

        # Build the query
        # We join FTS results with our metadata table
        sql = f"""
            SELECT
                im.message_id,
                im.chat_id,
                im.text,
                im.date,
                im.is_from_me,
                snippet({fts_table}, 0, '>>>', '<<<', '...', 32) as snippet,
                bm25({fts_table}) as rank
            FROM {fts_table}
            JOIN indexed_messages im ON {fts_table}.rowid = im.{fts_rowid_col}
            WHERE {fts_table} MATCH ?
        """
        params: list = [search_query]

        # Apply filters
        if chat_ids:
            placeholders = ",".join("?" * len(chat_ids))
            sql += f" AND im.chat_id IN ({placeholders})"
            params.extend(chat_ids)
        elif chat_id:
            sql += " AND im.chat_id = ?"
            params.append(chat_id)

        if after:
            sql += " AND im.date > ?"
            params.append(datetime_to_apple_time(after))

        if before:
            sql += " AND im.date < ?"
            params.append(datetime_to_apple_time(before))

        # Order by relevance (BM25 - lower is more relevant)
        sql += " ORDER BY rank"

        if limit:
            sql += " LIMIT ?"
            params.append(limit)

        try:
            cursor = self.conn.execute(sql, params)

            for row in cursor:
                yield SearchResult(
                    message_id=row["message_id"],
                    chat_id=row["chat_id"],
                    text=row["text"],
                    snippet=row["snippet"],
                    date=apple_time_to_datetime(row["date"]),
                    is_from_me=bool(row["is_from_me"]),
                    rank=row["rank"],
                )
        except sqlite3.OperationalError as e:
            # Handle FTS5 syntax errors gracefully
            if "fts5" in str(e).lower():
                # Try escaping the query as a simple phrase
                escaped_query = f'"{query}"'
                params[0] = escaped_query
                cursor = self.conn.execute(sql, params)
                for row in cursor:
                    yield SearchResult(
                        message_id=row["message_id"],
                        chat_id=row["chat_id"],
                        text=row["text"],
                        snippet=row["snippet"],
                        date=apple_time_to_datetime(row["date"]),
                        is_from_me=bool(row["is_from_me"]),
                        rank=row["rank"],
                    )
            else:
                raise

    def get_stats(self) -> dict:
        """Get statistics about the index.

        Returns:
            Dictionary with index statistics
        """
        from .text_processing import get_stemmer_info

        indexed_count = self._get_indexed_count()
        last_date = self._get_last_indexed_date()

        return {
            "indexed_messages": indexed_count,
            "last_indexed_date": apple_time_to_datetime(last_date) if last_date else None,
            "index_path": str(self.path),
            "index_size_bytes": self.path.stat().st_size if self.path.exists() else 0,
            "stemmer": get_stemmer_info(),
        }

    def close(self) -> None:
        """Close the database connection."""
        if self._conn:
            self._conn.close()
            self._conn = None
