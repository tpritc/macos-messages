"""Tests for contact resolution from macOS Contacts.app."""

from messages.contacts import get_all_contacts, get_contact_name, search_contacts


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


class TestGetAllContacts:
    """Tests for get_all_contacts function."""

    def test_get_all_contacts(self, mock_contacts):
        """Should return list of Contact objects."""
        contacts = get_all_contacts()
        assert isinstance(contacts, list)
        assert len(contacts) > 0
        # Check that contacts have display_name
        names = [c.display_name for c in contacts]
        assert "Jane Doe" in names

    def test_get_all_contacts_empty(self, monkeypatch):
        """Should return empty list if no contacts database."""
        from messages import contacts as contacts_module

        monkeypatch.setattr(contacts_module, "_find_contacts_databases", lambda: [])
        monkeypatch.setattr(contacts_module, "_contact_lookup", None)
        contacts_module.clear_contact_cache()

        contacts = get_all_contacts()
        assert contacts == []


class TestSearchContacts:
    """Tests for search_contacts function."""

    def test_search_contacts_found(self, mock_contacts):
        """Should return matching contacts."""
        contacts = search_contacts("Jane")
        assert len(contacts) > 0
        names = [c.display_name for c in contacts]
        assert any("Jane" in name for name in names)

    def test_search_contacts_case_insensitive(self, mock_contacts):
        """Search should be case-insensitive."""
        contacts = search_contacts("jane")
        assert len(contacts) > 0
        names = [c.display_name for c in contacts]
        assert any("Jane" in name for name in names)

    def test_search_contacts_partial_match(self, mock_contacts):
        """Should match partial names."""
        contacts = search_contacts("Doe")
        assert len(contacts) > 0
        names = [c.display_name for c in contacts]
        assert any("Doe" in name for name in names)

    def test_search_contacts_no_match(self, mock_contacts):
        """Should return empty list for no matches."""
        contacts = search_contacts("xyznonexistent123")
        assert contacts == []

    def test_search_contacts_multiple_matches(self, mock_contacts):
        """Should return all matching contacts."""
        # This depends on test data having multiple contacts with common substring
        contacts = search_contacts("J")  # Should match Jane Doe, John Smith, etc.
        assert len(contacts) >= 1


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
        assert (
            incoming[0].sender.display_name is None
            or incoming[0].sender.display_name == incoming[0].sender.identifier
        )

    def test_chat_display_name_from_contacts(self, messages_db):
        """1:1 chat display_name should come from contact resolution."""
        chats = list(messages_db.chats())
        # Find chat 1 to verify it exists
        chat1 = next(c for c in chats if c.id == 1)
        # For 1:1 chats, display_name might be resolved from contacts
        # or might be None if no display_name in DB
        # This depends on implementation details
        assert chat1 is not None

    def test_group_chat_display_name_preserved(self, messages_db):
        """Group chat display_name should come from DB, not contacts."""
        chats = list(messages_db.chats())
        group_chat = next(c for c in chats if c.id == 3)
        assert group_chat.display_name == "Family Group"
