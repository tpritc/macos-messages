"""Data models for macos-messages."""

from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum

# Apple epoch: 2001-01-01 00:00:00 UTC
APPLE_EPOCH = datetime(2001, 1, 1)


def apple_time_to_datetime(ns: int | None) -> datetime | None:
    """Convert Apple nanoseconds since 2001-01-01 to datetime.

    Args:
        ns: Nanoseconds since Apple epoch, or None

    Returns:
        datetime object, or None if input is None
    """
    if ns is None:
        return None
    return APPLE_EPOCH + timedelta(seconds=ns / 1_000_000_000)


def datetime_to_apple_time(dt: datetime) -> int:
    """Convert datetime to Apple nanoseconds since 2001-01-01.

    Args:
        dt: datetime object

    Returns:
        Nanoseconds since Apple epoch
    """
    return int((dt - APPLE_EPOCH).total_seconds() * 1_000_000_000)


class ReactionType(Enum):
    """Tapback reaction types."""

    LOVE = "love"  # ❤️
    LIKE = "like"  # 👍
    DISLIKE = "dislike"  # 👎
    LAUGH = "ha-ha"  # 😂
    EMPHASIS = "emphasis"  # ‼️
    QUESTION = "question"  # ❓


# Maps associated_message_type values to ReactionType
# 2000-2005 are "add" reactions, 3000-3005 are "remove" reactions
REACTION_TYPE_MAP = {
    2000: ReactionType.LOVE,
    2001: ReactionType.LIKE,
    2002: ReactionType.DISLIKE,
    2003: ReactionType.LAUGH,
    2004: ReactionType.EMPHASIS,
    2005: ReactionType.QUESTION,
    3000: ReactionType.LOVE,  # Remove love
    3001: ReactionType.LIKE,  # Remove like
    3002: ReactionType.DISLIKE,  # Remove dislike
    3003: ReactionType.LAUGH,  # Remove laugh
    3004: ReactionType.EMPHASIS,  # Remove emphasis
    3005: ReactionType.QUESTION,  # Remove question
}


class MessageEffect(Enum):
    """iMessage bubble and screen effects."""

    # Bubble effects
    SLAM = "slam"
    LOUD = "loud"
    GENTLE = "gentle"
    INVISIBLE_INK = "invisible_ink"

    # Screen effects
    ECHO = "echo"
    SPOTLIGHT = "spotlight"
    BALLOONS = "balloons"
    CONFETTI = "confetti"
    LOVE_EFFECT = "love_effect"
    LASERS = "lasers"
    FIREWORKS = "fireworks"
    CELEBRATION = "celebration"


# Maps expressive_send_style_id values to MessageEffect
EFFECT_MAP = {
    "com.apple.MobileSMS.expressivesend.slam": MessageEffect.SLAM,
    "com.apple.MobileSMS.expressivesend.loud": MessageEffect.LOUD,
    "com.apple.MobileSMS.expressivesend.gentle": MessageEffect.GENTLE,
    "com.apple.MobileSMS.expressivesend.invisibleink": MessageEffect.INVISIBLE_INK,
    "com.apple.messages.effect.CKEchoEffect": MessageEffect.ECHO,
    "com.apple.messages.effect.CKSpotlightEffect": MessageEffect.SPOTLIGHT,
    "com.apple.messages.effect.CKHappyBirthdayEffect": MessageEffect.BALLOONS,
    "com.apple.messages.effect.CKConfettiEffect": MessageEffect.CONFETTI,
    "com.apple.messages.effect.CKHeartEffect": MessageEffect.LOVE_EFFECT,
    "com.apple.messages.effect.CKLasersEffect": MessageEffect.LASERS,
    "com.apple.messages.effect.CKFireworksEffect": MessageEffect.FIREWORKS,
    "com.apple.messages.effect.CKSparklesEffect": MessageEffect.CELEBRATION,
}


@dataclass
class Handle:
    """A contact identifier (phone number or email)."""

    id: int
    identifier: str  # Phone number or email
    service: str  # "iMessage", "SMS", "RCS"
    display_name: str | None = None  # Resolved from Contacts.app


@dataclass
class Chat:
    """A conversation with full details."""

    id: int
    identifier: str
    display_name: str | None
    service: str
    participants: list[Handle] = field(default_factory=list)


@dataclass
class ChatSummary:
    """Lightweight chat info for listing."""

    id: int
    identifier: str
    display_name: str | None
    service: str
    message_count: int
    last_message_date: datetime | None


@dataclass
class Reaction:
    """A reaction/tapback on a message."""

    type: ReactionType
    sender: Handle
    date: datetime


@dataclass
class EditRecord:
    """A single edit in a message's history."""

    text: str
    date: datetime


@dataclass
class Message:
    """A single message."""

    id: int
    chat_id: int
    text: str | None
    date: datetime
    is_from_me: bool
    sender: Handle | None
    has_attachments: bool
    reactions: list[Reaction] = field(default_factory=list)
    effect: MessageEffect | None = None
    edit_history: list[EditRecord] = field(default_factory=list)
    is_edited: bool = False
    is_unsent: bool = False
    transcription: str | None = None
    reply_to_id: int | None = None
    thread_id: int | None = None


@dataclass
class Attachment:
    """A file attachment."""

    id: int
    message_id: int
    filename: str
    mime_type: str | None
    path: str  # Local path (may not exist if in iCloud)
    size: int
    is_sticker: bool = False
