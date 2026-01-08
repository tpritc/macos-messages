# Installation

Getting macos-messages installed is straightforward. The recommended way is with [uv](https://docs.astral.sh/uv/), but pip works too.

## Installing with uv

If you want the `messages` command available everywhere on your system:

```bash
uv tool install macos-messages
```

You can also install directly from GitHub if you want the latest development version:

```bash
uv tool install git+https://github.com/tpritc/macos-messages
```

## Installing with pip

```bash
pip install macos-messages
```

## Development setup

If you want to work on macos-messages itself, clone the repo and use uv to set up the development environment:

```bash
git clone https://github.com/tpritc/macos-messages
cd macos-messages
uv sync

# Run commands during development
uv run messages --help

# Run the tests
uv run pytest
```

## Setting up permissions

Before macos-messages can read your messages, you need to grant Full Disk Access to your terminal app. This is a macOS security requirement because the Messages database is in a protected location.

The [Permissions](permissions.md) page has step-by-step instructions for setting this up.

## Verifying it works

Once you've installed macos-messages and set up permissions, give it a quick test:

```bash
messages chats --limit 3
```

If everything's working, you'll see a list of your recent conversations. If you get a permission error instead, head over to [Permissions](permissions.md) to troubleshoot.
