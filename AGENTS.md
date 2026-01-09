# AGENTS.md

## Project Overview

macos-messages is a Python library and CLI for read-only access to macOS Messages.app data (iMessage/SMS/RCS). It reads from the SQLite database at `~/Library/Messages/chat.db`.

## Common Commands

```bash
# Install dependencies
uv sync

# Run tests
uv run pytest

# Run a single test
uv run pytest tests/test_db.py::test_messages_basic

# Run tests with coverage
uv run pytest --cov=messages

# Lint and format
uv run ruff check src tests
uv run ruff format src tests

# Run CLI during development
uv run messages --help
uv run messages chats
uv run messages --chat 42
```

## Architecture

### Core Components

- **`src/messages/db.py`** - `MessagesDB` class: main database interface. Handles SQLite connection, queries, and coordinate resolution between tables. Key methods: `chats()`, `messages()`, `search()`, `attachments()`.

- **`src/messages/models.py`** - Dataclasses (`Message`, `Chat`, `Handle`, `Attachment`, etc.) and Apple date conversion utilities. Dates in the database are nanoseconds since 2001-01-01.

- **`src/messages/cli.py`** - Click-based CLI. The main `cli` group handles message listing directly (not as a subcommand), while `chats`, `contacts`, and `index` are subcommands.

- **`src/messages/contacts.py`** - Reads from macOS Contacts.app database to resolve phone numbers/emails to display names.

- **`src/messages/phone.py`** - Phone number normalization using `phonenumbers` library for international format matching.

### Search System

The search system has multiple layers:
- **Basic search** (`db.search()`) - SQL LIKE queries
- **`search_index.py`** - FTS5 full-text search with stemming support
- **`embeddings.py`** - Optional semantic search using sentence-transformers (requires `[semantic]` extra)
- **`hybrid_search.py`** - Combines keyword, stemmed, and semantic search modes

### Key Database Details

The Messages database has these key tables: `message`, `chat`, `handle`, `chat_message_join`, `chat_handle_join`, `attachment`, `message_attachment_join`.

Message text can be in either the `text` column or encoded in `attributedBody` (NSKeyedArchiver format). The `_extract_text_from_attributed_body()` function in `db.py` handles this extraction.

## Testing

Tests use a mock database created in `tests/conftest.py` with the `test_db_path` and `messages_db` fixtures. Contact resolution is mocked to return predictable names.

## Documentation

**Important:** When making changes, always check if documentation needs updating:

- **README.md** - Update if adding/changing CLI options, new features, installation steps, or usage examples
- **docs/** - Public documentation site. Update when adding features, changing APIs, or modifying user-facing behavior
- **Docstrings** - Update function/class docstrings if changing their behavior or parameters
- **AGENTS.md** - Update if changing architecture, adding new modules, or modifying development workflows

Before completing any PR or significant change, ask: "Would a user or developer need to know about this change?" If yes, update the relevant docs.

## Release Process

To release a new version:

1. **Update version numbers** in both files:
   - `pyproject.toml`: `version = "X.Y.Z"`
   - `src/messages/__init__.py`: `__version__ = "X.Y.Z"`

2. **Update CHANGELOG.md** with the new version section:
   ```markdown
   ## [X.Y.Z] - YYYY-MM-DD

   ### Added
   - New features...

   ### Changed
   - Changes to existing functionality...

   ### Fixed
   - Bug fixes...
   ```
   Add the release link at the bottom: `[X.Y.Z]: https://github.com/tpritc/macos-messages/releases/tag/vX.Y.Z`

3. **Commit the version bump**

4. **Create and push the tag**:
   ```bash
   git tag -a vX.Y.Z -m "Release X.Y.Z"
   git push origin vX.Y.Z
   ```

5. **Create GitHub release** (include section headings like `### Changed` for consistency):
   ```bash
   gh release create vX.Y.Z --title "X.Y.Z" --notes "### Changed

   - First change
   - Second change"
   ```

6. **Build and publish to PyPI**:
   ```bash
   uv build
   uv publish --token "$(op read 'op://Private/PyPI/api token' --account my.1password.com)"
   ```
