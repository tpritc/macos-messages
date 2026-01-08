# CLI Reference

The `messages` command gives you access to your Messages.app data right from the terminal. This page covers all the available commands and options.

## Quick reference

```bash
# Show help
messages
messages --help

# List chats
messages chats
messages chats --search "john"

# List contacts
messages contacts
messages contacts --search "john"

# List messages from a chat
messages --chat 42
messages --chat "Mom"
messages --with "John Doe"

# Search messages
messages --search "dinner"
messages --with "John Doe" --search "dinner"
messages --with "John Doe" --search "dinner" --since 2025-07-15
```

---

## Global options

These options work with any command:

| Option | What it does |
|--------|--------------|
| `--db PATH` | Use a different database file (defaults to `~/Library/Messages/chat.db`) |
| `--no-contacts` | Don't resolve phone numbers to contact names |
| `--version` | Show the version number |
| `--help` | Show help |

---

## Listing messages

When you provide message options directly to `messages`, it lists messages from a conversation. Use `--chat` or `--with` to specify the conversation, and `--search` to search within messages.

```bash
messages [OPTIONS]
```

| Option | What it does |
|--------|--------------|
| `-c, --chat ID\|NAME` | Chat ID or display name |
| `-w, --with NAME` | Contact name (exact match) |
| `-s, --search TEXT` | Search messages for text |
| `--since DATETIME` | Only show messages after this date (YYYY-MM-DD) |
| `--before DATETIME` | Only show messages before this date (YYYY-MM-DD) |
| `-f, --first INTEGER` | Show first N messages (oldest) |
| `-l, --last INTEGER` | Show last N messages (newest, default: 50) |
| `--with-attachments` | Only show messages with attachments |
| `--json` | Output as JSON |

!!! note "--chat and --with are mutually exclusive"
    You can use `--chat` or `--with`, but not both. If you specify both, the command will exit with an error.

**Examples:**

```bash
# Get the last 50 messages from chat ID 42
messages --chat 42

# Get messages by chat display name
messages --chat "Mom"

# Get messages with a contact (exact name match)
messages --with "John Doe"

# Search all messages
messages --search "dinner"

# Search within a conversation
messages --with "John Doe" --search "dinner"

# Messages from the last week
messages --chat 42 --since 2025-01-01

# Date range
messages --chat 42 --since 2025-01-01 --before 2025-01-15

# Only show messages with attachments
messages --chat 42 --with-attachments

# Get JSON for scripting
messages --chat 42 --json | jq '.[] | select(.is_from_me == false)'
```

**What the output looks like:**

```
[January 15, 2025]
Mom (10:30am): Hey, are you free for lunch?
me (10:31am): Sure! Where? [❤️ 1, 👍 1]
Mom (10:32am): How about Main St? (edited)
```

With `--with-attachments`:

```
[January 15, 2025]
Mom (10:33am): Check out this photo!
  [image: ~/Library/Messages/Attachments/ab/cd/photo.jpg]
```

---

## chats

Lists your conversations, ordered by most recent activity.

```bash
messages chats [OPTIONS]
```

| Option | What it does |
|--------|--------------|
| `-s, --search TEXT` | Filter chats by display name |
| `--service [imessage\|sms\|rcs]` | Only show chats from a specific service |
| `-n, --limit INTEGER` | How many to show (default: 20) |
| `--json` | Output as JSON instead of plain text |

**Examples:**

```bash
# Show your 20 most recent conversations
messages chats

# Search for chats by name
messages chats --search "john"

# Show your 10 most recent conversations
messages chats --limit 10

# Only iMessage conversations
messages chats --service imessage

# Get JSON for scripting
messages chats --json | jq '.[0]'
```

**What the output looks like:**

```
42 Mom (iMessage) - 1,247 messages
15 Work Group (iMessage) - 892 messages
```

The number at the start is the chat ID, which you can use with `--chat`.

---

## contacts

Lists contacts from your macOS Contacts.app.

```bash
messages contacts [OPTIONS]
```

| Option | What it does |
|--------|--------------|
| `-s, --search TEXT` | Filter contacts by name |
| `-n, --limit INTEGER` | How many to show (default: 20) |
| `--json` | Output as JSON instead of plain text |

**Examples:**

```bash
# List contacts
messages contacts

# Search for contacts by name
messages contacts --search "john"

# Get JSON for scripting
messages contacts --json
```

**What the output looks like:**

```
John Doe
John Smith
Debbie Johnson
```

---

## Output formats

By default, commands output plain text that's easy to read and pipe to other tools. If you need machine-readable output, use `--json`:

```bash
messages --chat 42 --json | jq '.[] | select(.is_from_me == false)'
```

---

## Error messages

If something goes wrong, you'll get one of these errors:

| Error | What it means |
|-------|---------------|
| `Messages database not found` | The chat.db file doesn't exist at the expected location |
| `Cannot read Messages database. Grant Full Disk Access...` | Your terminal needs Full Disk Access permission |
| `Chat 999 not found` | There's no chat with that ID |
| `Multiple chats match "Name"` | More than one chat matches the display name—use the chat ID instead |
| `Cannot specify both --chat and --with` | These options are mutually exclusive |
| `Contact "Name" not found` | No contact with that exact name was found |
