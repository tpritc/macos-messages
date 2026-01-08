# Quickstart

Let's get you reading your messages in just a few minutes.

## Finding a conversation

First, let's see what conversations you have. Run this command to list your most recent chats:

```bash
messages chats
```

You'll see something like:

```
42 Mom (iMessage) - 1,247 messages
15 Work Group (iMessage) - 892 messages
23 jane@example.com (iMessage) - 456 messages
```

That number at the beginning is the chat ID. You'll use this to fetch messages from a specific conversation.

## Reading messages

Now let's read some messages. You can use the chat ID you just found:

```bash
messages --chat 42
```

Or you can use the chat's display name:

```bash
messages --chat "Mom"
```

Or you can use a contact name (exact match):

```bash
messages --with "Mom"
```

You'll get output like this:

```
[January 15, 2025]

Mom (9:30am): Hey, are you coming for dinner Sunday?
You (9:31am): Yes! What time?
Mom (9:32am): 6pm works. Bringing anyone?
```

## Searching messages

Maybe you're looking for something specific. Use `--search` to find messages containing certain text:

```bash
messages --search "dinner"
```

```
[January 15, 2025]

Mom (9:30am): Hey, are you coming for dinner Sunday?

[January 12, 2025]

Mom (6:45pm): Dinner was great, thanks for coming!
```

You can limit the search to a specific conversation if you want:

```bash
messages --with "Mom" --search "dinner"
```

## Exporting conversations

Need to save a conversation? Just redirect the output to a file:

```bash
messages --chat 42 --limit 10000 > mom-messages.txt
```

Or get JSON if you want to process it programmatically:

```bash
messages --chat 42 --json > mom-messages.json
```

## Using the Python library

If you're writing Python code, here's how to do the same things:

```python
import messages

db = messages.get_db()

# Find a conversation with "Mom" in the name
for chat in db.chats(limit=10):
    if chat.display_name and "Mom" in chat.display_name:
        mom_chat = chat
        break

# Read the last 20 messages
for msg in db.messages(chat_id=mom_chat.id, limit=20):
    if msg.is_from_me:
        print(f"me: {msg.text}")
    else:
        print(f"Mom: {msg.text}")

    # Check for reactions
    if msg.reactions:
        for r in msg.reactions:
            print(f"  {r.sender.display_name} reacted with {r.type.value}")
```

## What's next?

Now that you've got the basics down, check out:

- [CLI Reference](cli.md) - All the commands and options available
- [Python Library](library.md) - Full API documentation with all the models
- [Permissions](permissions.md) - If you ran into any access issues
