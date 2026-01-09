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

From the command line:

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

Or in Python:

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

## Installation

```bash
uv tool install macos-messages
```

You'll need to grant Full Disk Access to your terminal app before this will work. See the [Permissions](https://macos-messages.readthedocs.io/permissions/) guide for instructions.

## Documentation

Full documentation is available at [macos-messages.readthedocs.io](https://macos-messages.readthedocs.io/), including:

- [Installation](https://macos-messages.readthedocs.io/installation/) - Getting set up
- [Quickstart](https://macos-messages.readthedocs.io/quickstart/) - Your first queries
- [CLI Reference](https://macos-messages.readthedocs.io/cli/) - All the commands
- [Python Library](https://macos-messages.readthedocs.io/library/) - Full API docs
- [Permissions](https://macos-messages.readthedocs.io/permissions/) - macOS permissions explained

## Requirements

- macOS
- Python 3.12+
- Full Disk Access permission for your terminal

## Contributing

Bug reports and pull requests are welcome on [GitHub](https://github.com/tpritc/macos-messages). This project is intended to be a safe, welcoming space for collaboration.

## License

The library is available as open source under the terms of the [MIT License](https://opensource.org/licenses/MIT).
