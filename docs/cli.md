# CLI Reference

The `messages` command gives you access to your Messages.app data right from the terminal. This page covers all the available commands and options.

## Global options

These options work with any command:

```bash
messages [OPTIONS] COMMAND [ARGS]
```

| Option | What it does |
|--------|--------------|
| `--db PATH` | Use a different database file (defaults to `~/Library/Messages/chat.db`) |
| `--no-contacts` | Don't resolve phone numbers to contact names |
| `--version` | Show the version number |
| `--help` | Show help |

## chats

Lists your conversations, ordered by most recent activity.

```bash
messages chats [OPTIONS]
```

| Option | What it does |
|--------|--------------|
| `--service [imessage\|sms\|rcs]` | Only show chats from a specific service |
| `-n, --limit INTEGER` | How many to show (default: 20) |
| `--json` | Output as JSON instead of plain text |

**Examples:**

```bash
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

The number at the start is the chat ID, which you'll use with other commands.

---

## messages

Lists messages from a conversation. You need to specify which conversation using either `--chat` (with a chat ID) or `--with` (with a phone number or email).

```bash
messages messages [OPTIONS]
```

| Option | What it does |
|--------|--------------|
| `-c, --chat INTEGER` | Chat ID (get this from the `chats` command) |
| `-w, --with TEXT` | Phone number or email address |
| `--after DATETIME` | Only show messages after this date (YYYY-MM-DD) |
| `--before DATETIME` | Only show messages before this date (YYYY-MM-DD) |
| `-n, --limit INTEGER` | How many to show (default: 50) |
| `--offset INTEGER` | Skip the first N messages |
| `--no-unsent` | Don't include messages that were unsent |
| `-v, --verbose` | Show more details (like who reacted to each message) |
| `--json` | Output as JSON |

**Examples:**

```bash
# Get messages by chat ID
messages messages --chat 42

# Get messages by phone number (any format works!)
messages messages --with "+1 555 123 4567"
messages messages --with "555-123-4567"
messages messages --with "5551234567"

# Messages from the last week
messages messages --chat 42 --after 2024-01-08

# See who reacted to each message
messages messages --chat 42 --verbose

# Export a whole conversation
messages messages --chat 42 --limit 10000 > conversation.txt
```

**What the output looks like:**

```
[2024-01-15 09:30] [id:12345] Mom: Hey, are you free for lunch?
[2024-01-15 09:31] [id:12346] me: Sure! Where? [2 reactions: 1 love, 1 like]
[2024-01-15 09:32] [id:12347] Mom: How about Main St? (edited)
```

With `--verbose`, you'll see who left each reaction:

```
[2024-01-15 09:31] [id:12346] me: Sure! Where?
  reactions: Mom love, Dad like
```

---

## read

Shows a single message with all its details. Useful when you want to see the full picture - edit history, all reactions, effects, etc.

```bash
messages read MESSAGE_ID [OPTIONS]
```

| Option | What it does |
|--------|--------------|
| `--json` | Output as JSON |

**Examples:**

```bash
messages read 12345
messages read 12345 --json
```

**What the output looks like:**

```
ID: 12345
Date: 2024-01-15 09:31:00
From: me
Chat: 42
Effect: balloons

Sure! Where were you thinking?

Reactions (2):
  love from Mom
  like from Dad
```

---

## search

Searches your messages for specific text. The search is case-insensitive.

```bash
messages search QUERY [OPTIONS]
```

| Option | What it does |
|--------|--------------|
| `-c, --chat INTEGER` | Only search within a specific chat |
| `--after DATETIME` | Only search messages after this date |
| `--before DATETIME` | Only search messages before this date |
| `-n, --limit INTEGER` | How many results to show (default: 20) |
| `-v, --verbose` | Show more details |
| `--json` | Output as JSON |

**Examples:**

```bash
# Search all your messages
messages search "dinner"

# Search within a specific conversation
messages search "project update" --chat 15

# Search within a date range
messages search "birthday" --after 2024-01-01 --before 2024-02-01
```

---

## attachments

Lists file attachments (images, videos, documents, etc.) from your messages.

```bash
messages attachments [OPTIONS]
```

| Option | What it does |
|--------|--------------|
| `-c, --chat INTEGER` | Only show attachments from a specific chat |
| `-m, --message INTEGER` | Only show attachments from a specific message |
| `--type TEXT` | Filter by MIME type (e.g., `image/*`, `image/png`) |
| `-n, --limit INTEGER` | How many to show (default: 20) |
| `--no-download` | Don't automatically download iCloud attachments |
| `--json` | Output as JSON |

**Examples:**

```bash
# All attachments from a chat
messages attachments --chat 42

# Only images
messages attachments --chat 42 --type "image/*"

# Attachments from a specific message
messages attachments --message 12345
```

**What the output looks like:**

```
1001 IMG_1234.jpg (245KB) image/jpeg
  ~/Library/Messages/Attachments/ab/cd/IMG_1234.jpg
```

---

## Output formats

By default, commands output plain text that's easy to read and pipe to other tools. If you need machine-readable output, use `--json`:

```bash
messages messages --chat 42 --json | jq '.[] | select(.is_from_me == false)'
```

The `--verbose` flag (on commands that support it) shows extra details like who reacted to each message.

---

## Error messages

If something goes wrong, you'll get one of these errors:

| Error | What it means |
|-------|---------------|
| `Messages database not found` | The chat.db file doesn't exist at the expected location |
| `Cannot read Messages database. Grant Full Disk Access...` | Your terminal needs Full Disk Access permission |
| `Chat 999 not found` | There's no chat with that ID |
| `Could not parse phone number` | The phone number format wasn't recognized |
