# macos-messages

macos-messages is a Python library and CLI for reading your macOS Messages.app data. It gives you quick, easy, read-only access to your iMessage and SMS history.

## Why would I want this?

I built this primarily so AI agents (like Claude running in a terminal) can read my messages on my behalf. When I'm working with an AI assistant and I say "find that restaurant recommendation someone texted me last week," I want it to actually be able to go look.

But it's useful for plenty of other things too:

- Search your messages for something you know someone sent you
- Export conversations for safekeeping
- Build tools that analyze your messaging patterns
- Pipe message data into other scripts

The key thing is that it's **read-only**. macos-messages can't send messages, modify anything, or access your Apple ID. It just reads what's already on your Mac.

## What it looks like

Here's a quick taste of what you can do with the Python library:

```python
import messages

db = messages.get_db()

# Get your recent conversations
for chat in db.chats(limit=5):
    print(f"{chat.display_name}: {chat.message_count} messages")

# Read messages from a specific chat
for msg in db.messages(chat_id=42, limit=10):
    sender = "me" if msg.is_from_me else msg.sender.display_name
    print(f"{sender}: {msg.text}")
```

Or if you prefer working from the command line:

```bash
# List your conversations
messages chats

# Get messages from a chat
messages --chat 42
messages --chat "Mom"

# Get messages with a contact
messages --with "Mom"

# Search across everything
messages --search "dinner tomorrow"
```

## Features

- **Agent-friendly** - Designed for CLI agents to read messages on your behalf. The output is clean and easy to parse.

- **Smart phone number matching** - Search for `555-123-4567`, `+1 555 123 4567`, or `5551234567` and they'll all find the same conversation. No need to remember exactly how the number is stored.

- **Contact name resolution** - Phone numbers are automatically resolved to names from your Contacts.app, so you see "Mom" instead of "+15551234567".

- **Full message data** - Access everything: reactions (tapbacks), message edits, effects (like balloons or confetti), attachments, audio transcriptions, and threaded replies.

- **Read-only by design** - The database is always opened in read-only mode. No risk of accidentally modifying your messages.

## Requirements

- macOS (tested on Sonoma 14.0+)
- Python 3.12+
- Full Disk Access permission for your terminal (see [Permissions](permissions.md))

## Getting started

Head over to [Installation](installation.md) to get set up, then check out the [Quickstart](quickstart.md) to run your first queries.
