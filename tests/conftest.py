"""Shared test fixtures for macos-messages tests."""

import sqlite3
from datetime import datetime, timedelta
from pathlib import Path

import pytest

# Apple epoch for date conversion (2001-01-01 00:00:00 UTC)
APPLE_EPOCH = datetime(2001, 1, 1)


def to_apple_time(dt: datetime) -> int:
    """Convert datetime to Apple nanoseconds since 2001-01-01."""
    return int((dt - APPLE_EPOCH).total_seconds() * 1_000_000_000)


# Base date for test messages
BASE_DATE = datetime(2024, 1, 15, 9, 30, 0)


@pytest.fixture
def test_db_path(tmp_path):
    """Create a test Messages database with comprehensive test data.

    Includes:
    - Multiple handles (US phone, UK phone, email)
    - Multiple chats (1:1 iMessage, 1:1 SMS, group chat)
    - Various message types (regular, reactions, edited, unsent, effects, threaded)
    - Attachments (image, PDF, sticker)
    """
    db_path = tmp_path / "chat.db"
    conn = sqlite3.connect(db_path)

    # Create schema matching real chat.db
    conn.executescript("""
        CREATE TABLE handle (
            ROWID INTEGER PRIMARY KEY,
            id TEXT NOT NULL,
            service TEXT NOT NULL
        );

        CREATE TABLE chat (
            ROWID INTEGER PRIMARY KEY,
            guid TEXT UNIQUE NOT NULL,
            chat_identifier TEXT,
            display_name TEXT,
            service_name TEXT
        );

        CREATE TABLE message (
            ROWID INTEGER PRIMARY KEY,
            guid TEXT UNIQUE NOT NULL,
            text TEXT,
            date INTEGER,
            date_read INTEGER,
            date_delivered INTEGER,
            is_from_me INTEGER DEFAULT 0,
            handle_id INTEGER,
            cache_has_attachments INTEGER DEFAULT 0,
            associated_message_guid TEXT,
            associated_message_type INTEGER DEFAULT 0,
            expressive_send_style_id TEXT,
            message_summary_info BLOB,
            was_edited INTEGER DEFAULT 0,
            date_edited INTEGER,
            is_unsent INTEGER DEFAULT 0,
            thread_originator_guid TEXT,
            thread_originator_part TEXT
        );

        CREATE TABLE chat_message_join (
            chat_id INTEGER,
            message_id INTEGER,
            PRIMARY KEY (chat_id, message_id)
        );

        CREATE TABLE chat_handle_join (
            chat_id INTEGER,
            handle_id INTEGER,
            PRIMARY KEY (chat_id, handle_id)
        );

        CREATE TABLE attachment (
            ROWID INTEGER PRIMARY KEY,
            guid TEXT UNIQUE NOT NULL,
            filename TEXT,
            mime_type TEXT,
            total_bytes INTEGER,
            is_sticker INTEGER DEFAULT 0,
            transfer_name TEXT
        );

        CREATE TABLE message_attachment_join (
            message_id INTEGER,
            attachment_id INTEGER,
            PRIMARY KEY (message_id, attachment_id)
        );
    """)

    # Insert handles
    conn.executemany(
        "INSERT INTO handle (ROWID, id, service) VALUES (?, ?, ?)",
        [
            (1, "+15551234567", "iMessage"),
            (2, "+447700900123", "SMS"),
            (3, "jane@example.com", "iMessage"),
        ]
    )

    # Insert chats
    conn.executemany(
        "INSERT INTO chat (ROWID, guid, chat_identifier, display_name, service_name) VALUES (?, ?, ?, ?, ?)",
        [
            (1, "iMessage;-;+15551234567", "+15551234567", None, "iMessage"),
            (2, "SMS;-;+447700900123", "+447700900123", None, "SMS"),
            (3, "iMessage;-;chat123456", "chat123456", "Family Group", "iMessage"),
        ]
    )

    # Link handles to chats
    conn.executemany(
        "INSERT INTO chat_handle_join (chat_id, handle_id) VALUES (?, ?)",
        [
            (1, 1),  # Chat 1 has handle 1
            (2, 2),  # Chat 2 has handle 2
            (3, 1),  # Group chat has handles 1, 2, 3
            (3, 2),
            (3, 3),
        ]
    )

    # Insert messages
    messages = [
        # Chat 1: Regular conversation
        (1, "msg001", "Hey, are you free for lunch?", to_apple_time(BASE_DATE), 0, 1, 0, None, 0, None, 0, None, 0, None),
        (2, "msg002", "Sure! Where were you thinking?", to_apple_time(BASE_DATE + timedelta(minutes=1)), 1, None, 0, None, 0, None, 0, None, 0, None),
        (3, "msg003", "How about that new place on Main St?", to_apple_time(BASE_DATE + timedelta(minutes=2)), 0, 1, 0, None, 0, None, 0, None, 0, None),

        # Chat 1: Message with reaction (love reaction on msg002)
        # associated_message_type: 2000 = love, 2001 = like, 2002 = dislike, 2003 = laugh, 2004 = emphasis, 2005 = question
        (4, "msg004", "\ufffc", to_apple_time(BASE_DATE + timedelta(minutes=3)), 0, 1, 0, "msg002", 2000, None, 0, None, 0, None),

        # Chat 1: Another reaction (like on msg002)
        (5, "msg005", "\ufffc", to_apple_time(BASE_DATE + timedelta(minutes=3, seconds=30)), 0, 1, 0, "msg002", 2001, None, 0, None, 0, None),

        # Chat 1: Message with effect (balloons)
        (6, "msg006", "Happy birthday!", to_apple_time(BASE_DATE + timedelta(minutes=5)), 1, None, 0, None, 0, "com.apple.messages.effect.CKHappyBirthdayEffect", 0, None, 0, None),

        # Chat 1: Edited message
        (7, "msg007", "Let's meet at 12:30", to_apple_time(BASE_DATE + timedelta(minutes=10)), 1, None, 0, None, 0, None, 1, to_apple_time(BASE_DATE + timedelta(minutes=11)), 0, None),

        # Chat 1: Unsent message
        (8, "msg008", None, to_apple_time(BASE_DATE + timedelta(minutes=15)), 1, None, 0, None, 0, None, 0, None, 1, None),

        # Chat 1: Message with attachment
        (9, "msg009", "Check out this photo!", to_apple_time(BASE_DATE + timedelta(minutes=20)), 0, 1, 1, None, 0, None, 0, None, 0, None),

        # Chat 1: Threaded reply (reply to msg003)
        (10, "msg010", "Yes! I've heard great things about it", to_apple_time(BASE_DATE + timedelta(minutes=25)), 1, None, 0, None, 0, None, 0, None, 0, "msg003"),

        # Chat 2: SMS conversation (for service filtering tests)
        (11, "msg011", "Got your text!", to_apple_time(BASE_DATE + timedelta(hours=1)), 0, 2, 0, None, 0, None, 0, None, 0, None),
        (12, "msg012", "Great, talk soon", to_apple_time(BASE_DATE + timedelta(hours=1, minutes=5)), 1, None, 0, None, 0, None, 0, None, 0, None),

        # Chat 3: Group chat messages
        (13, "msg013", "Family dinner this Sunday?", to_apple_time(BASE_DATE + timedelta(hours=2)), 0, 1, 0, None, 0, None, 0, None, 0, None),
        (14, "msg014", "I'm in!", to_apple_time(BASE_DATE + timedelta(hours=2, minutes=10)), 0, 3, 0, None, 0, None, 0, None, 0, None),

        # Chat 1: Message from a week ago (for date filtering)
        (15, "msg015", "Old message from last week", to_apple_time(BASE_DATE - timedelta(days=7)), 0, 1, 0, None, 0, None, 0, None, 0, None),
    ]

    conn.executemany(
        """INSERT INTO message (
            ROWID, guid, text, date, is_from_me, handle_id, cache_has_attachments,
            associated_message_guid, associated_message_type, expressive_send_style_id,
            was_edited, date_edited, is_unsent, thread_originator_guid
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        messages
    )

    # Link messages to chats
    chat_message_joins = [
        (1, 1), (1, 2), (1, 3), (1, 4), (1, 5), (1, 6), (1, 7), (1, 8), (1, 9), (1, 10), (1, 15),
        (2, 11), (2, 12),
        (3, 13), (3, 14),
    ]
    conn.executemany(
        "INSERT INTO chat_message_join (chat_id, message_id) VALUES (?, ?)",
        chat_message_joins
    )

    # Insert attachments
    conn.executemany(
        "INSERT INTO attachment (ROWID, guid, filename, mime_type, total_bytes, is_sticker, transfer_name) VALUES (?, ?, ?, ?, ?, ?, ?)",
        [
            (1, "att001", "~/Library/Messages/Attachments/ab/cd/photo.jpg", "image/jpeg", 102400, 0, "photo.jpg"),
            (2, "att002", "~/Library/Messages/Attachments/ef/gh/document.pdf", "application/pdf", 51200, 0, "document.pdf"),
            (3, "att003", "~/Library/Messages/Attachments/ij/kl/sticker.png", "image/png", 2048, 1, "sticker.png"),
        ]
    )

    # Link attachments to messages
    conn.executemany(
        "INSERT INTO message_attachment_join (message_id, attachment_id) VALUES (?, ?)",
        [
            (9, 1),   # photo attached to msg009
            (9, 2),   # PDF also attached to msg009
            (13, 3),  # sticker in group chat
        ]
    )

    conn.commit()
    conn.close()
    return db_path


@pytest.fixture
def messages_db(test_db_path, monkeypatch):
    """Get a MessagesDB instance with mocked contact resolution."""
    import messages

    # Mock contact resolution to return predictable names
    contact_map = {
        "+15551234567": "Jane Doe",
        "+447700900123": "John Smith",
        "jane@example.com": "Jane Email",
    }
    monkeypatch.setattr(
        "messages.contacts.get_contact_name",
        lambda x: contact_map.get(x)
    )

    # Mock system region
    monkeypatch.setattr(
        "messages.phone.get_system_region",
        lambda: "US"
    )

    return messages.get_db(path=test_db_path)


@pytest.fixture
def mock_region(monkeypatch):
    """Mock system region detection to return US."""
    monkeypatch.setattr("messages.phone.get_system_region", lambda: "US")


@pytest.fixture
def mock_region_gb(monkeypatch):
    """Mock system region detection to return GB."""
    monkeypatch.setattr("messages.phone.get_system_region", lambda: "GB")


@pytest.fixture
def mock_contacts(monkeypatch):
    """Mock contact resolution."""
    contact_map = {
        "+15551234567": "Jane Doe",
        "+447700900123": "John Smith",
        "jane@example.com": "Jane Email",
    }
    monkeypatch.setattr(
        "messages.contacts.get_contact_name",
        lambda x: contact_map.get(x)
    )
