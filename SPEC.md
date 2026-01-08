# macos-messages

A Python library and CLI for reading macOS Messages.app data.

## Overview

Following the pattern of [simonw/llm](https://github.com/simonw/llm):
- **Library first**: Clean Python API for programmatic access
- **CLI on top**: Click-based CLI that consumes the library
- **uv-native**: Uses uv for project management, dependencies, and installation
- **Installable**: `uv tool install` puts `messages` command in PATH

## Data Source

Messages are stored in SQLite at `~/Library/Messages/chat.db`.

### Key Tables

| Table | Purpose |
|-------|---------|
| `message` | All messages with text, timestamps, metadata |
| `chat` | Conversations (1:1 and group chats) |
| `handle` | Contact identifiers (phone numbers, emails) |
| `chat_message_join` | Links messages to chats |
| `chat_handle_join` | Links handles to chats |
| `attachment` | File attachments metadata |
| `message_attachment_join` | Links attachments to messages |

### Date Format

Dates are nanoseconds since 2001-01-01. Conversion:
```python
from datetime import datetime, timedelta
APPLE_EPOCH = datetime(2001, 1, 1)
def convert_date(ns: int) -> datetime:
    return APPLE_EPOCH + timedelta(seconds=ns / 1_000_000_000)
```

---

## Project Structure

```
macos-messages/
├── pyproject.toml
├── uv.lock
├── README.md
├── src/
│   └── messages/
│       ├── __init__.py      # Public API exports
│       ├── __main__.py      # python -m messages
│       ├── cli.py           # Click CLI commands
│       ├── db.py            # Database connection & queries
│       ├── models.py        # Dataclasses for Message, Chat, Handle, etc.
│       ├── contacts.py      # macOS Contacts.app integration
│       └── phone.py         # Phone number normalization
└── tests/
    ├── test_db.py
    └── test_cli.py
```

### Project Setup

```bash
# Create project
mkdir macos-messages && cd macos-messages
uv init --lib --name macos-messages

# Add dependencies
uv add click phonenumbers

# Add dev dependencies
uv add --group dev pytest ruff
```

---

## Python Library API

### `messages/__init__.py`

```python
from .models import (
    Message, Chat, Handle, Attachment, ChatSummary,
    Reaction, ReactionType, MessageEffect, EditRecord
)
from .db import MessagesDB

__all__ = [
    "MessagesDB",
    "Message",
    "Chat",
    "Handle",
    "Attachment",
    "ChatSummary",
    "Reaction",
    "ReactionType",
    "MessageEffect",
    "EditRecord",
    "get_db",
]

def get_db(path: str | None = None) -> MessagesDB:
    """
    Get a MessagesDB instance.

    Args:
        path: Path to chat.db. Defaults to ~/Library/Messages/chat.db

    Returns:
        MessagesDB instance

    Raises:
        FileNotFoundError: If database doesn't exist
        PermissionError: If Full Disk Access not granted
    """
    ...
```

### `messages/models.py`

```python
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Optional

@dataclass
class Handle:
    id: int
    identifier: str      # phone number or email
    service: str         # "iMessage", "SMS", "RCS"
    display_name: Optional[str] = None  # resolved from Contacts.app

@dataclass
class Chat:
    id: int
    identifier: str
    display_name: Optional[str]
    service: str
    participants: list[Handle]  # populated on demand

@dataclass
class ChatSummary:
    """Lightweight chat info for listing."""
    id: int
    identifier: str
    display_name: Optional[str]
    service: str
    message_count: int
    last_message_date: Optional[datetime]


class ReactionType(Enum):
    """Tapback reaction types."""
    LOVE = "love"           # ❤️
    LIKE = "like"           # 👍
    DISLIKE = "dislike"     # 👎
    LAUGH = "ha-ha"         # 😂
    EMPHASIS = "emphasis"   # ‼️
    QUESTION = "question"   # ❓

@dataclass
class Reaction:
    """A reaction/tapback on a message."""
    type: ReactionType
    sender: Handle
    date: datetime


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

@dataclass
class EditRecord:
    """A single edit in a message's history."""
    text: str
    date: datetime

@dataclass
class Message:
    id: int
    chat_id: int
    text: Optional[str]
    date: datetime
    is_from_me: bool
    sender: Optional[Handle]
    has_attachments: bool
    # Reactions (aggregated from associated messages)
    reactions: list[Reaction] = field(default_factory=list)
    # Message effect
    effect: Optional[MessageEffect] = None
    # Edit history (newest to oldest, current text is self.text)
    edit_history: list[EditRecord] = field(default_factory=list)
    is_edited: bool = False
    # Unsent/deleted via "Undo Send"
    is_unsent: bool = False
    # Audio message transcription (when available)
    transcription: Optional[str] = None
    # Threaded replies
    reply_to_id: Optional[int] = None
    thread_id: Optional[int] = None

@dataclass
class Attachment:
    id: int
    message_id: int
    filename: str
    mime_type: Optional[str]
    path: str               # local path (may not exist if in iCloud)
    size: int
    is_sticker: bool = False
```

### `messages/phone.py`

```python
import phonenumbers
import subprocess

def get_system_region() -> str:
    """
    Get the user's region code from macOS system settings.

    Returns:
        Two-letter region code (e.g., "US", "GB")
    """
    # Read from: defaults read NSGlobalDomain AppleLocale
    # or AppleGeo, depending on what's available
    ...

def normalize_phone(number: str, default_region: str | None = None) -> str:
    """
    Normalize a phone number to E.164 format for matching.

    Args:
        number: Phone number in any format
        default_region: Region code for numbers without country code.
                       Auto-detected from system if not provided.

    Returns:
        E.164 formatted number (e.g., "+15551234567")

    Raises:
        ValueError: If number cannot be parsed
    """
    ...

def phone_match(query: str, stored: str, default_region: str | None = None) -> bool:
    """
    Check if a phone number query matches a stored number.

    Handles cases like:
    - "07XXX XXXXXX" matching "+44 7XXX XXXXXX"
    - "555-1234" matching "+1 555 555 1234" (with area code inference)
    - Full E.164 exact matches

    Args:
        query: User's search query (any format)
        stored: Number stored in database
        default_region: Region for parsing numbers without country code

    Returns:
        True if numbers match
    """
    ...
```

### `messages/contacts.py`

```python
from typing import Optional

def get_contact_name(identifier: str) -> Optional[str]:
    """
    Look up a display name from macOS Contacts.app.

    Uses the identifier (phone number or email) to find the contact
    and returns the display name matching Messages.app behavior:
    - Nickname if set
    - Otherwise first name (or full name depending on system settings)

    Args:
        identifier: Phone number or email address

    Returns:
        Display name if found, None otherwise

    Note:
        May require Contacts permission on first use.
        Returns None silently if permission denied.
    """
    ...
```

### `messages/db.py`

```python
import sqlite3
from pathlib import Path
from typing import Iterator, Optional
from datetime import datetime

from .models import Message, Chat, ChatSummary, Handle, Attachment
from .phone import phone_match, get_system_region
from .contacts import get_contact_name

DEFAULT_DB_PATH = Path.home() / "Library" / "Messages" / "chat.db"

class MessagesDB:
    """Read-only interface to the Messages database."""

    def __init__(self, path: Path | str | None = None, resolve_contacts: bool = True):
        """
        Initialize database connection.

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
        if self._conn is None:
            if not self.path.exists():
                raise FileNotFoundError(f"Database not found: {self.path}")
            try:
                self._conn = sqlite3.connect(
                    f"file:{self.path}?mode=ro",
                    uri=True,
                    check_same_thread=False
                )
                self._conn.row_factory = sqlite3.Row
            except sqlite3.OperationalError as e:
                if "unable to open" in str(e):
                    raise PermissionError(
                        "Cannot read Messages database. "
                        "Grant Full Disk Access to Terminal in "
                        "System Settings > Privacy & Security > Full Disk Access"
                    )
                raise
        return self._conn

    @property
    def region(self) -> str:
        """User's region code for phone number parsing."""
        if self._region is None:
            self._region = get_system_region()
        return self._region

    def chats(
        self,
        *,
        service: Optional[str] = None,
        limit: Optional[int] = None,
    ) -> Iterator[ChatSummary]:
        """
        List all chats, ordered by most recent activity.

        Args:
            service: Filter by service ("iMessage", "SMS", "RCS")
            limit: Maximum number of results

        Yields:
            ChatSummary objects
        """
        ...

    def chat(self, chat_id: int) -> Chat:
        """Get a single chat by ID with full details."""
        ...

    def chat_by_identifier(self, identifier: str) -> Chat:
        """
        Get a chat by phone number or email.

        Uses smart phone number matching for international format support.

        Args:
            identifier: Phone number (any format) or email
        """
        ...

    def messages(
        self,
        *,
        chat_id: Optional[int] = None,
        identifier: Optional[str] = None,
        after: Optional[datetime] = None,
        before: Optional[datetime] = None,
        limit: int = 100,
        offset: int = 0,
        include_unsent: bool = True,
    ) -> Iterator[Message]:
        """
        List messages in chronological order (oldest first).

        Args:
            chat_id: Filter by chat ID
            identifier: Filter by phone/email (alternative to chat_id)
            after: Only messages after this date
            before: Only messages before this date
            limit: Maximum results (default 100)
            offset: Skip first N results
            include_unsent: Include messages that were unsent (default True)

        Yields:
            Message objects with reactions aggregated
        """
        ...

    def message(self, message_id: int) -> Message:
        """Get a single message by ID with full details."""
        ...

    def search(
        self,
        query: str,
        *,
        chat_id: Optional[int] = None,
        after: Optional[datetime] = None,
        before: Optional[datetime] = None,
        limit: int = 50,
    ) -> Iterator[Message]:
        """
        Search messages by text content.

        Args:
            query: Search string (case-insensitive substring match)
            chat_id: Limit search to specific chat
            after: Only messages after this date
            before: Only messages before this date
            limit: Maximum results (default 50)

        Yields:
            Message objects with matching text
        """
        ...

    def attachments(
        self,
        *,
        chat_id: Optional[int] = None,
        message_id: Optional[int] = None,
        mime_type: Optional[str] = None,
        limit: int = 100,
        auto_download: bool = True,
    ) -> Iterator[Attachment]:
        """
        List attachments.

        Args:
            chat_id: Filter by chat
            message_id: Filter by specific message
            mime_type: Filter by type (e.g., "image/png", "image/*")
            limit: Maximum results
            auto_download: If True, download iCloud attachments automatically

        Yields:
            Attachment objects (includes records where file may not exist locally)
        """
        ...

    def download_attachment(self, attachment: Attachment) -> Path:
        """
        Ensure an attachment is downloaded locally.

        For iCloud-stored attachments, triggers download and waits.

        Args:
            attachment: Attachment to download

        Returns:
            Path to local file

        Raises:
            FileNotFoundError: If attachment cannot be downloaded
        """
        ...
```

### Usage Examples

```python
import messages

# Get the default database
db = messages.get_db()

# List recent conversations
for chat in db.chats(limit=10):
    print(f"{chat.display_name or chat.identifier}: {chat.message_count} messages")

# Get messages from a specific conversation (oldest first)
for msg in db.messages(chat_id=45, limit=20):
    sender = "me" if msg.is_from_me else msg.sender.display_name or msg.sender.identifier
    print(f"[{msg.date}] {sender}: {msg.text}")

    # Show reactions
    if msg.reactions:
        reaction_summary = ", ".join(f"{r.type.value}" for r in msg.reactions)
        print(f"  Reactions: {reaction_summary}")

    # Show if edited
    if msg.is_edited:
        print(f"  (edited {len(msg.edit_history)} times)")

# Search by phone number (any format)
for msg in db.messages(identifier="07700 900123", limit=20):
    print(f"{msg.date}: {msg.text}")

# Search across all messages
for msg in db.search("dinner tomorrow"):
    print(f"[Chat {msg.chat_id}] {msg.text}")

# Find all images in a chat
for att in db.attachments(chat_id=45, mime_type="image/*"):
    print(f"{att.filename} ({att.size} bytes) - {att.path}")
```

---

## CLI Design

### Entry Point

`pyproject.toml`:
```toml
[project.scripts]
messages = "messages.cli:cli"
```

### Output Format

The CLI outputs plain text optimized for AI agent consumption and minimal token usage.

**Default format:**
```
[2024-01-15 09:30] [id:12345] Jane Doe: Hey, are you free for lunch?
[2024-01-15 09:31] [id:12346] me: Sure! Where were you thinking? [2 reactions: 1 love, 1 like]
[2024-01-15 09:32] [id:12347] Jane Doe: How about that new place on Main St?
```

**With `--verbose`:**
```
[2024-01-15 09:30] [id:12345] Jane Doe: Hey, are you free for lunch?
[2024-01-15 09:31] [id:12346] me: Sure! Where were you thinking?
  reactions: Jane Doe love, +15551234567 like
[2024-01-15 09:32] [id:12347] Jane Doe: How about that new place on Main St?
```

### `messages/cli.py`

```python
import click
from datetime import datetime
import json
import sys

import messages
from messages.models import Message

def format_reactions_compact(msg: Message) -> str:
    """Format reactions as '[N reactions: X type, Y type]'"""
    if not msg.reactions:
        return ""
    counts: dict[str, int] = {}
    for r in msg.reactions:
        counts[r.type.value] = counts.get(r.type.value, 0) + 1
    parts = [f"{count} {rtype}" for rtype, count in counts.items()]
    return f" [{len(msg.reactions)} reactions: {', '.join(parts)}]"

def format_reactions_verbose(msg: Message) -> str:
    """Format reactions with who reacted."""
    if not msg.reactions:
        return ""
    parts = []
    for r in msg.reactions:
        name = r.sender.display_name or r.sender.identifier
        parts.append(f"{name} {r.type.value}")
    return f"\n  reactions: {', '.join(parts)}"

def format_message(msg: Message, verbose: bool = False) -> str:
    """Format a message for plain text output."""
    sender = "me" if msg.is_from_me else (
        msg.sender.display_name or msg.sender.identifier if msg.sender else "?"
    )
    text = msg.text or "(no text)"
    if msg.transcription:
        text = f"[audio] {msg.transcription}"

    reactions = format_reactions_verbose(msg) if verbose else format_reactions_compact(msg)

    line = f"[{msg.date:%Y-%m-%d %H:%M}] [id:{msg.id}] {sender}: {text}{reactions if not verbose else ''}"
    if verbose and reactions:
        line += reactions

    if msg.is_edited:
        line += " (edited)"
    if msg.is_unsent:
        line += " (unsent)"
    if msg.effect:
        line += f" [effect:{msg.effect.value}]"

    return line


@click.group()
@click.version_option()
@click.option(
    "--db",
    type=click.Path(exists=True),
    help="Path to chat.db (default: ~/Library/Messages/chat.db)"
)
@click.option(
    "--no-contacts",
    is_flag=True,
    help="Don't resolve phone numbers to contact names"
)
@click.pass_context
def cli(ctx, db, no_contacts):
    """
    Read messages from macOS Messages.app

    Requires Full Disk Access permission for Terminal.
    """
    ctx.ensure_object(dict)
    try:
        ctx.obj["db"] = messages.get_db(db)
        ctx.obj["db"].resolve_contacts = not no_contacts
    except PermissionError as e:
        click.echo(str(e), err=True)
        sys.exit(1)
    except FileNotFoundError as e:
        click.echo(str(e), err=True)
        sys.exit(1)


@cli.command()
@click.option("--service", type=click.Choice(["imessage", "sms", "rcs"]))
@click.option("--limit", "-n", type=int, default=20)
@click.option("--json", "as_json", is_flag=True, help="Output as JSON")
@click.pass_context
def chats(ctx, service, limit, as_json):
    """List conversations."""
    db = ctx.obj["db"]
    results = list(db.chats(service=service, limit=limit))

    if as_json:
        click.echo(json.dumps([asdict(c) for c in results], default=str, indent=2))
    else:
        for chat in results:
            name = chat.display_name or chat.identifier
            click.echo(f"{chat.id} {name} ({chat.service}) - {chat.message_count} messages")


@cli.command("messages")
@click.option("--chat", "-c", "chat_id", type=int, help="Chat ID")
@click.option("--with", "-w", "identifier", help="Phone number or email")
@click.option("--after", type=click.DateTime(), help="After date (YYYY-MM-DD)")
@click.option("--before", type=click.DateTime(), help="Before date (YYYY-MM-DD)")
@click.option("--limit", "-n", type=int, default=50)
@click.option("--offset", type=int, default=0)
@click.option("--no-unsent", is_flag=True, help="Exclude unsent messages")
@click.option("--verbose", "-v", is_flag=True, help="Show detailed reaction info")
@click.option("--json", "as_json", is_flag=True, help="Output as JSON")
@click.option("--no-download", is_flag=True, help="Don't auto-download iCloud attachments")
@click.pass_context
def list_messages(ctx, chat_id, identifier, after, before, limit, offset, no_unsent, verbose, as_json, no_download):
    """List messages from a conversation."""
    db = ctx.obj["db"]

    if not chat_id and not identifier:
        raise click.UsageError("Specify --chat or --with")

    results = list(db.messages(
        chat_id=chat_id,
        identifier=identifier,
        after=after,
        before=before,
        limit=limit,
        offset=offset,
        include_unsent=not no_unsent,
    ))

    if as_json:
        click.echo(json.dumps([asdict(m) for m in results], default=str, indent=2))
    else:
        for msg in results:
            click.echo(format_message(msg, verbose=verbose))


@cli.command()
@click.argument("message_id", type=int)
@click.option("--json", "as_json", is_flag=True, help="Output as JSON")
@click.pass_context
def read(ctx, message_id, as_json):
    """Read a single message with full details."""
    db = ctx.obj["db"]
    msg = db.message(message_id)

    if as_json:
        click.echo(json.dumps(asdict(msg), default=str, indent=2))
    else:
        sender = "me" if msg.is_from_me else (
            msg.sender.display_name or msg.sender.identifier if msg.sender else "?"
        )
        click.echo(f"ID: {msg.id}")
        click.echo(f"Date: {msg.date}")
        click.echo(f"From: {sender}")
        click.echo(f"Chat: {msg.chat_id}")
        if msg.effect:
            click.echo(f"Effect: {msg.effect.value}")
        if msg.is_edited:
            click.echo(f"Edited: {len(msg.edit_history)} times")
            for edit in msg.edit_history:
                click.echo(f"  [{edit.date}] {edit.text}")
        if msg.is_unsent:
            click.echo("Status: unsent")
        click.echo()
        click.echo(msg.text or "(no text)")
        if msg.transcription:
            click.echo(f"\nTranscription: {msg.transcription}")
        if msg.reactions:
            click.echo(f"\nReactions ({len(msg.reactions)}):")
            for r in msg.reactions:
                name = r.sender.display_name or r.sender.identifier
                click.echo(f"  {r.type.value} from {name}")


@cli.command()
@click.argument("query")
@click.option("--chat", "-c", "chat_id", type=int, help="Limit to chat ID")
@click.option("--after", type=click.DateTime(), help="After date")
@click.option("--before", type=click.DateTime(), help="Before date")
@click.option("--limit", "-n", type=int, default=20)
@click.option("--verbose", "-v", is_flag=True, help="Show detailed reaction info")
@click.option("--json", "as_json", is_flag=True, help="Output as JSON")
@click.pass_context
def search(ctx, query, chat_id, after, before, limit, verbose, as_json):
    """Search messages by text content."""
    db = ctx.obj["db"]

    results = list(db.search(
        query,
        chat_id=chat_id,
        after=after,
        before=before,
        limit=limit,
    ))

    if as_json:
        click.echo(json.dumps([asdict(m) for m in results], default=str, indent=2))
    else:
        for msg in results:
            click.echo(format_message(msg, verbose=verbose))


@cli.command()
@click.option("--chat", "-c", "chat_id", type=int, help="Filter by chat")
@click.option("--message", "-m", "message_id", type=int, help="Filter by message")
@click.option("--type", "mime_type", help="Filter by MIME type (e.g., image/*)")
@click.option("--limit", "-n", type=int, default=20)
@click.option("--no-download", is_flag=True, help="Don't auto-download iCloud attachments")
@click.option("--json", "as_json", is_flag=True, help="Output as JSON")
@click.pass_context
def attachments(ctx, chat_id, message_id, mime_type, limit, no_download, as_json):
    """List attachments."""
    db = ctx.obj["db"]

    results = list(db.attachments(
        chat_id=chat_id,
        message_id=message_id,
        mime_type=mime_type,
        limit=limit,
        auto_download=not no_download,
    ))

    if as_json:
        click.echo(json.dumps([asdict(a) for a in results], default=str, indent=2))
    else:
        for att in results:
            size_kb = att.size // 1024 if att.size else 0
            click.echo(f"{att.id} {att.filename} ({size_kb}KB) {att.mime_type or ''}")
            click.echo(f"  {att.path}")
```

### `messages/__main__.py`

```python
from .cli import cli

if __name__ == "__main__":
    cli()
```

---

## CLI Usage Examples

```bash
# List recent conversations
messages chats
messages chats --limit 5
messages chats --service imessage --json

# List messages from a chat (oldest first by default)
messages messages --chat 45
messages messages --with "+15551234567" --limit 100
messages messages --with "07700 900123"  # UK format works too
messages messages --chat 45 --after 2024-01-01 --json
messages messages --chat 45 --verbose  # show who reacted

# Read a specific message with full details
messages read 12345
messages read 12345 --json

# Search messages
messages search "dinner"
messages search "meeting" --chat 45
messages search "project" --after 2024-06-01 --limit 50

# List attachments
messages attachments --chat 45
messages attachments --type "image/*"
messages attachments --message 12345 --json
messages attachments --chat 45 --no-download  # don't fetch iCloud files

# Export a conversation (use shell redirection)
messages messages --chat 45 --limit 10000 > conversation.txt
```

---

## pyproject.toml

```toml
[project]
name = "macos-messages"
version = "0.1.0"
description = "Python library and CLI for reading macOS Messages.app data"
readme = "README.md"
requires-python = ">=3.12"
license = "MIT"
authors = [
    { name = "Your Name" }
]
classifiers = [
    "Development Status :: 3 - Alpha",
    "Environment :: Console",
    "Environment :: MacOS X",
    "Intended Audience :: Developers",
    "License :: OSI Approved :: MIT License",
    "Operating System :: MacOS",
    "Programming Language :: Python :: 3",
    "Programming Language :: Python :: 3.12",
    "Programming Language :: Python :: 3.13",
    "Topic :: Communications :: Chat",
]

dependencies = [
    "click>=8.0",
    "phonenumbers>=8.13",
]

[project.scripts]
messages = "messages.cli:cli"

[project.urls]
Homepage = "https://github.com/tpritc/macos-messages"
Issues = "https://github.com/tpritc/macos-messages/issues"

[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[tool.hatch.build.targets.wheel]
packages = ["src/messages"]

[dependency-groups]
dev = [
    "pytest>=8.0",
    "ruff>=0.4",
]
```

---

## Installation

```bash
# Development (from project directory)
cd macos-messages
uv sync
uv run messages --help

# Install globally as a tool (available in PATH)
uv tool install .

# Or install from git
uv tool install git+https://github.com/tpritc/macos-messages

# Verify
messages --help
messages chats
```

---

## Permissions Required

This tool requires the following macOS permissions:

### Full Disk Access (Required)
To read the Messages database at `~/Library/Messages/chat.db`:
1. Open System Settings > Privacy & Security > Full Disk Access
2. Enable your terminal app (Terminal.app, iTerm2, etc.)
3. Restart the terminal

### Contacts Access (Optional)
To resolve phone numbers to contact names:
- The app will request permission on first use
- If denied, phone numbers/emails are shown instead of names
- Use `--no-contacts` flag to skip contact resolution entirely

---

## Error Handling

| Error | CLI Message |
|-------|-------------|
| DB not found | `Error: Messages database not found at ~/Library/Messages/chat.db` |
| Permission denied | `Error: Cannot read Messages database. Grant Full Disk Access to Terminal in System Settings > Privacy & Security > Full Disk Access` |
| Chat not found | `Error: Chat 999 not found` |
| Phone parse error | `Error: Could not parse phone number "xyz"` |
| No results | (empty output, exit 0) |

---

## Testing

Following patterns from [simonw/llm](https://github.com/simonw/llm), tests use pytest with fixtures that isolate all external dependencies.

### Test Dependencies

```toml
[dependency-groups]
dev = [
    "pytest>=8.0",
    "pytest-asyncio>=0.23",
    "sqlite-utils>=3.37",
    "ruff>=0.4",
]
```

### Test Structure

```
tests/
├── conftest.py              # Shared fixtures
├── test_db.py               # Database query tests
├── test_phone.py            # Phone normalization tests
├── test_contacts.py         # Contact resolution tests
├── test_cli.py              # CLI command tests
└── test_models.py           # Date conversion, dataclass tests
```

### Core Fixtures (`tests/conftest.py`)

```python
import pytest
import sqlite3
from pathlib import Path
from datetime import datetime

# Apple epoch for date conversion
APPLE_EPOCH = datetime(2001, 1, 1)

def to_apple_time(dt: datetime) -> int:
    """Convert datetime to Apple nanoseconds since 2001."""
    return int((dt - APPLE_EPOCH).total_seconds() * 1_000_000_000)


@pytest.fixture
def test_db_path(tmp_path):
    """Create a test Messages database with known schema and data."""
    db_path = tmp_path / "chat.db"
    conn = sqlite3.connect(db_path)
    
    # Create schema matching real chat.db
    conn.executescript("""
        CREATE TABLE handle (
            ROWID INTEGER PRIMARY KEY,
            id TEXT,
            service TEXT
        );
        
        CREATE TABLE chat (
            ROWID INTEGER PRIMARY KEY,
            guid TEXT,
            chat_identifier TEXT,
            display_name TEXT,
            service_name TEXT
        );
        
        CREATE TABLE message (
            ROWID INTEGER PRIMARY KEY,
            guid TEXT,
            text TEXT,
            date INTEGER,
            is_from_me INTEGER,
            handle_id INTEGER,
            cache_has_attachments INTEGER DEFAULT 0,
            associated_message_type INTEGER DEFAULT 0,
            expressive_send_style_id TEXT,
            was_edited INTEGER DEFAULT 0,
            date_edited INTEGER,
            was_delivered_quietly INTEGER DEFAULT 0
        );
        
        CREATE TABLE chat_message_join (
            chat_id INTEGER,
            message_id INTEGER
        );
        
        CREATE TABLE chat_handle_join (
            chat_id INTEGER,
            handle_id INTEGER
        );
        
        CREATE TABLE attachment (
            ROWID INTEGER PRIMARY KEY,
            guid TEXT,
            filename TEXT,
            mime_type TEXT,
            total_bytes INTEGER,
            is_sticker INTEGER DEFAULT 0
        );
        
        CREATE TABLE message_attachment_join (
            message_id INTEGER,
            attachment_id INTEGER
        );
    """)
    
    # Insert test data
    conn.executemany(
        "INSERT INTO handle (ROWID, id, service) VALUES (?, ?, ?)",
        [
            (1, "+15551234567", "iMessage"),
            (2, "+447700900123", "iMessage"),
            (3, "jane@example.com", "iMessage"),
        ]
    )
    
    conn.executemany(
        "INSERT INTO chat (ROWID, guid, chat_identifier, display_name, service_name) VALUES (?, ?, ?, ?, ?)",
        [
            (1, "chat1", "+15551234567", None, "iMessage"),
            (2, "chat2", "chat12345", "Family Group", "iMessage"),
        ]
    )
    
    # Messages with known dates
    base_date = datetime(2024, 1, 15, 9, 30)
    conn.executemany(
        "INSERT INTO message (ROWID, guid, text, date, is_from_me, handle_id) VALUES (?, ?, ?, ?, ?, ?)",
        [
            (1, "msg1", "Hey, are you free for lunch?", to_apple_time(base_date), 0, 1),
            (2, "msg2", "Sure! Where were you thinking?", to_apple_time(base_date.replace(minute=31)), 1, None),
            (3, "msg3", "How about that new place on Main St?", to_apple_time(base_date.replace(minute=32)), 0, 1),
        ]
    )
    
    conn.executemany(
        "INSERT INTO chat_message_join (chat_id, message_id) VALUES (?, ?)",
        [(1, 1), (1, 2), (1, 3)]
    )
    
    conn.executemany(
        "INSERT INTO chat_handle_join (chat_id, handle_id) VALUES (?, ?)",
        [(1, 1), (2, 1), (2, 2), (2, 3)]
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
    }
    monkeypatch.setattr(
        "messages.contacts.get_contact_name",
        lambda x: contact_map.get(x)
    )
    
    return messages.get_db(path=test_db_path)


@pytest.fixture
def mock_region(monkeypatch):
    """Mock system region detection."""
    monkeypatch.setattr("messages.phone.get_system_region", lambda: "US")
```

### Database Tests (`tests/test_db.py`)

```python
def test_chats_returns_all_chats(messages_db):
    chats = list(messages_db.chats())
    assert len(chats) == 2


def test_chats_ordered_by_recent(messages_db):
    chats = list(messages_db.chats())
    # Chat with most recent message should be first
    assert chats[0].id == 1


def test_chats_limit(messages_db):
    chats = list(messages_db.chats(limit=1))
    assert len(chats) == 1


def test_messages_chronological_order(messages_db):
    msgs = list(messages_db.messages(chat_id=1))
    assert msgs[0].text == "Hey, are you free for lunch?"
    assert msgs[-1].text == "How about that new place on Main St?"


def test_messages_by_identifier(messages_db, mock_region):
    msgs = list(messages_db.messages(identifier="+15551234567"))
    assert len(msgs) == 3


def test_messages_date_filter(messages_db):
    from datetime import datetime
    
    msgs = list(messages_db.messages(
        chat_id=1,
        after=datetime(2024, 1, 15, 9, 31)
    ))
    assert len(msgs) == 2  # Excludes first message


def test_search_finds_matching_text(messages_db):
    results = list(messages_db.search("lunch"))
    assert len(results) == 1
    assert "lunch" in results[0].text


def test_contact_names_resolved(messages_db):
    msgs = list(messages_db.messages(chat_id=1))
    incoming = [m for m in msgs if not m.is_from_me][0]
    assert incoming.sender.display_name == "Jane Doe"
```

### Phone Normalization Tests (`tests/test_phone.py`)

```python
import pytest
from messages.phone import normalize_phone, phone_match


@pytest.mark.parametrize("input,region,expected", [
    ("+15551234567", "US", "+15551234567"),  # Already E.164
    ("555-123-4567", "US", "+15551234567"),  # US local format
    ("(555) 123-4567", "US", "+15551234567"),  # US with parens
    ("07700 900123", "GB", "+447700900123"),  # UK mobile
    ("+44 7700 900123", "GB", "+447700900123"),  # UK international
])
def test_normalize_phone(input, region, expected, monkeypatch):
    monkeypatch.setattr("messages.phone.get_system_region", lambda: region)
    assert normalize_phone(input) == expected


@pytest.mark.parametrize("query,stored,should_match", [
    ("555-123-4567", "+15551234567", True),
    ("07700 900123", "+447700900123", True),
    ("+15551234567", "+15551234567", True),
    ("555-123-4567", "+15559999999", False),
])
def test_phone_match(query, stored, should_match, monkeypatch):
    monkeypatch.setattr("messages.phone.get_system_region", lambda: "US")
    assert phone_match(query, stored) == should_match


def test_invalid_phone_raises():
    with pytest.raises(ValueError):
        normalize_phone("not a phone number")
```

### CLI Tests (`tests/test_cli.py`)

```python
from click.testing import CliRunner
from messages.cli import cli
import json


def test_cli_version():
    runner = CliRunner()
    result = runner.invoke(cli, ["--version"])
    assert result.exit_code == 0
    assert "version" in result.output


def test_chats_command(test_db_path):
    runner = CliRunner()
    result = runner.invoke(cli, ["--db", str(test_db_path), "chats"])
    assert result.exit_code == 0
    assert "Family Group" in result.output


def test_chats_json_output(test_db_path):
    runner = CliRunner()
    result = runner.invoke(cli, ["--db", str(test_db_path), "chats", "--json"])
    assert result.exit_code == 0
    data = json.loads(result.output)
    assert isinstance(data, list)
    assert len(data) == 2


def test_messages_requires_chat_or_with():
    runner = CliRunner()
    result = runner.invoke(cli, ["messages"])
    assert result.exit_code != 0
    assert "Specify --chat or --with" in result.output


def test_messages_command(test_db_path):
    runner = CliRunner()
    result = runner.invoke(cli, ["--db", str(test_db_path), "messages", "--chat", "1"])
    assert result.exit_code == 0
    assert "lunch" in result.output


def test_search_command(test_db_path):
    runner = CliRunner()
    result = runner.invoke(cli, ["--db", str(test_db_path), "search", "lunch"])
    assert result.exit_code == 0
    assert "free for lunch" in result.output


def test_missing_database():
    runner = CliRunner()
    result = runner.invoke(cli, ["--db", "/nonexistent/chat.db", "chats"])
    assert result.exit_code == 1
    assert "not found" in result.output.lower()


def test_no_contacts_flag(test_db_path):
    runner = CliRunner()
    result = runner.invoke(cli, [
        "--db", str(test_db_path),
        "--no-contacts",
        "messages", "--chat", "1"
    ])
    assert result.exit_code == 0
    # Should show phone number, not resolved name
    assert "+1555" in result.output or "5551234567" in result.output
```

### pytest Configuration

```toml
# pyproject.toml
[tool.pytest.ini_options]
testpaths = ["tests"]
```

### Running Tests

```bash
# Run all tests
uv run pytest

# Run with coverage
uv run pytest --cov=messages

# Run specific test file
uv run pytest tests/test_phone.py -v
```

---

## Future Enhancements (Out of Scope for v1)

- [ ] Export conversations to HTML with styling
- [ ] Attachment downloading/copying to specified directory
- [ ] Filter by read/unread status
- [ ] Watch mode for new messages
- [ ] Shell completion for chat IDs
- [ ] Link preview metadata extraction
