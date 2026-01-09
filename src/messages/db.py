"""Database connection and queries for Messages.app data."""

import fnmatch
import re
import sqlite3
from collections.abc import Iterator
from datetime import datetime
from pathlib import Path

from .contacts import get_contact_name
from .models import (
    EFFECT_MAP,
    REACTION_TYPE_MAP,
    Attachment,
    Chat,
    ChatSummary,
    Handle,
    Message,
    Reaction,
    apple_time_to_datetime,
    datetime_to_apple_time,
)
from .phone import get_system_region, phone_match

DEFAULT_DB_PATH = Path.home() / "Library" / "Messages" / "chat.db"


def _extract_text_from_attributed_body(blob: bytes | None) -> str | None:
    """Extract plain text from NSAttributedString blob.

    The attributedBody column contains an NSKeyedArchiver-encoded
    NSAttributedString. The plain text is stored as a UTF-8 string
    after a type marker and length byte(s).

    Length encoding formats after + marker (0x2B):
    - Simple: + <1 byte length> <text> (length < 0x80, up to 127 bytes)
    - Extended: + 0x81 <2 bytes little-endian length> <text> (up to 65535 bytes)
    - Extended: + 0x82 <3 bytes little-endian length> <text>
    - Extended: + 0x83 <4 bytes little-endian length> <text>

    Alternative formats:
    - 0x4F 0x10 <1 byte>: length in next byte
    - 0x4F 0x11 <2 bytes>: length in next 2 bytes big-endian
    - I <4 byte big-endian length> <text>
    """
    if not blob:
        return None

    try:
        # Look for the NSString marker followed by the text
        text_section = blob.split(b"NSString")[1].split(b"NSDictionary")[0]

        # Try + marker format (most common)
        # Pattern: 0x2B <length encoding> <text bytes>
        plus_idx = text_section.find(b"+")
        if plus_idx != -1 and plus_idx + 2 < len(text_section):
            length_marker = text_section[plus_idx + 1]

            if length_marker < 0x80:
                # Simple 1-byte length (0-127)
                length = length_marker
                text_start = plus_idx + 2
            elif length_marker == 0x81:
                # Extended: 2 bytes little-endian length follow
                if plus_idx + 4 <= len(text_section):
                    length = int.from_bytes(text_section[plus_idx + 2 : plus_idx + 4], "little")
                    text_start = plus_idx + 4
                else:
                    length = 0
                    text_start = 0
            elif length_marker == 0x82:
                # Extended: 3 bytes little-endian length follow
                if plus_idx + 5 <= len(text_section):
                    length = int.from_bytes(text_section[plus_idx + 2 : plus_idx + 5], "little")
                    text_start = plus_idx + 5
                else:
                    length = 0
                    text_start = 0
            elif length_marker == 0x83:
                # Extended: 4 bytes little-endian length follow
                if plus_idx + 6 <= len(text_section):
                    length = int.from_bytes(text_section[plus_idx + 2 : plus_idx + 6], "little")
                    text_start = plus_idx + 6
                else:
                    length = 0
                    text_start = 0
            else:
                length = 0
                text_start = 0

            if length > 0 and text_start + length <= len(text_section):
                text_bytes = text_section[text_start : text_start + length]
                result = text_bytes.decode("utf-8", errors="ignore").strip()
                if result:
                    return result

        # Try bplist-style extended length encoding (alternative format)
        # Look for 0x4F which indicates extended length encoding
        for i in range(len(text_section) - 2):
            if text_section[i] == 0x4F:  # Extended length marker
                size_marker = text_section[i + 1]
                if size_marker == 0x10:  # 1-byte length
                    length = text_section[i + 2]
                    start = i + 3
                    if start + length <= len(text_section):
                        text_bytes = text_section[start : start + length]
                        result = text_bytes.decode("utf-8", errors="ignore").strip()
                        if result and len(result) >= 1:
                            return result
                elif size_marker == 0x11:  # 2-byte length (big-endian)
                    if i + 4 <= len(text_section):
                        length = int.from_bytes(text_section[i + 2 : i + 4], "big")
                        start = i + 4
                        if 0 < length < 100000 and start + length <= len(text_section):
                            text_bytes = text_section[start : start + length]
                            result = text_bytes.decode("utf-8", errors="ignore").strip()
                            if result and len(result) >= 1:
                                return result
                elif size_marker == 0x12:  # 4-byte length (big-endian)
                    if i + 6 <= len(text_section):
                        length = int.from_bytes(text_section[i + 2 : i + 6], "big")
                        start = i + 6
                        if 0 < length < 100000 and start + length <= len(text_section):
                            text_bytes = text_section[start : start + length]
                            result = text_bytes.decode("utf-8", errors="ignore").strip()
                            if result and len(result) >= 1:
                                return result

        # Legacy format: I marker (0x49) for longer texts
        # Pattern: I <4-byte length> <text>
        i_idx = text_section.find(b"I")
        if i_idx != -1 and i_idx + 5 < len(text_section):
            # 4-byte big-endian length after I
            length = int.from_bytes(text_section[i_idx + 1 : i_idx + 5], "big")
            if 0 < length < 100000 and i_idx + 5 + length <= len(text_section):
                text_bytes = text_section[i_idx + 5 : i_idx + 5 + length]
                result = text_bytes.decode("utf-8", errors="ignore").strip()
                if result:
                    return result

    except (IndexError, UnicodeDecodeError, ValueError):
        pass

    # Fallback: try to find any readable text in the blob
    try:
        if b"streamtyped" in blob:
            parts = blob.split(b"NSString")
            if len(parts) > 1:
                text_part = parts[1]
                # Find printable ASCII/UTF-8 sequences (at least 4 chars)
                matches = re.findall(rb"[\x20-\x7e\xc0-\xff]{4,}", text_part)
                if matches:
                    for m in matches:
                        try:
                            decoded = m.decode("utf-8", errors="ignore").strip()
                            # Skip metadata-looking strings
                            if decoded and not decoded.startswith(("NS", "{")):
                                return decoded
                        except UnicodeDecodeError:
                            continue
    except Exception:
        pass

    return None


class MessagesDB:
    """Read-only interface to the Messages database."""

    def __init__(self, path: Path | str | None = None, resolve_contacts: bool = True):
        """Initialize database connection.

        Args:
            path: Path to chat.db. Defaults to ~/Library/Messages/chat.db
            resolve_contacts: If True, resolve phone/email to contact names
        """
        self.path = Path(path) if path else DEFAULT_DB_PATH
        self.resolve_contacts = resolve_contacts
        self._conn: sqlite3.Connection | None = None
        self._region: str | None = None

    @property
    def conn(self) -> sqlite3.Connection:
        """Get database connection, creating if needed."""
        if self._conn is None:
            if not self.path.exists():
                raise FileNotFoundError(f"Database not found: {self.path}")
            try:
                self._conn = sqlite3.connect(
                    f"file:{self.path}?mode=ro",
                    uri=True,
                    check_same_thread=False,
                )
                self._conn.row_factory = sqlite3.Row
            except sqlite3.OperationalError as e:
                if "unable to open" in str(e).lower():
                    raise PermissionError(
                        "Cannot read Messages database. "
                        "Grant Full Disk Access to Terminal in "
                        "System Settings > Privacy & Security > Full Disk Access"
                    ) from e
                raise
        return self._conn

    @property
    def region(self) -> str:
        """User's region code for phone number parsing."""
        if self._region is None:
            self._region = get_system_region()
        return self._region

    def _resolve_handle(self, handle_id: int | None) -> Handle | None:
        """Look up a handle by ID and optionally resolve contact name."""
        if handle_id is None:
            return None

        cursor = self.conn.execute(
            "SELECT ROWID, id, service FROM handle WHERE ROWID = ?",
            (handle_id,),
        )
        row = cursor.fetchone()
        if not row:
            return None

        display_name = None
        if self.resolve_contacts:
            display_name = get_contact_name(row["id"])

        return Handle(
            id=row["ROWID"],
            identifier=row["id"],
            service=row["service"],
            display_name=display_name,
        )

    def _get_reactions_for_message(self, message_guid: str) -> list[Reaction]:
        """Get all reactions for a message by its GUID."""
        reactions = []

        cursor = self.conn.execute(
            """
            SELECT m.ROWID, m.date, m.associated_message_type, m.handle_id
            FROM message m
            WHERE m.associated_message_guid = ?
              AND m.associated_message_type >= 2000
              AND m.associated_message_type <= 2005
            ORDER BY m.date
            """,
            (message_guid,),
        )

        for row in cursor:
            reaction_type = REACTION_TYPE_MAP.get(row["associated_message_type"])
            if reaction_type:
                sender = self._resolve_handle(row["handle_id"])
                if sender:
                    reactions.append(
                        Reaction(
                            type=reaction_type,
                            sender=sender,
                            date=apple_time_to_datetime(row["date"]),
                        )
                    )

        return reactions

    def _row_to_message(self, row: sqlite3.Row, chat_id: int) -> Message:
        """Convert a database row to a Message object."""
        # Get reactions
        reactions = self._get_reactions_for_message(row["guid"])

        # Parse effect
        effect = None
        if row["expressive_send_style_id"]:
            effect = EFFECT_MAP.get(row["expressive_send_style_id"])

        # Get sender handle
        sender = None
        if not row["is_from_me"] and row["handle_id"]:
            sender = self._resolve_handle(row["handle_id"])

        # Get reply_to_id from thread_originator_guid
        reply_to_id = None
        if row["thread_originator_guid"]:
            cursor = self.conn.execute(
                "SELECT ROWID FROM message WHERE guid = ?",
                (row["thread_originator_guid"],),
            )
            reply_row = cursor.fetchone()
            if reply_row:
                reply_to_id = reply_row["ROWID"]

        # Get text, falling back to attributedBody if text is empty
        text = row["text"]
        if not text and "attributedBody" in row.keys():
            text = _extract_text_from_attributed_body(row["attributedBody"])

        return Message(
            id=row["ROWID"],
            chat_id=chat_id,
            text=text,
            date=apple_time_to_datetime(row["date"]),
            is_from_me=bool(row["is_from_me"]),
            sender=sender,
            has_attachments=bool(row["cache_has_attachments"]),
            reactions=reactions,
            effect=effect,
            is_edited=bool(row["date_edited"]),
            is_unsent=bool(row["date_retracted"]),
            reply_to_id=reply_to_id,
        )

    def chats(
        self,
        *,
        service: str | None = None,
        limit: int | None = None,
    ) -> Iterator[ChatSummary]:
        """List all chats, ordered by most recent activity.

        Args:
            service: Filter by service ("iMessage", "SMS", "RCS")
            limit: Maximum number of results

        Yields:
            ChatSummary objects
        """
        query = """
            SELECT
                c.ROWID,
                c.chat_identifier,
                c.display_name,
                c.service_name,
                COUNT(cmj.message_id) as message_count,
                MAX(m.date) as last_message_date
            FROM chat c
            LEFT JOIN chat_message_join cmj ON c.ROWID = cmj.chat_id
            LEFT JOIN message m ON cmj.message_id = m.ROWID
                AND (m.associated_message_type IS NULL OR m.associated_message_type = 0)
        """
        params: list = []

        if service:
            query += " WHERE c.service_name = ?"
            params.append(service)

        query += """
            GROUP BY c.ROWID
            ORDER BY last_message_date DESC NULLS LAST
        """

        if limit:
            query += " LIMIT ?"
            params.append(limit)

        cursor = self.conn.execute(query, params)

        for row in cursor:
            # Try to resolve display name for 1:1 chats
            display_name = row["display_name"]
            if not display_name and self.resolve_contacts:
                display_name = get_contact_name(row["chat_identifier"])

            yield ChatSummary(
                id=row["ROWID"],
                identifier=row["chat_identifier"],
                display_name=display_name,
                service=row["service_name"],
                message_count=row["message_count"] or 0,
                last_message_date=apple_time_to_datetime(row["last_message_date"]),
            )

    def chat(self, chat_id: int) -> Chat:
        """Get a single chat by ID with full details.

        Args:
            chat_id: Chat ID

        Returns:
            Chat object with participants

        Raises:
            LookupError: If chat not found
        """
        cursor = self.conn.execute(
            """
            SELECT ROWID, chat_identifier, display_name, service_name
            FROM chat
            WHERE ROWID = ?
            """,
            (chat_id,),
        )
        row = cursor.fetchone()
        if not row:
            raise LookupError(f"Chat {chat_id} not found")

        # Get participants
        participants = []
        cursor = self.conn.execute(
            """
            SELECT h.ROWID, h.id, h.service
            FROM handle h
            JOIN chat_handle_join chj ON h.ROWID = chj.handle_id
            WHERE chj.chat_id = ?
            """,
            (chat_id,),
        )
        for handle_row in cursor:
            display_name = None
            if self.resolve_contacts:
                display_name = get_contact_name(handle_row["id"])
            participants.append(
                Handle(
                    id=handle_row["ROWID"],
                    identifier=handle_row["id"],
                    service=handle_row["service"],
                    display_name=display_name,
                )
            )

        display_name = row["display_name"]
        if not display_name and self.resolve_contacts:
            display_name = get_contact_name(row["chat_identifier"])

        return Chat(
            id=row["ROWID"],
            identifier=row["chat_identifier"],
            display_name=display_name,
            service=row["service_name"],
            participants=participants,
        )

    def chat_by_identifier(self, identifier: str) -> Chat:
        """Get a chat by phone number or email.

        Uses smart phone number matching for international format support.

        Args:
            identifier: Phone number (any format) or email

        Returns:
            Chat object

        Raises:
            LookupError: If no matching chat found
        """
        cursor = self.conn.execute("SELECT ROWID, chat_identifier FROM chat")

        for row in cursor:
            if phone_match(identifier, row["chat_identifier"], self.region):
                return self.chat(row["ROWID"])

        # Also check handles in case the chat_identifier is different
        cursor = self.conn.execute(
            """
            SELECT DISTINCT chj.chat_id, h.id
            FROM handle h
            JOIN chat_handle_join chj ON h.ROWID = chj.handle_id
            """
        )

        for row in cursor:
            if phone_match(identifier, row["id"], self.region):
                return self.chat(row["chat_id"])

        raise LookupError(f"Chat not found for identifier: {identifier}")

    def messages(
        self,
        *,
        chat_id: int | None = None,
        chat_ids: list[int] | None = None,
        identifier: str | None = None,
        after: datetime | None = None,
        before: datetime | None = None,
        limit: int = 100,
        offset: int = 0,
        include_unsent: bool = True,
        reverse: bool = False,
    ) -> Iterator[Message]:
        """List messages from a conversation.

        Args:
            chat_id: Filter by chat ID (single chat)
            chat_ids: Filter by multiple chat IDs (merges messages from all chats)
            identifier: Filter by phone/email (alternative to chat_id)
            after: Only messages after this date
            before: Only messages before this date
            limit: Maximum results (default 100)
            offset: Skip first N results
            include_unsent: Include messages that were unsent (default True)
            reverse: If True, return newest messages first (default False)

        Yields:
            Message objects with reactions aggregated
        """
        # If identifier provided, find the chat first
        if identifier and not chat_id and not chat_ids:
            chat = self.chat_by_identifier(identifier)
            chat_id = chat.id

        # Normalize to a list of chat IDs
        if chat_ids:
            target_chat_ids = chat_ids
        elif chat_id:
            target_chat_ids = [chat_id]
        else:
            raise ValueError("Either chat_id, chat_ids, or identifier must be provided")

        # Validate all chat IDs exist
        for cid in target_chat_ids:
            cursor = self.conn.execute("SELECT 1 FROM chat WHERE ROWID = ?", (cid,))
            if cursor.fetchone() is None:
                raise LookupError(f"Chat {cid} not found")

        if limit == 0:
            return

        # Build query with IN clause for multiple chat IDs
        placeholders = ",".join("?" * len(target_chat_ids))
        query = f"""
            SELECT m.ROWID, m.guid, m.text, m.attributedBody, m.date, m.is_from_me, m.handle_id,
                   m.cache_has_attachments, m.expressive_send_style_id,
                   m.date_edited, m.date_retracted, m.thread_originator_guid,
                   cmj.chat_id
            FROM message m
            JOIN chat_message_join cmj ON m.ROWID = cmj.message_id
            WHERE cmj.chat_id IN ({placeholders})
              AND (m.associated_message_type IS NULL OR m.associated_message_type = 0)
        """
        params: list = list(target_chat_ids)

        if not include_unsent:
            query += " AND (m.date_retracted IS NULL OR m.date_retracted = 0)"

        if after:
            query += " AND m.date > ?"
            params.append(datetime_to_apple_time(after))

        if before:
            query += " AND m.date < ?"
            params.append(datetime_to_apple_time(before))

        if reverse:
            query += " ORDER BY m.date DESC"
        else:
            query += " ORDER BY m.date ASC"

        if limit:
            query += " LIMIT ?"
            params.append(limit)

        if offset:
            query += " OFFSET ?"
            params.append(offset)

        cursor = self.conn.execute(query, params)

        for row in cursor:
            yield self._row_to_message(row, row["chat_id"])

    def message(self, message_id: int) -> Message:
        """Get a single message by ID with full details.

        Args:
            message_id: Message ID

        Returns:
            Message object

        Raises:
            LookupError: If message not found
        """
        cursor = self.conn.execute(
            """
            SELECT m.ROWID, m.guid, m.text, m.attributedBody, m.date, m.is_from_me, m.handle_id,
                   m.cache_has_attachments, m.expressive_send_style_id,
                   m.date_edited, m.date_retracted, m.thread_originator_guid,
                   cmj.chat_id
            FROM message m
            LEFT JOIN chat_message_join cmj ON m.ROWID = cmj.message_id
            WHERE m.ROWID = ?
            """,
            (message_id,),
        )
        row = cursor.fetchone()
        if not row:
            raise LookupError(f"Message {message_id} not found")

        return self._row_to_message(row, row["chat_id"] or 0)

    def search(
        self,
        query: str,
        *,
        chat_id: int | None = None,
        chat_ids: list[int] | None = None,
        after: datetime | None = None,
        before: datetime | None = None,
        limit: int = 50,
    ) -> Iterator[Message]:
        """Search messages by text content.

        Args:
            query: Search string (case-insensitive substring match)
            chat_id: Limit search to specific chat
            chat_ids: Limit search to multiple chats (merges results)
            after: Only messages after this date
            before: Only messages before this date
            limit: Maximum results (default 50)

        Yields:
            Message objects with matching text
        """
        sql = """
            SELECT m.ROWID, m.guid, m.text, m.attributedBody, m.date, m.is_from_me, m.handle_id,
                   m.cache_has_attachments, m.expressive_send_style_id,
                   m.date_edited, m.date_retracted, m.thread_originator_guid,
                   cmj.chat_id
            FROM message m
            LEFT JOIN chat_message_join cmj ON m.ROWID = cmj.message_id
            WHERE m.text LIKE ?
              AND (m.associated_message_type IS NULL OR m.associated_message_type = 0)
        """
        params: list = [f"%{query}%"]

        # Handle single chat_id or multiple chat_ids
        if chat_ids:
            placeholders = ",".join("?" * len(chat_ids))
            sql += f" AND cmj.chat_id IN ({placeholders})"
            params.extend(chat_ids)
        elif chat_id:
            sql += " AND cmj.chat_id = ?"
            params.append(chat_id)

        if after:
            sql += " AND m.date > ?"
            params.append(datetime_to_apple_time(after))

        if before:
            sql += " AND m.date < ?"
            params.append(datetime_to_apple_time(before))

        sql += " ORDER BY m.date DESC"

        if limit:
            sql += " LIMIT ?"
            params.append(limit)

        cursor = self.conn.execute(sql, params)

        for row in cursor:
            yield self._row_to_message(row, row["chat_id"] or 0)

    def attachments(
        self,
        *,
        chat_id: int | None = None,
        message_id: int | None = None,
        mime_type: str | None = None,
        limit: int = 100,
        auto_download: bool = True,
    ) -> Iterator[Attachment]:
        """List attachments.

        Args:
            chat_id: Filter by chat
            message_id: Filter by specific message
            mime_type: Filter by type (e.g., "image/png", "image/*")
            limit: Maximum results
            auto_download: If True, download iCloud attachments automatically (not yet implemented)

        Yields:
            Attachment objects
        """
        query = """
            SELECT DISTINCT a.ROWID, a.filename, a.mime_type, a.total_bytes,
                   a.is_sticker, a.transfer_name, maj.message_id
            FROM attachment a
            JOIN message_attachment_join maj ON a.ROWID = maj.attachment_id
        """
        params: list = []
        conditions = []

        if message_id:
            conditions.append("maj.message_id = ?")
            params.append(message_id)

        if chat_id:
            query += " JOIN chat_message_join cmj ON maj.message_id = cmj.message_id"
            conditions.append("cmj.chat_id = ?")
            params.append(chat_id)

        if conditions:
            query += " WHERE " + " AND ".join(conditions)

        query += " ORDER BY a.ROWID DESC"

        if limit:
            query += " LIMIT ?"
            params.append(limit)

        cursor = self.conn.execute(query, params)

        for row in cursor:
            # Check mime_type filter (supports wildcards like "image/*")
            if mime_type:
                row_mime = row["mime_type"] or ""
                if not fnmatch.fnmatch(row_mime, mime_type):
                    continue

            # Use transfer_name as filename if filename is a path
            filename = row["transfer_name"] or row["filename"] or ""
            if "/" in filename:
                filename = filename.split("/")[-1]

            yield Attachment(
                id=row["ROWID"],
                message_id=row["message_id"],
                filename=filename,
                mime_type=row["mime_type"],
                path=row["filename"] or "",
                size=row["total_bytes"] or 0,
                is_sticker=bool(row["is_sticker"]),
            )

    def download_attachment(self, attachment: Attachment) -> Path:
        """Ensure an attachment is downloaded locally.

        For iCloud-stored attachments, triggers download and waits.

        Args:
            attachment: Attachment to download

        Returns:
            Path to local file

        Raises:
            FileNotFoundError: If attachment cannot be downloaded
        """
        # Expand ~ in path
        path = Path(attachment.path).expanduser()

        if path.exists():
            return path

        # TODO: Implement iCloud download trigger
        # For now, just raise if file doesn't exist
        raise FileNotFoundError(f"Attachment not found locally: {path}")
