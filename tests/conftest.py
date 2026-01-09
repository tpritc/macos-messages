"""Shared test fixtures for macos-messages tests."""

import sqlite3
from datetime import datetime, timedelta

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
            attributedBody BLOB,
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
            date_edited INTEGER,
            date_retracted INTEGER,
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
        ],
    )

    # Insert chats
    conn.executemany(
        """INSERT INTO chat (ROWID, guid, chat_identifier, display_name, service_name)
        VALUES (?, ?, ?, ?, ?)""",
        [
            (1, "iMessage;-;+15551234567", "+15551234567", None, "iMessage"),
            (2, "SMS;-;+447700900123", "+447700900123", None, "SMS"),
            (3, "iMessage;-;chat123456", "chat123456", "Family Group", "iMessage"),
        ],
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
        ],
    )

    # Insert messages
    # Format: (ROWID, guid, text, attributedBody, date, is_from_me, handle_id,
    #          cache_has_attachments, associated_message_guid, associated_message_type,
    #          expressive_send_style_id, date_edited, date_retracted, thread_originator_guid)

    # Mock attributedBody blob containing "Hello from blob"
    # This mimics the NSKeyedArchiver format used by macOS Messages:
    # - Header with "streamtyped" and "NSAttributedString" markers
    # - NSString section with + marker (0x2B), length byte, then UTF-8 text
    # - Terminator (0x86) and trailing metadata
    attributed_body_blob = (
        # Header: streamtyped + class info
        b"\x04\x0bstreamtyped\x81\xe8\x03\x84\x01\x40\x84\x84\x84\x12NSAttributedString"
        b"\x00\x84\x84\x08NSObject\x00\x85\x92\x84\x84\x84\x08NSString\x01\x94\x84\x01"
        # + marker (0x2B) + length (0x0F = 15) + "Hello from blob"
        b"\x2b\x0fHello from blob"
        # Terminator and trailing structure
        b"\x86\x84\x02iI\x01\x10\x92\x84\x84\x84\x0cNSDictionary\x00\x94\x84\x01i\x01"
        b"\x92\x84\x96\x96\x1d__kIMMes sagePartAttributeName\x86\x92\x84\x84\x84\x08"
        b"NSNumber\x00\x84\x84\x07NSValue\x00\x94\x84\x01*\x84\x99\x99\x00\x86\x86\x86"
    )

    # Mock attributedBody blob with extended length encoding (0x81 marker)
    # This tests the case where text is longer than 127 bytes
    # Format: + marker (0x2B) + 0x81 (extended) + 2-byte little-endian length + text
    long_text = (
        "This is a longer message that exceeds 127 bytes to test the extended length "
        "encoding format used by macOS Messages for longer strings. The 0x81 marker "
        "indicates a 2-byte little-endian length follows."
    )
    long_text_bytes = long_text.encode("utf-8")
    long_text_length = len(long_text_bytes)  # Should be > 127
    attributed_body_blob_extended = (
        # Header: streamtyped + class info
        b"\x04\x0bstreamtyped\x81\xe8\x03\x84\x01\x40\x84\x84\x84\x12NSAttributedString"
        b"\x00\x84\x84\x08NSObject\x00\x85\x92\x84\x84\x84\x08NSString\x01\x94\x84\x01"
        # + marker (0x2B) + 0x81 (extended length) + 2-byte little-endian length
        + b"\x2b\x81"
        + long_text_length.to_bytes(2, "little")
        # The actual text
        + long_text_bytes
        # Terminator and trailing structure
        + b"\x86\x84\x02iI\x01\x10\x92\x84\x84\x84\x0cNSDictionary\x00\x94\x84\x01i\x01"
        b"\x92\x84\x96\x96\x1d__kIMMes sagePartAttributeName\x86\x92\x84\x84\x84\x08"
        b"NSNumber\x00\x84\x84\x07NSValue\x00\x94\x84\x01*\x84\x99\x99\x00\x86\x86\x86"
    )

    birthday_effect = "com.apple.messages.effect.CKHappyBirthdayEffect"
    messages = [
        # Chat 1: Regular conversation
        (
            1,
            "msg001",
            "Hey, are you free for lunch?",
            None,
            to_apple_time(BASE_DATE),
            0,
            1,
            0,
            None,
            0,
            None,
            None,
            None,
            None,
        ),
        (
            2,
            "msg002",
            "Sure! Where were you thinking?",
            None,
            to_apple_time(BASE_DATE + timedelta(minutes=1)),
            1,
            None,
            0,
            None,
            0,
            None,
            None,
            None,
            None,
        ),
        (
            3,
            "msg003",
            "How about that new place on Main St?",
            None,
            to_apple_time(BASE_DATE + timedelta(minutes=2)),
            0,
            1,
            0,
            None,
            0,
            None,
            None,
            None,
            None,
        ),
        # Chat 1: Message with reaction (love reaction on msg002)
        # associated_message_type: 2000=love, 2001=like, 2002=dislike,
        # 2003=laugh, 2004=emphasis, 2005=question
        (
            4,
            "msg004",
            "\ufffc",
            None,
            to_apple_time(BASE_DATE + timedelta(minutes=3)),
            0,
            1,
            0,
            "msg002",
            2000,
            None,
            None,
            None,
            None,
        ),
        # Chat 1: Another reaction (like on msg002)
        (
            5,
            "msg005",
            "\ufffc",
            None,
            to_apple_time(BASE_DATE + timedelta(minutes=3, seconds=30)),
            0,
            1,
            0,
            "msg002",
            2001,
            None,
            None,
            None,
            None,
        ),
        # Chat 1: Message with effect (balloons)
        (
            6,
            "msg006",
            "Happy birthday!",
            None,
            to_apple_time(BASE_DATE + timedelta(minutes=5)),
            1,
            None,
            0,
            None,
            0,
            birthday_effect,
            None,
            None,
            None,
        ),
        # Chat 1: Edited message (date_edited is set to indicate it was edited)
        (
            7,
            "msg007",
            "Let's meet at 12:30",
            None,
            to_apple_time(BASE_DATE + timedelta(minutes=10)),
            1,
            None,
            0,
            None,
            0,
            None,
            to_apple_time(BASE_DATE + timedelta(minutes=11)),
            None,
            None,
        ),
        # Chat 1: Retracted/unsent message (date_retracted is set)
        (
            8,
            "msg008",
            None,
            None,
            to_apple_time(BASE_DATE + timedelta(minutes=15)),
            1,
            None,
            0,
            None,
            0,
            None,
            None,
            to_apple_time(BASE_DATE + timedelta(minutes=16)),
            None,
        ),
        # Chat 1: Message with attachment
        (
            9,
            "msg009",
            "Check out this photo!",
            None,
            to_apple_time(BASE_DATE + timedelta(minutes=20)),
            0,
            1,
            1,
            None,
            0,
            None,
            None,
            None,
            None,
        ),
        # Chat 1: Threaded reply (reply to msg003)
        (
            10,
            "msg010",
            "Yes! I've heard great things about it",
            None,
            to_apple_time(BASE_DATE + timedelta(minutes=25)),
            1,
            None,
            0,
            None,
            0,
            None,
            None,
            None,
            "msg003",
        ),
        # Chat 2: SMS conversation (for service filtering tests)
        (
            11,
            "msg011",
            "Got your text!",
            None,
            to_apple_time(BASE_DATE + timedelta(hours=1)),
            0,
            2,
            0,
            None,
            0,
            None,
            None,
            None,
            None,
        ),
        (
            12,
            "msg012",
            "Great, talk soon",
            None,
            to_apple_time(BASE_DATE + timedelta(hours=1, minutes=5)),
            1,
            None,
            0,
            None,
            0,
            None,
            None,
            None,
            None,
        ),
        # Chat 3: Group chat messages
        (
            13,
            "msg013",
            "Family dinner this Sunday?",
            None,
            to_apple_time(BASE_DATE + timedelta(hours=2)),
            0,
            1,
            0,
            None,
            0,
            None,
            None,
            None,
            None,
        ),
        (
            14,
            "msg014",
            "I'm in!",
            None,
            to_apple_time(BASE_DATE + timedelta(hours=2, minutes=10)),
            0,
            3,
            0,
            None,
            0,
            None,
            None,
            None,
            None,
        ),
        # Chat 1: Message from a week ago (for date filtering)
        (
            15,
            "msg015",
            "Old message from last week",
            None,
            to_apple_time(BASE_DATE - timedelta(days=7)),
            0,
            1,
            0,
            None,
            0,
            None,
            None,
            None,
            None,
        ),
        # Chat 1: Message with text ONLY in attributedBody (text column is NULL)
        # This tests the attributedBody extraction fallback
        (
            16,
            "msg016",
            None,
            attributed_body_blob,
            to_apple_time(BASE_DATE + timedelta(minutes=30)),
            1,
            None,
            0,
            None,
            0,
            None,
            None,
            None,
            None,
        ),
        # Chat 1: Message with extended length encoding in attributedBody
        # This tests the 0x81 extended length marker
        (
            17,
            "msg017",
            None,
            attributed_body_blob_extended,
            to_apple_time(BASE_DATE + timedelta(minutes=31)),
            1,
            None,
            0,
            None,
            0,
            None,
            None,
            None,
            None,
        ),
    ]

    conn.executemany(
        """INSERT INTO message (
            ROWID, guid, text, attributedBody, date, is_from_me, handle_id, cache_has_attachments,
            associated_message_guid, associated_message_type, expressive_send_style_id,
            date_edited, date_retracted, thread_originator_guid
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        messages,
    )

    # Link messages to chats
    chat_message_joins = [
        (1, 1),
        (1, 2),
        (1, 3),
        (1, 4),
        (1, 5),
        (1, 6),
        (1, 7),
        (1, 8),
        (1, 9),
        (1, 10),
        (1, 15),
        (1, 16),
        (1, 17),
        (2, 11),
        (2, 12),
        (3, 13),
        (3, 14),
    ]
    conn.executemany(
        "INSERT INTO chat_message_join (chat_id, message_id) VALUES (?, ?)", chat_message_joins
    )

    # Insert attachments
    att_base = "~/Library/Messages/Attachments"
    conn.executemany(
        """INSERT INTO attachment
        (ROWID, guid, filename, mime_type, total_bytes, is_sticker, transfer_name)
        VALUES (?, ?, ?, ?, ?, ?, ?)""",
        [
            (1, "att001", f"{att_base}/ab/cd/photo.jpg", "image/jpeg", 102400, 0, "photo.jpg"),
            (
                2,
                "att002",
                f"{att_base}/ef/gh/document.pdf",
                "application/pdf",
                51200,
                0,
                "document.pdf",
            ),
            (3, "att003", f"{att_base}/ij/kl/sticker.png", "image/png", 2048, 1, "sticker.png"),
        ],
    )

    # Link attachments to messages
    conn.executemany(
        "INSERT INTO message_attachment_join (message_id, attachment_id) VALUES (?, ?)",
        [
            (9, 1),  # photo attached to msg009
            (9, 2),  # PDF also attached to msg009
            (13, 3),  # sticker in group chat
        ],
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
    # Patch where it's used (in db.py), not where it's defined
    monkeypatch.setattr("messages.db.get_contact_name", lambda x: contact_map.get(x))

    # Mock system region
    monkeypatch.setattr("messages.phone.get_system_region", lambda: "US")

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
def mock_contacts(tmp_path, monkeypatch):
    """Mock contact resolution with a temporary contacts database."""
    import sqlite3

    from messages.contacts import clear_contact_cache

    # Create a temporary contacts database
    db_path = tmp_path / "AddressBook-v22.abcddb"
    conn = sqlite3.connect(db_path)

    # Create the required tables (minimal schema)
    conn.executescript("""
        CREATE TABLE ZABCDRECORD (
            Z_PK INTEGER PRIMARY KEY,
            ZFIRSTNAME VARCHAR,
            ZLASTNAME VARCHAR,
            ZNICKNAME VARCHAR,
            ZORGANIZATION VARCHAR
        );

        CREATE TABLE ZABCDPHONENUMBER (
            Z_PK INTEGER PRIMARY KEY,
            ZOWNER INTEGER,
            ZFULLNUMBER VARCHAR
        );

        CREATE TABLE ZABCDEMAILADDRESS (
            Z_PK INTEGER PRIMARY KEY,
            ZOWNER INTEGER,
            ZADDRESS VARCHAR
        );
    """)

    # Insert test contacts
    conn.execute("INSERT INTO ZABCDRECORD (Z_PK, ZFIRSTNAME, ZLASTNAME) VALUES (1, 'Jane', 'Doe')")
    conn.execute(
        "INSERT INTO ZABCDPHONENUMBER (ZOWNER, ZFULLNUMBER) VALUES (1, '+1 (555) 123-4567')"
    )

    conn.execute(
        "INSERT INTO ZABCDRECORD (Z_PK, ZFIRSTNAME, ZLASTNAME) VALUES (2, 'John', 'Smith')"
    )
    conn.execute("INSERT INTO ZABCDPHONENUMBER (ZOWNER, ZFULLNUMBER) VALUES (2, '+44 7700 900123')")

    conn.execute(
        "INSERT INTO ZABCDRECORD (Z_PK, ZFIRSTNAME, ZLASTNAME) VALUES (3, 'Jane', 'Email')"
    )
    conn.execute("INSERT INTO ZABCDEMAILADDRESS (ZOWNER, ZADDRESS) VALUES (3, 'jane@example.com')")

    conn.commit()
    conn.close()

    # Patch the database finder to return our test database
    monkeypatch.setattr("messages.contacts._find_contacts_databases", lambda: [db_path])

    # Clear the cache so it rebuilds from our test database
    clear_contact_cache()

    yield

    # Clear cache after test
    clear_contact_cache()
