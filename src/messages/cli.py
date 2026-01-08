"""Command-line interface for macos-messages."""

import json
import sys
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import click

import messages
from messages.models import Message


def json_serializer(obj: Any) -> Any:
    """JSON serializer for objects not serializable by default.
    
    Datetimes are output as UTC with Z suffix (ISO 8601).
    Naive datetimes from the database are already in UTC.
    """
    if isinstance(obj, datetime):
        # Naive datetimes from the Messages database are in UTC
        if obj.tzinfo is None:
            utc_dt = obj.replace(tzinfo=timezone.utc)
        else:
            utc_dt = obj.astimezone(timezone.utc)
        # Format as ISO 8601 with Z suffix
        return utc_dt.strftime("%Y-%m-%dT%H:%M:%SZ")
    if hasattr(obj, "value"):  # Enum
        return obj.value
    raise TypeError(f"Object of type {type(obj)} is not JSON serializable")


def message_to_dict(msg: Message, db: "messages.MessagesDB") -> dict:
    """Convert a Message to a dict, including attachments if present."""
    result = asdict(msg)
    # Clean up text by removing Object Replacement Character
    if result.get("text"):
        result["text"] = result["text"].replace("\ufffc", "").strip() or None
    # Add attachments if present
    if msg.has_attachments:
        atts = list(db.attachments(message_id=msg.id))
        result["attachments"] = [
            {
                "id": att.id,
                "filename": att.filename,
                "mime_type": att.mime_type,
                "path": att.path.replace("~", str(Path.home())) if att.path else None,
                "size": att.size,
                "is_sticker": att.is_sticker,
            }
            for att in atts
        ]
    else:
        result["attachments"] = []
    return result


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


def format_message(msg: Message, verbose: bool = False, attachments: list | None = None) -> str:
    """Format a message for plain text output in IRC-style format.
    
    Times are displayed in the user's local timezone.
    Naive datetimes from the database are treated as UTC.
    
    Args:
        msg: The message to format
        verbose: If True, show detailed reaction info
        attachments: Optional list of Attachment objects for this message
    """
    sender = "You" if msg.is_from_me else (
        msg.sender.display_name or msg.sender.identifier if msg.sender else "?"
    )
    
    # Build text with attachment indicators
    text = msg.text or ""
    
    # Remove Object Replacement Character (used as placeholder for attachments)
    text = text.replace("\ufffc", "").strip()
    
    # Add attachment indicator if message has attachments
    if msg.has_attachments and attachments:
        attachment_parts = []
        for att in attachments:
            # Determine attachment type from mime_type
            if att.mime_type:
                if att.mime_type.startswith("image/"):
                    att_type = "image"
                elif att.mime_type.startswith("video/"):
                    att_type = "video"
                elif att.mime_type.startswith("audio/"):
                    att_type = "audio"
                else:
                    att_type = "file"
            else:
                att_type = "file"
            # Use the path, expanding ~ to full path
            att_path = att.path.replace("~", str(Path.home())) if att.path else att.filename or "unknown"
            attachment_parts.append(f"[{att_type}:{att_path}]")
        attachment_str = " ".join(attachment_parts)
        if text:
            text = f"{attachment_str} {text}"
        else:
            text = attachment_str
    elif msg.has_attachments:
        # Fallback if we don't have attachment details
        if text:
            text = f"[attachment] {text}"
        else:
            text = "[attachment]"
    elif not text:
        text = "(no text)"
    
    if msg.transcription:
        text = f"[audio] {msg.transcription}"

    reactions = format_reactions_verbose(msg) if verbose else format_reactions_compact(msg)

    # Convert UTC to local time for display
    # Naive datetimes from the Messages database are in UTC
    if msg.date.tzinfo is None:
        utc_dt = msg.date.replace(tzinfo=timezone.utc)
    else:
        utc_dt = msg.date
    local_dt = utc_dt.astimezone()  # Convert to local timezone
    # Format time as 12-hour with am/pm (e.g., "1:12pm")
    time_str = local_dt.strftime("%-I:%M%p").lower()
    
    line = f"{sender} ({time_str}): {text}"
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


def format_date_header(dt: datetime) -> str:
    """Format a date header like [July 3, 2025].
    
    Uses local timezone for display.
    Naive datetimes from the database are treated as UTC.
    """
    if dt.tzinfo is None:
        utc_dt = dt.replace(tzinfo=timezone.utc)
    else:
        utc_dt = dt
    local_dt = utc_dt.astimezone()  # Convert to local timezone
    return f"[{local_dt.strftime('%B %-d, %Y')}]"


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
        click.echo(json.dumps([message_to_dict(m, db) for m in results], default=json_serializer, indent=2))
    else:
        current_date = None
        for msg in results:
            msg_date = msg.date.date()
            if msg_date != current_date:
                if current_date is not None:
                    click.echo()  # Blank line before new date header
                click.echo(format_date_header(msg.date))
                click.echo()  # Blank line after date header
                current_date = msg_date
            # Fetch attachments if message has them
            msg_attachments = None
            if msg.has_attachments:
                msg_attachments = list(db.attachments(message_id=msg.id))
            click.echo(format_message(msg, verbose=verbose, attachments=msg_attachments))


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
        click.echo(json.dumps(message_to_dict(msg, db), default=json_serializer, indent=2))
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
        click.echo(json.dumps([message_to_dict(m, db) for m in results], default=json_serializer, indent=2))
    else:
        for msg in results:
            # Fetch attachments if message has them
            msg_attachments = None
            if msg.has_attachments:
                msg_attachments = list(db.attachments(message_id=msg.id))
            click.echo(format_message(msg, verbose=verbose, attachments=msg_attachments))


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
