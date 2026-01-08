"""macos-messages: Python library and CLI for reading macOS Messages.app data."""

from .db import MessagesDB
from .models import (
    Attachment,
    Chat,
    ChatSummary,
    EditRecord,
    Handle,
    Message,
    MessageEffect,
    Reaction,
    ReactionType,
)

__version__ = "0.1.0"

__all__ = [
    "MessagesDB",
    "Message",
    "Chat",
    "ChatSummary",
    "Handle",
    "Attachment",
    "Reaction",
    "ReactionType",
    "MessageEffect",
    "EditRecord",
    "get_db",
]


def get_db(path: str | None = None) -> MessagesDB:
    """Get a MessagesDB instance.

    Args:
        path: Path to chat.db. Defaults to ~/Library/Messages/chat.db

    Returns:
        MessagesDB instance

    Raises:
        FileNotFoundError: If database doesn't exist
        PermissionError: If Full Disk Access not granted
    """
    db = MessagesDB(path=path)
    _ = db.conn
    return db
