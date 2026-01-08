"""Command-line interface for macos-messages."""

import json
import sys
from dataclasses import asdict
from datetime import datetime
from typing import Any

import click

import messages
from messages.models import Message


def json_serializer(obj: Any) -> Any:
    """JSON serializer for objects not serializable by default."""
    if isinstance(obj, datetime):
        return obj.isoformat()
    if hasattr(obj, "value"):  # Enum
        return obj.value
    raise TypeError(f"Object of type {type(obj)} is not JSON serializable")


def format_reactions_compact(msg: Message) -> str:
    """Format reactions as '[N reactions: X type, Y type]'."""
    if not msg.reactions:
        return ""
    counts: dict[str, int] = {}
    for r in msg.reactions:
        counts[r.type.value] = counts.get(r.type.value, 0) + 1
    parts = [f"{count} {rtype}" for rtype, count in counts.items()]
    return f" [{len(msg.reactions)} reactions: {', '.join(parts)}]"


def format_reactions_verbose(msg: Message) -> str:
    """Format reactions with who reacted."""
    if not msg.reactions:
        return ""
    parts = []
    for r in msg.reactions:
        name = r.sender.display_name or r.sender.identifier
        parts.append(f"{name} {r.type.value}")
    return f"\n  reactions: {', '.join(parts)}"


def format_message(msg: Message, verbose: bool = False) -> str:
    """Format a message for plain text output."""
    sender = "me" if msg.is_from_me else (
        msg.sender.display_name or msg.sender.identifier if msg.sender else "?"
    )
    text = msg.text or "(no text)"
    if msg.transcription:
        text = f"[audio] {msg.transcription}"

    reactions = format_reactions_verbose(msg) if verbose else format_reactions_compact(msg)

    line = f"[{msg.date:%Y-%m-%d %H:%M}] [id:{msg.id}] {sender}: {text}"
    if not verbose:
        line += reactions

    if verbose and reactions:
        line += reactions

    if msg.is_edited:
        line += " (edited)"
    if msg.is_unsent:
        line += " (unsent)"
    if msg.effect:
        line += f" [effect:{msg.effect.value}]"

    return line


@click.group()
@click.version_option(version=messages.__version__)
@click.option(
    "--db",
    type=click.Path(),
    help="Path to chat.db (default: ~/Library/Messages/chat.db)",
)
@click.option(
    "--no-contacts",
    is_flag=True,
    help="Don't resolve phone numbers to contact names",
)
@click.pass_context
def cli(ctx: click.Context, db: str | None, no_contacts: bool) -> None:
    """Read messages from macOS Messages.app.

    Requires Full Disk Access permission for Terminal.
    """
    ctx.ensure_object(dict)
    try:
        ctx.obj["db"] = messages.get_db(db)
        ctx.obj["db"].resolve_contacts = not no_contacts
    except PermissionError as e:
        click.echo(str(e), err=True)
        sys.exit(1)
    except FileNotFoundError as e:
        click.echo(f"Error: {e}", err=True)
        sys.exit(1)


@cli.command()
@click.option("--service", type=click.Choice(["imessage", "sms", "rcs"], case_sensitive=False))
@click.option("--limit", "-n", type=int, default=20)
@click.option("--json", "as_json", is_flag=True, help="Output as JSON")
@click.pass_context
def chats(ctx: click.Context, service: str | None, limit: int, as_json: bool) -> None:
    """List conversations."""
    db = ctx.obj["db"]

    # Convert service to the format used in the database
    service_map = {"imessage": "iMessage", "sms": "SMS", "rcs": "RCS"}
    db_service = service_map.get(service.lower()) if service else None

    results = list(db.chats(service=db_service, limit=limit))

    if as_json:
        click.echo(json.dumps([asdict(c) for c in results], default=json_serializer, indent=2))
    else:
        for chat in results:
            name = chat.display_name or chat.identifier
            click.echo(f"{chat.id} {name} ({chat.service}) - {chat.message_count} messages")


@cli.command("messages")
@click.option("--chat", "-c", "chat_id", type=int, help="Chat ID")
@click.option("--with", "-w", "identifier", help="Phone number or email")
@click.option("--after", type=click.DateTime(), help="After date (YYYY-MM-DD)")
@click.option("--before", type=click.DateTime(), help="Before date (YYYY-MM-DD)")
@click.option("--first", "-f", "first_n", type=int, help="Show first N messages (oldest)")
@click.option("--last", "-l", "last_n", type=int, default=50, help="Show last N messages (newest, default: 50)")
@click.option("--offset", type=int, default=0)
@click.option("--no-unsent", is_flag=True, help="Exclude unsent messages")
@click.option("--verbose", "-v", is_flag=True, help="Show detailed reaction info")
@click.option("--json", "as_json", is_flag=True, help="Output as JSON")
@click.pass_context
def list_messages(
    ctx: click.Context,
    chat_id: int | None,
    identifier: str | None,
    after: datetime | None,
    before: datetime | None,
    first_n: int | None,
    last_n: int,
    offset: int,
    no_unsent: bool,
    verbose: bool,
    as_json: bool,
) -> None:
    """List messages from a conversation."""
    db = ctx.obj["db"]

    if not chat_id and not identifier:
        raise click.UsageError("Specify --chat or --with")

    # Determine limit and direction
    # If --first is specified, use it (oldest first)
    # Otherwise use --last (newest first, the default)
    if first_n is not None:
        limit = first_n
        reverse = False
    else:
        limit = last_n
        reverse = True

    try:
        results = list(
            db.messages(
                chat_id=chat_id,
                identifier=identifier,
                after=after,
                before=before,
                limit=limit,
                offset=offset,
                include_unsent=not no_unsent,
                reverse=reverse,
            )
        )
        # When showing last N (reverse), re-reverse so messages appear in chronological order
        if reverse:
            results = list(reversed(results))
    except LookupError as e:
        click.echo(f"Error: {e}", err=True)
        sys.exit(1)
    except ValueError as e:
        click.echo(f"Error: {e}", err=True)
        sys.exit(1)

    if as_json:
        click.echo(json.dumps([asdict(m) for m in results], default=json_serializer, indent=2))
    else:
        for msg in results:
            click.echo(format_message(msg, verbose=verbose))


@cli.command()
@click.argument("message_id", type=int)
@click.option("--json", "as_json", is_flag=True, help="Output as JSON")
@click.pass_context
def read(ctx: click.Context, message_id: int, as_json: bool) -> None:
    """Read a single message with full details."""
    db = ctx.obj["db"]

    try:
        msg = db.message(message_id)
    except LookupError as e:
        click.echo(f"Error: {e}", err=True)
        sys.exit(1)

    if as_json:
        click.echo(json.dumps(asdict(msg), default=json_serializer, indent=2))
    else:
        sender = "me" if msg.is_from_me else (
            msg.sender.display_name or msg.sender.identifier if msg.sender else "?"
        )
        click.echo(f"ID: {msg.id}")
        click.echo(f"Date: {msg.date}")
        click.echo(f"From: {sender}")
        click.echo(f"Chat: {msg.chat_id}")
        if msg.effect:
            click.echo(f"Effect: {msg.effect.value}")
        if msg.is_edited:
            click.echo(f"Edited: {len(msg.edit_history)} times")
            for edit in msg.edit_history:
                click.echo(f"  [{edit.date}] {edit.text}")
        if msg.is_unsent:
            click.echo("Status: unsent")
        click.echo()
        click.echo(msg.text or "(no text)")
        if msg.transcription:
            click.echo(f"\nTranscription: {msg.transcription}")
        if msg.reactions:
            click.echo(f"\nReactions ({len(msg.reactions)}):")
            for r in msg.reactions:
                name = r.sender.display_name or r.sender.identifier
                click.echo(f"  {r.type.value} from {name}")


@cli.command()
@click.argument("query")
@click.option("--chat", "-c", "chat_id", type=int, help="Limit to chat ID")
@click.option("--after", type=click.DateTime(), help="After date")
@click.option("--before", type=click.DateTime(), help="Before date")
@click.option("--limit", "-n", type=int, default=20)
@click.option("--verbose", "-v", is_flag=True, help="Show detailed reaction info")
@click.option("--json", "as_json", is_flag=True, help="Output as JSON")
@click.pass_context
def search(
    ctx: click.Context,
    query: str,
    chat_id: int | None,
    after: datetime | None,
    before: datetime | None,
    limit: int,
    verbose: bool,
    as_json: bool,
) -> None:
    """Search messages by text content."""
    db = ctx.obj["db"]

    results = list(
        db.search(
            query,
            chat_id=chat_id,
            after=after,
            before=before,
            limit=limit,
        )
    )

    if as_json:
        click.echo(json.dumps([asdict(m) for m in results], default=json_serializer, indent=2))
    else:
        for msg in results:
            click.echo(format_message(msg, verbose=verbose))


@cli.command()
@click.option("--chat", "-c", "chat_id", type=int, help="Filter by chat")
@click.option("--message", "-m", "message_id", type=int, help="Filter by message")
@click.option("--type", "mime_type", help="Filter by MIME type (e.g., image/*)")
@click.option("--limit", "-n", type=int, default=20)
@click.option("--no-download", is_flag=True, help="Don't auto-download iCloud attachments")
@click.option("--json", "as_json", is_flag=True, help="Output as JSON")
@click.pass_context
def attachments(
    ctx: click.Context,
    chat_id: int | None,
    message_id: int | None,
    mime_type: str | None,
    limit: int,
    no_download: bool,
    as_json: bool,
) -> None:
    """List attachments."""
    db = ctx.obj["db"]

    results = list(
        db.attachments(
            chat_id=chat_id,
            message_id=message_id,
            mime_type=mime_type,
            limit=limit,
            auto_download=not no_download,
        )
    )

    if as_json:
        click.echo(json.dumps([asdict(a) for a in results], default=json_serializer, indent=2))
    else:
        for att in results:
            size_kb = att.size // 1024 if att.size else 0
            click.echo(f"{att.id} {att.filename} ({size_kb}KB) {att.mime_type or ''}")
            click.echo(f"  {att.path}")
