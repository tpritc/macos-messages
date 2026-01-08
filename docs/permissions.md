# Permissions

Before macos-messages can read your messages, you need to grant some permissions. This page explains what's needed and walks you through setting it up.

## Full Disk Access (required)

Your Messages database lives at `~/Library/Messages/chat.db`, and macOS protects this file pretty aggressively. To read it, your terminal app needs Full Disk Access.

### How to set it up

1. Open **System Settings**
2. Go to **Privacy & Security** → **Full Disk Access**
3. Click the **+** button
4. Find and select your terminal app:
   - **Terminal.app** (in `/Applications/Utilities/`)
   - **iTerm.app** (in `/Applications/`)
   - Or whatever terminal you use (Warp, Alacritty, etc.)
5. Make sure the toggle is enabled
6. **Restart your terminal completely** - this is important!

The permission change won't take effect until you quit and reopen your terminal. Not just open a new tab - actually quit the app and start it again.

### Checking if it worked

After restarting your terminal, try this:

```bash
messages chats --limit 1
```

If you see a conversation listed, you're good to go. If you get a permission error, double-check that:

- Your terminal app is in the Full Disk Access list
- The toggle next to it is actually enabled
- You've completely restarted the terminal since enabling it

### Running from an IDE

If you're running macos-messages from an IDE's integrated terminal (VS Code, PyCharm, etc.), you need to grant Full Disk Access to the IDE itself, not Terminal.app.

For VS Code specifically:

1. Add **Visual Studio Code.app** to Full Disk Access
2. Restart VS Code completely

---

## Contacts Access (automatic with Full Disk Access)

macos-messages can look up phone numbers in your Contacts to show names instead of raw numbers. This makes the output much nicer to read:

```
# With Contacts access:
[2024-01-15 09:30] Mom: Hey, are you free?

# Without Contacts access:
[2024-01-15 09:30] +15551234567: Hey, are you free?
```

### How it works

macos-messages reads directly from the Contacts database at `~/Library/Application Support/AddressBook/`. Since you've already granted Full Disk Access for Messages, Contacts lookup works automatically without any additional permissions needed.

### Skipping contact resolution

If you'd rather see raw phone numbers, you can disable contact resolution:

**From the CLI:**
```bash
messages --no-contacts chats
```

**From Python:**
```python
db = messages.get_db()
db.resolve_contacts = False
```

---

## Troubleshooting

### "Cannot read Messages database"

This means Full Disk Access isn't working. Check:

1. Is your terminal in the Full Disk Access list in System Settings?
2. Is the toggle actually enabled (not just added to the list)?
3. Have you restarted your terminal since enabling it?

### "Messages database not found"

The database doesn't exist where macos-messages expects it. This usually means:

- You've never used Messages.app on this Mac
- You're on a system that doesn't have Messages.app
- The database is in a non-standard location

If your database is somewhere else, you can point to it directly:

```bash
messages --db /path/to/chat.db chats
```

### Contact names not showing up

If you're seeing phone numbers instead of names:

1. Check that Full Disk Access is enabled for your terminal (this covers both Messages and Contacts)
2. Try running `messages chats --limit 5` to see if names appear
3. Make sure the contact actually has a phone number that matches (formats don't need to match exactly, we normalize them)

If contacts still aren't resolving, the Contacts database might be in an unexpected location (e.g., if you're not using iCloud for contacts).

---

## Security notes

### What macos-messages can access

- `~/Library/Messages/chat.db` - Read-only access to your Messages database
- `~/Library/Application Support/AddressBook/` - Read-only access to your Contacts database (for name lookups)

### What it doesn't do

- It never modifies your messages or database
- It can't send messages
- It doesn't access your Apple ID or iCloud credentials
- It doesn't upload anything anywhere

The database is always opened in read-only mode:

```python
sqlite3.connect(f"file:{path}?mode=ro", uri=True)
```

### A note about privacy

Your message history contains private conversations. Keep that in mind when:

- Exporting conversations to files
- Using `--json` output in scripts or pipelines
- Running in shared or logged environments

macos-messages is designed for personal use on your own Mac - reading your own messages for your own purposes.
