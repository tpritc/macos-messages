# Python Library

If you're writing Python code, macos-messages gives you a clean API to work with your Messages.app data. This page covers everything available in the library.

## Getting started

The simplest way to get going is with `get_db()`:

```python
import messages

db = messages.get_db()

# Now you can query your messages
for chat in db.chats(limit=5):
    print(f"{chat.display_name}: {chat.message_count} messages")
```

---

## get_db()

Creates a database connection. This is the main entry point you'll use.

```python
messages.get_db(path: str | None = None) -> MessagesDB
```

| Parameter | Type | What it does |
|-----------|------|--------------|
| `path` | `str \| None` | Path to chat.db. If you don't provide one, it defaults to `~/Library/Messages/chat.db` |

**Returns:** A `MessagesDB` instance

**Raises:**

- `FileNotFoundError` if the database doesn't exist
- `PermissionError` if Full Disk Access hasn't been granted

**Example:**

```python
# Use the default location
db = messages.get_db()

# Or point to a specific database file (like a backup)
db = messages.get_db("/path/to/backup/chat.db")
```

---

## MessagesDB

This is the main class you'll work with. It provides methods to query chats, messages, and attachments.

### Creating an instance

You can use `get_db()` (shown above) or create one directly:

```python
from messages.db import MessagesDB

db = MessagesDB(path="/path/to/chat.db", resolve_contacts=True)
```

| Parameter | Type | What it does |
|-----------|------|--------------|
| `path` | `Path \| str \| None` | Path to chat.db |
| `resolve_contacts` | `bool` | Whether to look up contact names from Contacts.app (default: True) |

### chats()

Lists your conversations, ordered by most recent activity.

```python
db.chats(
    *,
    service: str | None = None,
    limit: int | None = None,
) -> Iterator[ChatSummary]
```

| Parameter | Type | What it does |
|-----------|------|--------------|
| `service` | `str \| None` | Filter by service: `"iMessage"`, `"SMS"`, or `"RCS"` |
| `limit` | `int \| None` | Maximum number of results |

**Example:**

```python
# Get your 10 most recent conversations
for chat in db.chats(limit=10):
    print(f"{chat.id}: {chat.display_name or chat.identifier}")

# Only iMessage conversations
for chat in db.chats(service="iMessage"):
    print(chat.display_name)
```

### chat()

Gets a single chat by its ID.

```python
db.chat(chat_id: int) -> Chat
```

### chat_by_identifier()

Gets a chat by phone number or email. The nice thing here is that phone number matching is smart - you can use any format and it'll find the right conversation.

```python
db.chat_by_identifier(identifier: str) -> Chat
```

**Example:**

```python
# All of these will find the same conversation
chat = db.chat_by_identifier("+1 555 123 4567")
chat = db.chat_by_identifier("555-123-4567")
chat = db.chat_by_identifier("5551234567")
chat = db.chat_by_identifier("jane@example.com")
```

### messages()

Lists messages in chronological order (oldest first).

```python
db.messages(
    *,
    chat_id: int | None = None,
    identifier: str | None = None,
    after: datetime | None = None,
    before: datetime | None = None,
    limit: int = 100,
    offset: int = 0,
    include_unsent: bool = True,
) -> Iterator[Message]
```

| Parameter | Type | What it does |
|-----------|------|--------------|
| `chat_id` | `int \| None` | Filter by chat ID |
| `identifier` | `str \| None` | Filter by phone number or email (use this instead of chat_id if you prefer) |
| `after` | `datetime \| None` | Only include messages after this date |
| `before` | `datetime \| None` | Only include messages before this date |
| `limit` | `int` | Maximum number of results (default: 100) |
| `offset` | `int` | Skip the first N results |
| `include_unsent` | `bool` | Include messages that were unsent (default: True) |

**Example:**

```python
from datetime import datetime

# Get messages by chat ID
for msg in db.messages(chat_id=42, limit=20):
    print(f"{msg.date}: {msg.text}")

# Get messages by phone number
for msg in db.messages(identifier="+15551234567"):
    print(msg.text)

# Get messages from the last month
for msg in db.messages(chat_id=42, after=datetime(2024, 1, 1)):
    print(msg.text)
```

### message()

Gets a single message by its ID, with all the details.

```python
db.message(message_id: int) -> Message
```

### search()

Searches messages by text content. The search is case-insensitive.

```python
db.search(
    query: str,
    *,
    chat_id: int | None = None,
    after: datetime | None = None,
    before: datetime | None = None,
    limit: int = 50,
) -> Iterator[Message]
```

| Parameter | Type | What it does |
|-----------|------|--------------|
| `query` | `str` | The text to search for |
| `chat_id` | `int \| None` | Only search within a specific chat |
| `after` | `datetime \| None` | Only search messages after this date |
| `before` | `datetime \| None` | Only search messages before this date |
| `limit` | `int` | Maximum number of results (default: 50) |

**Example:**

```python
for msg in db.search("dinner tomorrow"):
    print(f"[Chat {msg.chat_id}] {msg.text}")
```

### attachments()

Lists file attachments.

```python
db.attachments(
    *,
    chat_id: int | None = None,
    message_id: int | None = None,
    mime_type: str | None = None,
    limit: int = 100,
    auto_download: bool = True,
) -> Iterator[Attachment]
```

| Parameter | Type | What it does |
|-----------|------|--------------|
| `chat_id` | `int \| None` | Filter by chat |
| `message_id` | `int \| None` | Filter by message |
| `mime_type` | `str \| None` | Filter by MIME type (e.g., `"image/*"`) |
| `limit` | `int` | Maximum number of results (default: 100) |
| `auto_download` | `bool` | Automatically download iCloud attachments (default: True) |

**Example:**

```python
# Get all images from a chat
for att in db.attachments(chat_id=42, mime_type="image/*"):
    print(f"{att.filename}: {att.path}")
```

### download_attachment()

Makes sure an attachment is downloaded locally. For attachments stored in iCloud, this triggers the download and waits for it to complete.

```python
db.download_attachment(attachment: Attachment) -> Path
```

---

## Models

These are the data classes you'll get back from queries.

### Message

A single message.

```python
@dataclass
class Message:
    id: int
    chat_id: int
    text: str | None
    date: datetime
    is_from_me: bool
    sender: Handle | None
    has_attachments: bool
    reactions: list[Reaction]
    effect: MessageEffect | None
    edit_history: list[EditRecord]
    is_edited: bool
    is_unsent: bool
    transcription: str | None  # For audio messages
    reply_to_id: int | None    # For threaded replies
    thread_id: int | None
```

**Example:**

```python
msg = db.message(12345)

print(f"From: {'me' if msg.is_from_me else msg.sender.display_name}")
print(f"Text: {msg.text}")

if msg.reactions:
    for r in msg.reactions:
        print(f"  {r.sender.display_name} reacted with {r.type.value}")

if msg.is_edited:
    print(f"  Edited {len(msg.edit_history)} times")
```

### Chat

A conversation with full details.

```python
@dataclass
class Chat:
    id: int
    identifier: str
    display_name: str | None
    service: str
    participants: list[Handle]
```

### ChatSummary

A lightweight version of Chat, returned by `chats()`. Includes message counts.

```python
@dataclass
class ChatSummary:
    id: int
    identifier: str
    display_name: str | None
    service: str
    message_count: int
    last_message_date: datetime | None
```

### Handle

A contact identifier - either a phone number or email address.

```python
@dataclass
class Handle:
    id: int
    identifier: str       # The phone number or email
    service: str          # "iMessage", "SMS", or "RCS"
    display_name: str | None  # Resolved from Contacts.app
```

### Attachment

A file attachment.

```python
@dataclass
class Attachment:
    id: int
    message_id: int
    filename: str
    mime_type: str | None
    path: str            # Local path (might not exist if it's in iCloud)
    size: int
    is_sticker: bool
```

### Reaction

A tapback reaction on a message.

```python
@dataclass
class Reaction:
    type: ReactionType
    sender: Handle
    date: datetime
```

### ReactionType

The different types of tapback reactions.

```python
class ReactionType(Enum):
    LOVE = "love"           # ❤️
    LIKE = "like"           # 👍
    DISLIKE = "dislike"     # 👎
    LAUGH = "ha-ha"         # 😂
    EMPHASIS = "emphasis"   # ‼️
    QUESTION = "question"   # ❓
```

### MessageEffect

iMessage bubble and screen effects.

```python
class MessageEffect(Enum):
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
```

### EditRecord

A single edit in a message's history.

```python
@dataclass
class EditRecord:
    text: str
    date: datetime
```

---

## Putting it all together

Here's a more complete example that shows how these pieces fit together:

```python
import messages
from datetime import datetime, timedelta

db = messages.get_db()

# Find conversations with "Mom" in the name
mom_chats = [
    chat for chat in db.chats()
    if chat.display_name and "Mom" in chat.display_name
]

if mom_chats:
    mom = mom_chats[0]
    print(f"Found: {mom.display_name} ({mom.message_count} messages)")

    # Get messages from the last 7 days
    week_ago = datetime.now() - timedelta(days=7)

    for msg in db.messages(chat_id=mom.id, after=week_ago):
        sender = "Me" if msg.is_from_me else mom.display_name
        print(f"[{msg.date:%b %d %H:%M}] {sender}: {msg.text}")

        # Show reactions
        for r in msg.reactions:
            print(f"    {r.type.value} from {r.sender.display_name}")

    # Find all photos shared in this conversation
    photos = list(db.attachments(chat_id=mom.id, mime_type="image/*"))
    print(f"\n{len(photos)} photos shared")
```
