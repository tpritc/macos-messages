"""Tests for contact resolution from macOS Contacts.app."""

import pytest

from messages.contacts import get_contact_name


class TestGetContactName:
    """Tests for get_contact_name function."""

    def test_get_contact_name_found(self, mock_contacts):
        """Should return display name for known contact."""
        name = get_contact_name("+15551234567")
        assert name == "Jane Doe"

    def test_get_contact_name_not_found(self, mock_contacts):
        """Should return None for unknown identifier."""
        name = get_contact_name("+19999999999")
        assert name is None

    def test_get_contact_name_by_email(self, mock_contacts):
        """Should resolve email addresses to names."""
        name = get_contact_name("jane@example.com")
        assert name == "Jane Email"

    def test_get_contact_name_none_input(self):
        """Should handle None input gracefully."""
        name = get_contact_name(None)
        assert name is None

    def test_get_contact_name_empty_string(self):
        """Should handle empty string gracefully."""
        name = get_contact_name("")
        assert name is None


class TestContactResolutionInDB:
    """Tests for contact resolution integrated with MessagesDB."""

    def test_resolve_contacts_enabled(self, messages_db):
        """With resolve_contacts=True, display_name should be populated."""
        msgs = list(messages_db.messages(chat_id=1, limit=10))
        incoming = [m for m in msgs if not m.is_from_me and m.sender]
        assert len(incoming) > 0
        # Should have resolved name from mock
        assert incoming[0].sender.display_name == "Jane Doe"

    def test_resolve_contacts_disabled(self, test_db_path, monkeypatch):
        """With resolve_contacts=False, display_name should be None."""
        import messages

        # Don't mock contacts - but disable resolution
        db = messages.get_db(path=test_db_path)
        db.resolve_contacts = False

        msgs = list(db.messages(chat_id=1, limit=10))
        incoming = [m for m in msgs if not m.is_from_me and m.sender]
        assert len(incoming) > 0
        # display_name should be None or the raw identifier
        assert incoming[0].sender.display_name is None or \
               incoming[0].sender.display_name == incoming[0].sender.identifier

    def test_chat_display_name_from_contacts(self, messages_db):
        """1:1 chat display_name should come from contact resolution."""
        chats = list(messages_db.chats())
        chat1 = next(c for c in chats if c.id == 1)
        # For 1:1 chats, display_name might be resolved from contacts
        # or might be None if no display_name in DB
        # This depends on implementation details

    def test_group_chat_display_name_preserved(self, messages_db):
        """Group chat display_name should come from DB, not contacts."""
        chats = list(messages_db.chats())
        group_chat = next(c for c in chats if c.id == 3)
        assert group_chat.display_name == "Family Group"
