"""Tests for data models and date conversion."""

from datetime import datetime


class TestDateConversion:
    """Tests for Apple date format conversion."""

    def test_apple_date_to_datetime(self):
        """Should convert Apple nanoseconds to datetime."""
        from messages.models import apple_time_to_datetime

        # 2024-01-15 09:30:00 in Apple time
        # (23 years + some days from 2001-01-01)
        apple_ns = 727_261_800_000_000_000  # Approximate
        result = apple_time_to_datetime(apple_ns)
        assert isinstance(result, datetime)
        assert result.year == 2024

    def test_apple_date_zero(self):
        """Zero should convert to 2001-01-01."""
        from messages.models import apple_time_to_datetime

        result = apple_time_to_datetime(0)
        assert result == datetime(2001, 1, 1)

    def test_apple_date_none(self):
        """None should return None."""
        from messages.models import apple_time_to_datetime

        result = apple_time_to_datetime(None)
        assert result is None

    def test_datetime_to_apple_date(self):
        """Should convert datetime to Apple nanoseconds."""
        from messages.models import datetime_to_apple_time

        dt = datetime(2024, 1, 15, 9, 30, 0)
        result = datetime_to_apple_time(dt)
        assert isinstance(result, int)
        assert result > 0


class TestReactionType:
    """Tests for ReactionType enum."""

    def test_reaction_type_love(self):
        """Love reaction should have correct value."""
        from messages.models import ReactionType

        assert ReactionType.LOVE.value == "love"

    def test_reaction_type_like(self):
        """Like reaction should have correct value."""
        from messages.models import ReactionType

        assert ReactionType.LIKE.value == "like"

    def test_reaction_type_dislike(self):
        """Dislike reaction should have correct value."""
        from messages.models import ReactionType

        assert ReactionType.DISLIKE.value == "dislike"

    def test_reaction_type_laugh(self):
        """Laugh reaction should have correct value."""
        from messages.models import ReactionType

        assert ReactionType.LAUGH.value == "ha-ha"

    def test_reaction_type_emphasis(self):
        """Emphasis reaction should have correct value."""
        from messages.models import ReactionType

        assert ReactionType.EMPHASIS.value == "emphasis"

    def test_reaction_type_question(self):
        """Question reaction should have correct value."""
        from messages.models import ReactionType

        assert ReactionType.QUESTION.value == "question"

    def test_all_reaction_types_defined(self):
        """All six reaction types should be defined."""
        from messages.models import ReactionType

        assert len(ReactionType) == 6


class TestMessageEffect:
    """Tests for MessageEffect enum."""

    def test_bubble_effects_defined(self):
        """Bubble effects should be defined."""
        from messages.models import MessageEffect

        bubble_effects = ["slam", "loud", "gentle", "invisible_ink"]
        for effect in bubble_effects:
            assert any(e.value == effect for e in MessageEffect)

    def test_screen_effects_defined(self):
        """Screen effects should be defined."""
        from messages.models import MessageEffect

        screen_effects = [
            "echo",
            "spotlight",
            "balloons",
            "confetti",
            "love_effect",
            "lasers",
            "fireworks",
            "celebration",
        ]
        for effect in screen_effects:
            assert any(e.value == effect for e in MessageEffect)


class TestHandle:
    """Tests for Handle dataclass."""

    def test_handle_creation(self):
        """Should create Handle with all fields."""
        from messages.models import Handle

        handle = Handle(
            id=1, identifier="+15551234567", service="iMessage", display_name="Jane Doe"
        )
        assert handle.id == 1
        assert handle.identifier == "+15551234567"
        assert handle.service == "iMessage"
        assert handle.display_name == "Jane Doe"

    def test_handle_display_name_optional(self):
        """display_name should be optional."""
        from messages.models import Handle

        handle = Handle(id=1, identifier="+15551234567", service="iMessage", display_name=None)
        assert handle.display_name is None


class TestMessage:
    """Tests for Message dataclass."""

    def test_message_creation(self):
        """Should create Message with required fields."""
        from messages.models import Message

        msg = Message(
            id=1,
            chat_id=1,
            text="Hello",
            date=datetime.now(),
            is_from_me=False,
            sender=None,
            has_attachments=False,
        )
        assert msg.id == 1
        assert msg.text == "Hello"

    def test_message_defaults(self):
        """Optional fields should have sensible defaults."""
        from messages.models import Message

        msg = Message(
            id=1,
            chat_id=1,
            text="Hello",
            date=datetime.now(),
            is_from_me=False,
            sender=None,
            has_attachments=False,
        )
        assert msg.reactions == []
        assert msg.effect is None
        assert msg.edit_history == []
        assert msg.is_edited is False
        assert msg.is_unsent is False
        assert msg.transcription is None
        assert msg.reply_to_id is None
        assert msg.thread_id is None


class TestChat:
    """Tests for Chat dataclass."""

    def test_chat_creation(self):
        """Should create Chat with all fields."""
        from messages.models import Chat

        chat = Chat(
            id=1, identifier="+15551234567", display_name=None, service="iMessage", participants=[]
        )
        assert chat.id == 1
        assert chat.service == "iMessage"


class TestChatSummary:
    """Tests for ChatSummary dataclass."""

    def test_chat_summary_creation(self):
        """Should create ChatSummary with message stats."""
        from messages.models import ChatSummary

        summary = ChatSummary(
            id=1,
            identifier="+15551234567",
            display_name="Jane",
            service="iMessage",
            message_count=42,
            last_message_date=datetime.now(),
        )
        assert summary.message_count == 42
        assert summary.last_message_date is not None


class TestAttachment:
    """Tests for Attachment dataclass."""

    def test_attachment_creation(self):
        """Should create Attachment with all fields."""
        from messages.models import Attachment

        att = Attachment(
            id=1,
            message_id=1,
            filename="photo.jpg",
            mime_type="image/jpeg",
            path="/path/to/photo.jpg",
            size=1024,
            is_sticker=False,
        )
        assert att.filename == "photo.jpg"
        assert att.size == 1024


class TestReaction:
    """Tests for Reaction dataclass."""

    def test_reaction_creation(self):
        """Should create Reaction with all fields."""
        from messages.models import Handle, Reaction, ReactionType

        handle = Handle(id=1, identifier="+15551234567", service="iMessage", display_name="Jane")
        reaction = Reaction(type=ReactionType.LOVE, sender=handle, date=datetime.now())
        assert reaction.type == ReactionType.LOVE
        assert reaction.sender.display_name == "Jane"


class TestEditRecord:
    """Tests for EditRecord dataclass."""

    def test_edit_record_creation(self):
        """Should create EditRecord with text and date."""
        from messages.models import EditRecord

        edit = EditRecord(text="Original text", date=datetime.now())
        assert edit.text == "Original text"
        assert edit.date is not None
