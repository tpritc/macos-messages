# Test Plan

This document outlines the test coverage for macos-messages, ensuring we test everything promised in the documentation.

## Test Structure

```
tests/
├── conftest.py          # Shared fixtures, test database setup
├── test_db.py           # MessagesDB query tests
├── test_models.py       # Date conversion, model behavior
├── test_phone.py        # Phone normalization and matching
├── test_contacts.py     # Contact resolution (mocked)
├── test_cli.py          # CLI command tests
└── test_errors.py       # Error handling tests
```

## Test Database Fixture

The test database needs to include all the features we support. Here's what it should contain:

### Handles (contacts)
- US phone number: `+15551234567`
- UK phone number: `+447700900123`
- Email: `jane@example.com`

### Chats
- 1:1 chat with US number (iMessage)
- 1:1 chat with UK number (SMS)
- Group chat with display name (iMessage)

### Messages
- Regular incoming message
- Regular outgoing message (`is_from_me=1`)
- Message with reactions (love, like, laugh)
- Edited message (with edit history)
- Unsent message
- Message with effect (balloons)
- Message with attachment
- Audio message with transcription
- Threaded reply
- Messages spanning multiple dates (for date filtering tests)

### Attachments
- Image attachment (image/jpeg)
- PDF attachment (application/pdf)
- Sticker

---

## Test Coverage by Module

### test_db.py - Database Queries

#### chats()
```python
def test_chats_returns_all_chats(messages_db):
    """Should return all chats."""

def test_chats_ordered_by_recent_activity(messages_db):
    """Most recently active chat should be first."""

def test_chats_limit(messages_db):
    """--limit should restrict number of results."""

def test_chats_service_filter_imessage(messages_db):
    """--service imessage should only return iMessage chats."""

def test_chats_service_filter_sms(messages_db):
    """--service sms should only return SMS chats."""

def test_chats_includes_message_count(messages_db):
    """ChatSummary should include accurate message_count."""

def test_chats_includes_last_message_date(messages_db):
    """ChatSummary should include last_message_date."""
```

#### chat()
```python
def test_chat_by_id(messages_db):
    """Should return chat with matching ID."""

def test_chat_by_id_not_found(messages_db):
    """Should raise appropriate error for nonexistent chat."""

def test_chat_includes_participants(messages_db):
    """Chat should include list of participants."""
```

#### chat_by_identifier()
```python
def test_chat_by_phone_e164(messages_db):
    """Should find chat by E.164 phone number."""

def test_chat_by_phone_local_format(messages_db):
    """Should find chat by local phone format (555-123-4567)."""

def test_chat_by_phone_with_spaces(messages_db):
    """Should find chat by spaced format (+1 555 123 4567)."""

def test_chat_by_email(messages_db):
    """Should find chat by email address."""

def test_chat_by_identifier_not_found(messages_db):
    """Should raise appropriate error for unknown identifier."""
```

#### messages()
```python
def test_messages_chronological_order(messages_db):
    """Messages should be returned oldest first."""

def test_messages_by_chat_id(messages_db):
    """Should filter messages by chat_id."""

def test_messages_by_identifier(messages_db):
    """Should filter messages by phone/email identifier."""

def test_messages_limit(messages_db):
    """Should respect limit parameter."""

def test_messages_offset(messages_db):
    """Should skip first N messages with offset."""

def test_messages_after_date(messages_db):
    """Should only return messages after specified date."""

def test_messages_before_date(messages_db):
    """Should only return messages before specified date."""

def test_messages_date_range(messages_db):
    """Should filter by both after and before."""

def test_messages_include_unsent_true(messages_db):
    """Should include unsent messages by default."""

def test_messages_include_unsent_false(messages_db):
    """Should exclude unsent messages when include_unsent=False."""

def test_messages_sender_resolved(messages_db):
    """Incoming messages should have sender Handle populated."""

def test_messages_from_me_no_sender(messages_db):
    """Outgoing messages should have sender=None."""
```

#### message()
```python
def test_message_by_id(messages_db):
    """Should return single message with full details."""

def test_message_by_id_not_found(messages_db):
    """Should raise appropriate error for nonexistent message."""

def test_message_includes_reactions(messages_db):
    """Message should include list of reactions."""

def test_message_includes_effect(messages_db):
    """Message with effect should have effect field populated."""

def test_message_includes_edit_history(messages_db):
    """Edited message should have edit_history populated."""

def test_message_is_edited_flag(messages_db):
    """Edited message should have is_edited=True."""

def test_message_is_unsent_flag(messages_db):
    """Unsent message should have is_unsent=True."""

def test_message_transcription(messages_db):
    """Audio message should have transcription populated."""

def test_message_reply_to_id(messages_db):
    """Threaded reply should have reply_to_id set."""
```

#### search()
```python
def test_search_finds_matching_text(messages_db):
    """Should find messages containing search term."""

def test_search_case_insensitive(messages_db):
    """Search should be case-insensitive."""

def test_search_no_results(messages_db):
    """Should return empty iterator for no matches."""

def test_search_limit(messages_db):
    """Should respect limit parameter."""

def test_search_within_chat(messages_db):
    """Should filter search to specific chat_id."""

def test_search_with_date_filter(messages_db):
    """Should combine search with date filtering."""
```

#### attachments()
```python
def test_attachments_returns_all(messages_db):
    """Should return all attachments."""

def test_attachments_by_chat(messages_db):
    """Should filter by chat_id."""

def test_attachments_by_message(messages_db):
    """Should filter by message_id."""

def test_attachments_mime_type_exact(messages_db):
    """Should filter by exact MIME type."""

def test_attachments_mime_type_wildcard(messages_db):
    """Should filter by MIME type wildcard (image/*)."""

def test_attachments_limit(messages_db):
    """Should respect limit parameter."""

def test_attachments_includes_sticker_flag(messages_db):
    """Sticker attachment should have is_sticker=True."""
```

---

### test_models.py - Data Models

#### Date conversion
```python
def test_apple_date_to_datetime():
    """Should convert Apple nanoseconds to datetime."""

def test_apple_date_zero():
    """Zero should convert to 2001-01-01."""

def test_datetime_to_apple_date():
    """Should convert datetime to Apple nanoseconds."""
```

#### ReactionType
```python
def test_reaction_type_values():
    """All reaction types should have expected string values."""
```

#### MessageEffect
```python
def test_message_effect_bubble_effects():
    """Bubble effects should be defined."""

def test_message_effect_screen_effects():
    """Screen effects should be defined."""
```

---

### test_phone.py - Phone Normalization

```python
@pytest.mark.parametrize("input,region,expected", [
    # US formats
    ("+15551234567", "US", "+15551234567"),      # Already E.164
    ("5551234567", "US", "+15551234567"),        # 10-digit
    ("555-123-4567", "US", "+15551234567"),      # Dashes
    ("(555) 123-4567", "US", "+15551234567"),    # Parens
    ("555.123.4567", "US", "+15551234567"),      # Dots
    ("1-555-123-4567", "US", "+15551234567"),    # With country code
    # UK formats
    ("+447700900123", "GB", "+447700900123"),    # Already E.164
    ("07700 900123", "GB", "+447700900123"),     # Local mobile
    ("07700900123", "GB", "+447700900123"),      # No spaces
    ("+44 7700 900123", "GB", "+447700900123"),  # International with spaces
])
def test_normalize_phone(input, region, expected, monkeypatch):
    """Phone numbers in various formats should normalize to E.164."""

def test_normalize_phone_invalid():
    """Invalid phone number should raise ValueError."""

def test_normalize_phone_empty():
    """Empty string should raise ValueError."""

@pytest.mark.parametrize("query,stored,should_match", [
    ("555-123-4567", "+15551234567", True),      # Local matches E.164
    ("+15551234567", "+15551234567", True),      # Exact match
    ("07700 900123", "+447700900123", True),     # UK local matches E.164
    ("555-123-4567", "+15559999999", False),     # Different number
    ("jane@example.com", "jane@example.com", True),  # Email exact match
])
def test_phone_match(query, stored, should_match, monkeypatch):
    """Phone matching should handle various format combinations."""

def test_get_system_region():
    """Should return a valid region code from system settings."""
```

---

### test_contacts.py - Contact Resolution

```python
def test_get_contact_name_found(mock_contacts):
    """Should return display name for known contact."""

def test_get_contact_name_not_found(mock_contacts):
    """Should return None for unknown identifier."""

def test_get_contact_name_by_email(mock_contacts):
    """Should resolve email addresses to names."""

def test_resolve_contacts_disabled(messages_db):
    """With resolve_contacts=False, display_name should be None."""
```

---

### test_cli.py - CLI Commands

#### Global options
```python
def test_cli_version():
    """--version should show version number."""

def test_cli_help():
    """--help should show usage information."""

def test_cli_custom_db_path(test_db_path):
    """--db should use specified database path."""

def test_cli_no_contacts_flag(test_db_path):
    """--no-contacts should disable contact resolution."""
```

#### chats command
```python
def test_chats_default(test_db_path):
    """Should list chats with default options."""

def test_chats_limit(test_db_path):
    """--limit should restrict output."""

def test_chats_service_filter(test_db_path):
    """--service should filter by service type."""

def test_chats_json_output(test_db_path):
    """--json should output valid JSON array."""

def test_chats_output_format(test_db_path):
    """Output should show ID, name, service, message count."""
```

#### messages command
```python
def test_messages_requires_chat_or_with():
    """Should error if neither --chat nor --with provided."""

def test_messages_by_chat_id(test_db_path):
    """--chat should filter by chat ID."""

def test_messages_by_identifier(test_db_path):
    """--with should filter by phone/email."""

def test_messages_limit(test_db_path):
    """--limit should restrict output."""

def test_messages_after_date(test_db_path):
    """--after should filter by date."""

def test_messages_before_date(test_db_path):
    """--before should filter by date."""

def test_messages_verbose(test_db_path):
    """--verbose should show detailed reaction info."""

def test_messages_json_output(test_db_path):
    """--json should output valid JSON array."""

def test_messages_no_unsent(test_db_path):
    """--no-unsent should exclude unsent messages."""

def test_messages_output_format(test_db_path):
    """Output should show [date] [id:N] sender: text."""

def test_messages_shows_reactions_compact(test_db_path):
    """Default output should show reaction summary."""

def test_messages_shows_edited_flag(test_db_path):
    """Edited messages should show (edited) marker."""
```

#### read command
```python
def test_read_message(test_db_path):
    """Should display single message details."""

def test_read_message_not_found(test_db_path):
    """Should error for nonexistent message ID."""

def test_read_json_output(test_db_path):
    """--json should output valid JSON object."""

def test_read_shows_reactions(test_db_path):
    """Should list all reactions with who reacted."""

def test_read_shows_edit_history(test_db_path):
    """Should show edit history for edited messages."""

def test_read_shows_effect(test_db_path):
    """Should show effect for messages with effects."""
```

#### search command
```python
def test_search_finds_matches(test_db_path):
    """Should find messages containing query."""

def test_search_no_results(test_db_path):
    """Should return empty output for no matches."""

def test_search_within_chat(test_db_path):
    """--chat should limit search to specific chat."""

def test_search_with_date_range(test_db_path):
    """--after and --before should filter results."""

def test_search_json_output(test_db_path):
    """--json should output valid JSON array."""
```

#### attachments command
```python
def test_attachments_list(test_db_path):
    """Should list attachments."""

def test_attachments_by_chat(test_db_path):
    """--chat should filter by chat ID."""

def test_attachments_by_message(test_db_path):
    """--message should filter by message ID."""

def test_attachments_mime_type_filter(test_db_path):
    """--type should filter by MIME type."""

def test_attachments_json_output(test_db_path):
    """--json should output valid JSON array."""

def test_attachments_output_format(test_db_path):
    """Output should show ID, filename, size, MIME type, path."""
```

---

### test_errors.py - Error Handling

```python
def test_database_not_found():
    """Should raise FileNotFoundError with clear message."""

def test_permission_denied(monkeypatch):
    """Should raise PermissionError with Full Disk Access instructions."""

def test_chat_not_found(messages_db):
    """Should raise error for nonexistent chat ID."""

def test_message_not_found(messages_db):
    """Should raise error for nonexistent message ID."""

def test_invalid_phone_number(messages_db):
    """Should raise ValueError for unparseable phone number."""

def test_cli_database_not_found():
    """CLI should show error and exit 1 for missing database."""

def test_cli_permission_denied(monkeypatch):
    """CLI should show Full Disk Access message and exit 1."""

def test_cli_chat_not_found(test_db_path):
    """CLI should show error for nonexistent chat."""
```

---

## Test Database Schema

The fixture needs these tables with test data:

```sql
-- Handles
INSERT INTO handle (ROWID, id, service) VALUES
    (1, '+15551234567', 'iMessage'),
    (2, '+447700900123', 'SMS'),
    (3, 'jane@example.com', 'iMessage');

-- Chats
INSERT INTO chat (ROWID, guid, chat_identifier, display_name, service_name) VALUES
    (1, 'chat1', '+15551234567', NULL, 'iMessage'),
    (2, 'chat2', '+447700900123', NULL, 'SMS'),
    (3, 'chat3', 'chat;+15551234567;+447700900123', 'Family Group', 'iMessage');

-- Messages (variety of types)
-- Regular messages, reactions, edits, effects, unsent, threaded, with attachments

-- Attachments
INSERT INTO attachment (ROWID, guid, filename, mime_type, total_bytes, is_sticker) VALUES
    (1, 'att1', 'photo.jpg', 'image/jpeg', 102400, 0),
    (2, 'att2', 'document.pdf', 'application/pdf', 51200, 0),
    (3, 'att3', 'sticker.png', 'image/png', 2048, 1);
```

---

## Running Tests

```bash
# Run all tests
uv run pytest

# Run with verbose output
uv run pytest -v

# Run specific test file
uv run pytest tests/test_db.py

# Run tests matching a pattern
uv run pytest -k "test_messages"

# Run with coverage
uv run pytest --cov=messages --cov-report=term-missing
```

---

## Dependencies

```toml
[dependency-groups]
dev = [
    "pytest>=8.0",
    "pytest-cov>=4.0",
    "ruff>=0.4",
]
```

Note: Removed `pytest-asyncio` (nothing is async) and `sqlite-utils` (creating test DBs manually).
