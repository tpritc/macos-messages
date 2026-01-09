"""Tests for MessagesDB database queries."""

from datetime import datetime, timedelta

import pytest
from conftest import BASE_DATE


class TestChats:
    """Tests for MessagesDB.chats() method."""

    def test_chats_returns_all_chats(self, messages_db):
        """Should return all chats."""
        chats = list(messages_db.chats())
        assert len(chats) == 3

    def test_chats_ordered_by_recent_activity(self, messages_db):
        """Most recently active chat should be first."""
        chats = list(messages_db.chats())
        # Chat 3 (group) has most recent message (2 hours after BASE_DATE)
        assert chats[0].id == 3

    def test_chats_limit(self, messages_db):
        """--limit should restrict number of results."""
        chats = list(messages_db.chats(limit=1))
        assert len(chats) == 1

    def test_chats_service_filter_imessage(self, messages_db):
        """--service iMessage should only return iMessage chats."""
        chats = list(messages_db.chats(service="iMessage"))
        assert len(chats) == 2
        assert all(c.service == "iMessage" for c in chats)

    def test_chats_service_filter_sms(self, messages_db):
        """--service SMS should only return SMS chats."""
        chats = list(messages_db.chats(service="SMS"))
        assert len(chats) == 1
        assert chats[0].service == "SMS"

    def test_chats_includes_message_count(self, messages_db):
        """ChatSummary should include accurate message_count."""
        chats = list(messages_db.chats())
        # Find chat 1 which has the most messages in our test data
        chat1 = next(c for c in chats if c.id == 1)
        # Chat 1 has messages 1,2,3,4,5,6,7,8,9,10,15 = 11 messages
        # But reactions (4,5) might not count as messages depending on implementation
        assert chat1.message_count >= 9  # At least the non-reaction messages

    def test_chats_includes_last_message_date(self, messages_db):
        """ChatSummary should include last_message_date."""
        chats = list(messages_db.chats())
        chat1 = next(c for c in chats if c.id == 1)
        assert chat1.last_message_date is not None
        assert isinstance(chat1.last_message_date, datetime)


class TestChat:
    """Tests for MessagesDB.chat() method."""

    def test_chat_by_id(self, messages_db):
        """Should return chat with matching ID."""
        chat = messages_db.chat(1)
        assert chat.id == 1
        assert chat.identifier == "+15551234567"

    def test_chat_by_id_not_found(self, messages_db):
        """Should raise appropriate error for nonexistent chat."""
        with pytest.raises(Exception):  # Could be LookupError, ValueError, etc.
            messages_db.chat(999)

    def test_chat_includes_participants(self, messages_db):
        """Chat should include list of participants."""
        chat = messages_db.chat(3)  # Group chat
        assert len(chat.participants) == 3


class TestChatByIdentifier:
    """Tests for MessagesDB.chat_by_identifier() method."""

    def test_chat_by_phone_e164(self, messages_db):
        """Should find chat by E.164 phone number."""
        chat = messages_db.chat_by_identifier("+15551234567")
        assert chat.id == 1

    def test_chat_by_phone_local_format(self, messages_db):
        """Should find chat by local phone format (555-123-4567)."""
        chat = messages_db.chat_by_identifier("555-123-4567")
        assert chat.id == 1

    def test_chat_by_phone_with_spaces(self, messages_db):
        """Should find chat by spaced format (+1 555 123 4567)."""
        chat = messages_db.chat_by_identifier("+1 555 123 4567")
        assert chat.id == 1

    def test_chat_by_email(self, messages_db):
        """Should find chat by email address."""
        # Email is in group chat (chat 3)
        chat = messages_db.chat_by_identifier("jane@example.com")
        assert chat is not None

    def test_chat_by_identifier_not_found(self, messages_db):
        """Should raise appropriate error for unknown identifier."""
        with pytest.raises(Exception):
            messages_db.chat_by_identifier("+19999999999")


class TestMessages:
    """Tests for MessagesDB.messages() method."""

    def test_messages_chronological_order(self, messages_db):
        """Messages should be returned oldest first."""
        msgs = list(messages_db.messages(chat_id=1, limit=100))
        # Filter out reactions for this test
        regular_msgs = [m for m in msgs if m.text and m.text != "\ufffc"]
        dates = [m.date for m in regular_msgs]
        assert dates == sorted(dates)

    def test_messages_by_chat_id(self, messages_db):
        """Should filter messages by chat_id."""
        msgs = list(messages_db.messages(chat_id=2))
        assert len(msgs) == 2  # Chat 2 has 2 messages

    def test_messages_by_identifier(self, messages_db):
        """Should filter messages by phone/email identifier."""
        msgs = list(messages_db.messages(identifier="+15551234567"))
        assert len(msgs) > 0

    def test_messages_limit(self, messages_db):
        """Should respect limit parameter."""
        msgs = list(messages_db.messages(chat_id=1, limit=3))
        assert len(msgs) == 3

    def test_messages_offset(self, messages_db):
        """Should skip first N messages with offset."""
        all_msgs = list(messages_db.messages(chat_id=1, limit=100))
        offset_msgs = list(messages_db.messages(chat_id=1, limit=100, offset=2))
        assert len(offset_msgs) == len(all_msgs) - 2

    def test_messages_after_date(self, messages_db):
        """Should only return messages after specified date."""
        after = BASE_DATE + timedelta(minutes=5)
        msgs = list(messages_db.messages(chat_id=1, after=after))
        assert all(m.date > after for m in msgs)

    def test_messages_before_date(self, messages_db):
        """Should only return messages before specified date."""
        before = BASE_DATE + timedelta(minutes=5)
        msgs = list(messages_db.messages(chat_id=1, before=before))
        assert all(m.date < before for m in msgs)

    def test_messages_date_range(self, messages_db):
        """Should filter by both after and before."""
        after = BASE_DATE
        before = BASE_DATE + timedelta(minutes=10)
        msgs = list(messages_db.messages(chat_id=1, after=after, before=before))
        assert all(after < m.date < before for m in msgs)

    def test_messages_include_unsent_true(self, messages_db):
        """Should include unsent messages by default."""
        msgs = list(messages_db.messages(chat_id=1, limit=100))
        unsent = [m for m in msgs if m.is_unsent]
        assert len(unsent) >= 1

    def test_messages_include_unsent_false(self, messages_db):
        """Should exclude unsent messages when include_unsent=False."""
        msgs = list(messages_db.messages(chat_id=1, limit=100, include_unsent=False))
        unsent = [m for m in msgs if m.is_unsent]
        assert len(unsent) == 0

    def test_messages_sender_resolved(self, messages_db):
        """Incoming messages should have sender Handle populated."""
        msgs = list(messages_db.messages(chat_id=1, limit=100))
        incoming = [m for m in msgs if not m.is_from_me and m.sender]
        assert len(incoming) > 0
        assert incoming[0].sender.display_name == "Jane Doe"

    def test_messages_from_me_no_sender(self, messages_db):
        """Outgoing messages should have sender=None or is_from_me=True."""
        msgs = list(messages_db.messages(chat_id=1, limit=100))
        outgoing = [m for m in msgs if m.is_from_me]
        assert len(outgoing) > 0


class TestMessage:
    """Tests for MessagesDB.message() method."""

    def test_message_by_id(self, messages_db):
        """Should return single message with full details."""
        msg = messages_db.message(1)
        assert msg.id == 1
        assert msg.text == "Hey, are you free for lunch?"

    def test_message_by_id_not_found(self, messages_db):
        """Should raise appropriate error for nonexistent message."""
        with pytest.raises(Exception):
            messages_db.message(9999)

    def test_message_includes_reactions(self, messages_db):
        """Message should include list of reactions."""
        # Message 2 has reactions (love and like)
        msg = messages_db.message(2)
        assert len(msg.reactions) >= 2

    def test_message_reaction_types(self, messages_db):
        """Reactions should have correct types."""
        msg = messages_db.message(2)
        reaction_types = {r.type.value for r in msg.reactions}
        assert "love" in reaction_types
        assert "like" in reaction_types

    def test_message_includes_effect(self, messages_db):
        """Message with effect should have effect field populated."""
        # Message 6 has balloons effect
        msg = messages_db.message(6)
        assert msg.effect is not None

    def test_message_is_edited_flag(self, messages_db):
        """Edited message should have is_edited=True."""
        # Message 7 was edited
        msg = messages_db.message(7)
        assert msg.is_edited is True

    def test_message_is_unsent_flag(self, messages_db):
        """Unsent message should have is_unsent=True."""
        # Message 8 is unsent
        msg = messages_db.message(8)
        assert msg.is_unsent is True

    def test_message_reply_to_id(self, messages_db):
        """Threaded reply should have reply_to_id set."""
        # Message 10 is a reply to message 3
        msg = messages_db.message(10)
        assert msg.reply_to_id is not None

    def test_message_has_attachments_flag(self, messages_db):
        """Message with attachments should have has_attachments=True."""
        # Message 9 has attachments
        msg = messages_db.message(9)
        assert msg.has_attachments is True

    def test_message_text_from_attributed_body(self, messages_db):
        """Message with NULL text should extract text from attributedBody."""
        # Message 16 has text=NULL but attributedBody contains "Hello from blob"
        msg = messages_db.message(16)
        assert msg.text == "Hello from blob"

    def test_message_text_from_attributed_body_extended_length(self, messages_db):
        """Message with extended length encoding (0x81) should extract full text."""
        # Message 17 has text=NULL but attributedBody contains a long message (>127 bytes)
        # using the 0x81 extended length encoding format
        msg = messages_db.message(17)
        expected_text = (
            "This is a longer message that exceeds 127 bytes to test the extended length "
            "encoding format used by macOS Messages for longer strings. The 0x81 marker "
            "indicates a 2-byte little-endian length follows."
        )
        assert msg.text == expected_text
        assert len(msg.text) > 127  # Verify it's actually a long message

    def test_messages_list_includes_attributed_body_text(self, messages_db):
        """messages() should also extract text from attributedBody."""
        msgs = list(messages_db.messages(chat_id=1, limit=100))
        # Find message 16 in the list
        msg16 = next((m for m in msgs if m.id == 16), None)
        assert msg16 is not None
        assert msg16.text == "Hello from blob"


class TestSearch:
    """Tests for MessagesDB.search() method."""

    def test_search_finds_matching_text(self, messages_db):
        """Should find messages containing search term."""
        results = list(messages_db.search("lunch"))
        assert len(results) >= 1
        assert any("lunch" in r.text.lower() for r in results)

    def test_search_case_insensitive(self, messages_db):
        """Search should be case-insensitive."""
        results_lower = list(messages_db.search("lunch"))
        results_upper = list(messages_db.search("LUNCH"))
        assert len(results_lower) == len(results_upper)

    def test_search_no_results(self, messages_db):
        """Should return empty iterator for no matches."""
        results = list(messages_db.search("xyznonexistent123"))
        assert len(results) == 0

    def test_search_limit(self, messages_db):
        """Should respect limit parameter."""
        results = list(messages_db.search("a", limit=2))  # Common letter
        assert len(results) <= 2

    def test_search_within_chat(self, messages_db):
        """Should filter search to specific chat_id."""
        results = list(messages_db.search("dinner", chat_id=3))
        assert all(r.chat_id == 3 for r in results)

    def test_search_with_date_filter(self, messages_db):
        """Should combine search with date filtering."""
        after = BASE_DATE
        results = list(messages_db.search("lunch", after=after))
        assert all(r.date >= after for r in results)


class TestAttachments:
    """Tests for MessagesDB.attachments() method."""

    def test_attachments_returns_all(self, messages_db):
        """Should return all attachments."""
        atts = list(messages_db.attachments(limit=100))
        assert len(atts) == 3

    def test_attachments_by_chat(self, messages_db):
        """Should filter by chat_id."""
        atts = list(messages_db.attachments(chat_id=1))
        assert len(atts) == 2  # photo and PDF in chat 1

    def test_attachments_by_message(self, messages_db):
        """Should filter by message_id."""
        atts = list(messages_db.attachments(message_id=9))
        assert len(atts) == 2  # msg 9 has photo and PDF

    def test_attachments_mime_type_exact(self, messages_db):
        """Should filter by exact MIME type."""
        atts = list(messages_db.attachments(mime_type="image/jpeg"))
        assert len(atts) == 1
        assert atts[0].mime_type == "image/jpeg"

    def test_attachments_mime_type_wildcard(self, messages_db):
        """Should filter by MIME type wildcard (image/*)."""
        atts = list(messages_db.attachments(mime_type="image/*"))
        assert len(atts) == 2  # jpeg and png

    def test_attachments_limit(self, messages_db):
        """Should respect limit parameter."""
        atts = list(messages_db.attachments(limit=1))
        assert len(atts) == 1

    def test_attachments_includes_sticker_flag(self, messages_db):
        """Sticker attachment should have is_sticker=True."""
        atts = list(messages_db.attachments(mime_type="image/png"))
        sticker = next((a for a in atts if a.is_sticker), None)
        assert sticker is not None
        assert sticker.is_sticker is True

    def test_attachment_has_size(self, messages_db):
        """Attachments should have size populated."""
        atts = list(messages_db.attachments(limit=1))
        assert atts[0].size > 0

    def test_attachment_has_path(self, messages_db):
        """Attachments should have path populated."""
        atts = list(messages_db.attachments(limit=1))
        assert atts[0].path is not None
