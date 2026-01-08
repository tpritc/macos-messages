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

Now let's read some messages. You can either use the chat ID you just found:

```bash
messages messages --chat 42
```

Or you can search by phone number directly. The nice thing is that any format works - you don't need to remember exactly how the number is stored:

```bash
messages messages --with "555-123-4567"
messages messages --with "+1 555 123 4567"
messages messages --with "5551234567"
```

You'll get output like this:

```
[2024-01-15 09:30] [id:12345] Mom: Hey, are you coming for dinner Sunday?
[2024-01-15 09:31] [id:12346] me: Yes! What time?
[2024-01-15 09:32] [id:12347] Mom: 6pm works. Bringing anyone?
```

## Searching messages

Maybe you're looking for something specific. The `search` command lets you find messages containing certain text:

```bash
messages search "dinner"
```

```
[2024-01-15 09:30] [id:12345] Mom: Hey, are you coming for dinner Sunday?
[2024-01-12 18:45] [id:12298] Mom: Dinner was great, thanks for coming!
```

You can limit the search to a specific conversation if you want:

```bash
messages search "project update" --chat 15
```

## Exporting conversations

Need to save a conversation? Just redirect the output to a file:

```bash
messages messages --chat 42 --limit 10000 > mom-messages.txt
```

Or get JSON if you want to process it programmatically:

```bash
messages messages --chat 42 --json > mom-messages.json
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
