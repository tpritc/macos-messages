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
from messages.contacts import get_all_contacts, search_contacts


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


@click.group(invoke_without_command=True)
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
@click.option("--chat", "-c", "chat_id", help="Chat ID or display name")
@click.option("--with", "-w", "with_contact", help="Contact name (exact match)")
@click.option("--search", "-s", "search_query", help="Search messages for text")
@click.option(
    "--search-mode", "-m",
    type=click.Choice(["basic", "keyword", "stemmed", "hybrid"], case_sensitive=False),
    default="basic",
    help="Search mode: basic (SQL LIKE), keyword (FTS), stemmed, or hybrid (all methods)",
)
@click.option("--since", type=click.DateTime(), help="After date (YYYY-MM-DD)")
@click.option("--before", type=click.DateTime(), help="Before date (YYYY-MM-DD)")
@click.option("--first", "-f", "first_n", type=int, help="Show first N messages (oldest)")
@click.option("--last", "-l", "last_n", type=int, default=50, help="Show last N messages (newest, default: 50)")
@click.option("--with-attachments", is_flag=True, help="Only show messages with attachments")
@click.option("--json", "as_json", is_flag=True, help="Output as JSON")
@click.pass_context
def cli(
    ctx: click.Context,
    db: str | None,
    no_contacts: bool,
    chat_id: str | None,
    with_contact: str | None,
    search_query: str | None,
    search_mode: str,
    since: datetime | None,
    before: datetime | None,
    first_n: int | None,
    last_n: int,
    with_attachments: bool,
    as_json: bool,
) -> None:
    """Read messages from macOS Messages.app.

    Requires Full Disk Access permission for Terminal.

    \b
    Examples:
      messages --chat 42              List messages from chat ID 42
      messages --chat "Mom"           List messages from chat named "Mom"
      messages --with "John Doe"      List messages with contact John Doe
      messages --search "dinner"      Search all messages for "dinner"
      messages --search "meeting" -m hybrid  Search with all methods combined
    """
    ctx.ensure_object(dict)
    
    # Check for mutually exclusive options
    if chat_id and with_contact:
        click.echo("Error: Cannot specify both --chat and --with", err=True)
        sys.exit(1)
    
    # If a subcommand is being invoked, just set up the DB
    if ctx.invoked_subcommand is not None:
        try:
            ctx.obj["db"] = messages.get_db(db)
            ctx.obj["db"].resolve_contacts = not no_contacts
        except PermissionError as e:
            click.echo(str(e), err=True)
            sys.exit(1)
        except FileNotFoundError as e:
            click.echo(f"Error: {e}", err=True)
            sys.exit(1)
        return
    
    # If no message options provided, show help
    if not chat_id and not with_contact and not search_query:
        click.echo(ctx.get_help())
        return
    
    # Initialize DB for message listing
    try:
        db_instance = messages.get_db(db)
        db_instance.resolve_contacts = not no_contacts
        ctx.obj["db"] = db_instance
    except PermissionError as e:
        click.echo(str(e), err=True)
        sys.exit(1)
    except FileNotFoundError as e:
        click.echo(f"Error: {e}", err=True)
        sys.exit(1)
    
    # Handle message listing
    _list_messages(
        ctx,
        chat_id=chat_id,
        with_contact=with_contact,
        search_query=search_query,
        search_mode=search_mode,
        since=since,
        before=before,
        first_n=first_n,
        last_n=last_n,
        with_attachments=with_attachments,
        as_json=as_json,
    )


def _resolve_chat_id(db: "messages.MessagesDB", chat_id_or_name: str) -> int:
    """Resolve a chat ID or display name to a numeric chat ID.
    
    Args:
        db: The database instance
        chat_id_or_name: Either a numeric ID or a display name
        
    Returns:
        The numeric chat ID
        
    Raises:
        click.ClickException: If chat not found or multiple matches
    """
    # Try to parse as integer first
    try:
        return int(chat_id_or_name)
    except ValueError:
        pass
    
    # Search for chat by display name
    all_chats = list(db.chats(limit=1000))
    matches = [
        c for c in all_chats
        if c.display_name and chat_id_or_name.lower() in c.display_name.lower()
    ]
    
    if not matches:
        raise click.ClickException(f"Chat '{chat_id_or_name}' not found")
    
    # Check for exact match first
    exact_matches = [c for c in matches if c.display_name and c.display_name.lower() == chat_id_or_name.lower()]
    if len(exact_matches) == 1:
        return exact_matches[0].id
    
    if len(matches) > 1:
        match_list = "\n".join(f"  {c.id}: {c.display_name}" for c in matches[:10])
        raise click.ClickException(
            f"Multiple chats match '{chat_id_or_name}':\n{match_list}\n\nUse the chat ID instead."
        )
    
    return matches[0].id


def _resolve_contact_chat_ids(db: "messages.MessagesDB", contact_name: str) -> list[int]:
    """Resolve a contact name to all matching chat IDs.
    
    A contact may have multiple conversations (e.g., different phone numbers,
    iMessage vs SMS). This returns all chat IDs for that contact.
    
    Args:
        db: The database instance
        contact_name: The exact contact name to find
        
    Returns:
        List of chat IDs for conversations with that contact (may be empty)
    """
    # Find all chats where the display name matches the contact name
    all_chats = list(db.chats(limit=1000))
    matching_ids = []
    for chat in all_chats:
        if chat.display_name and chat.display_name.lower() == contact_name.lower():
            matching_ids.append(chat.id)
    return matching_ids


def _do_search(
    db: "messages.MessagesDB",
    query: str,
    *,
    search_mode: str,
    chat_id: int | None,
    chat_ids: list[int] | None,
    after: datetime | None,
    before: datetime | None,
    limit: int,
) -> list[Message]:
    """Perform search using the specified search mode.

    Args:
        db: MessagesDB instance
        query: Search query string
        search_mode: Search mode (basic, keyword, stemmed, hybrid)
        chat_id: Single chat ID filter
        chat_ids: Multiple chat IDs filter
        after: After date filter
        before: Before date filter
        limit: Maximum results

    Returns:
        List of Message objects matching the query
    """
    if search_mode == "basic":
        # Use the original SQL LIKE search
        return list(
            db.search(
                query,
                chat_id=chat_id,
                chat_ids=chat_ids,
                after=after,
                before=before,
                limit=limit,
            )
        )

    # Use enhanced search
    from messages.hybrid_search import HybridSearch, SearchMode

    hybrid = HybridSearch(db)

    # Map CLI mode names to SearchMode enum
    mode_map = {
        "keyword": SearchMode.KEYWORD,
        "stemmed": SearchMode.STEMMED,
        "hybrid": SearchMode.HYBRID,
    }
    mode = mode_map.get(search_mode, SearchMode.HYBRID)

    # Search and convert results to Message objects
    results = []
    for result in hybrid.search(
        query,
        mode=mode,
        chat_id=chat_id,
        chat_ids=chat_ids,
        after=after,
        before=before,
        limit=limit,
    ):
        try:
            msg = db.message(result.message_id)
            results.append(msg)
        except LookupError:
            # Message may have been deleted
            continue

    return results


def _list_messages(
    ctx: click.Context,
    chat_id: str | None,
    with_contact: str | None,
    search_query: str | None,
    search_mode: str,
    since: datetime | None,
    before: datetime | None,
    first_n: int | None,
    last_n: int,
    with_attachments: bool,
    as_json: bool,
) -> None:
    """List or search messages based on provided options."""
    db = ctx.obj["db"]

    resolved_chat_id = None
    resolved_chat_ids = None

    # Resolve chat ID from --chat option
    if chat_id:
        try:
            resolved_chat_id = _resolve_chat_id(db, chat_id)
        except click.ClickException as e:
            click.echo(f"Error: {e.message}", err=True)
            sys.exit(1)

    # Resolve chat IDs from --with option (may return multiple chats for same contact)
    if with_contact:
        resolved_chat_ids = _resolve_contact_chat_ids(db, with_contact)
        if not resolved_chat_ids:
            # No conversation found with this contact - return empty
            if as_json:
                click.echo("[]")
            return

    # Determine limit and direction
    # If --first is specified, use it (oldest first)
    # Otherwise use --last (newest first, the default)
    if first_n is not None:
        limit = first_n
        reverse = False
    else:
        limit = last_n
        reverse = True

    # Fetch more if filtering by attachments, since we filter after
    fetch_limit = limit * 10 if with_attachments else limit

    if search_query:
        results = _do_search(
            db,
            search_query,
            search_mode=search_mode,
            chat_id=resolved_chat_id,
            chat_ids=resolved_chat_ids,
            after=since,
            before=before,
            limit=fetch_limit,
        )
    else:
        if resolved_chat_id is None and resolved_chat_ids is None:
            click.echo("Error: Specify --chat or --with to list messages", err=True)
            sys.exit(1)
        results = list(
            db.messages(
                chat_id=resolved_chat_id,
                chat_ids=resolved_chat_ids,
                after=since,
                before=before,
                limit=fetch_limit,
                reverse=reverse,
            )
        )
        # When showing last N (reverse), re-reverse so messages appear in chronological order
        if reverse:
            results = list(reversed(results))
    
    # Filter to only messages with attachments if requested
    if with_attachments:
        results = [m for m in results if m.has_attachments][:limit]
    
    if as_json:
        click.echo(json.dumps([message_to_dict(m, db) for m in results], default=json_serializer, indent=2))
    else:
        current_date = None
        for msg in results:
            msg_date = msg.date.date()
            if msg_date != current_date:
                if current_date is not None:
                    click.echo()
                click.echo(format_date_header(msg.date))
                click.echo()
                current_date = msg_date
            msg_attachments = list(db.attachments(message_id=msg.id)) if msg.has_attachments else None
            click.echo(format_message(msg, verbose=False, attachments=msg_attachments))


@cli.command()
@click.option("--search", "-s", "search_query", help="Filter chats by display name")
@click.option("--service", type=click.Choice(["imessage", "sms", "rcs"], case_sensitive=False))
@click.option("--limit", "-n", type=int, default=20)
@click.option("--json", "as_json", is_flag=True, help="Output as JSON")
@click.pass_context
def chats(ctx: click.Context, search_query: str | None, service: str | None, limit: int, as_json: bool) -> None:
    """List conversations."""
    db = ctx.obj["db"]

    # Convert service to the format used in the database
    service_map = {"imessage": "iMessage", "sms": "SMS", "rcs": "RCS"}
    db_service = service_map.get(service.lower()) if service else None

    results = list(db.chats(service=db_service, limit=limit if not search_query else 1000))
    
    # Filter by display name if search provided
    if search_query:
        query_lower = search_query.lower()
        results = [
            c for c in results
            if c.display_name and query_lower in c.display_name.lower()
        ][:limit]

    if as_json:
        click.echo(json.dumps([asdict(c) for c in results], default=json_serializer, indent=2))
    else:
        for chat in results:
            name = chat.display_name or chat.identifier
            click.echo(f"{chat.id} {name} ({chat.service}) - {chat.message_count} messages")


@cli.command()
@click.option("--search", "-s", "search_query", help="Filter contacts by name")
@click.option("--limit", "-n", type=int, default=20)
@click.option("--json", "as_json", is_flag=True, help="Output as JSON")
@click.pass_context
def contacts(ctx: click.Context, search_query: str | None, limit: int, as_json: bool) -> None:
    """List contacts from macOS Contacts.app."""
    if search_query:
        results = search_contacts(search_query)[:limit]
    else:
        results = get_all_contacts()[:limit]

    if as_json:
        click.echo(json.dumps([asdict(c) for c in results], default=json_serializer, indent=2))
    else:
        for contact in results:
            if contact.display_name:
                click.echo(contact.display_name)


@cli.group()
@click.pass_context
def index(ctx: click.Context) -> None:
    """Manage search indexes for enhanced search features.

    The search index enables advanced search capabilities including:
    - Fast full-text search with FTS5
    - Stemmed search for word variants
    - Semantic search for meaning-based queries (requires extra install)

    \b
    Build the index before using enhanced search modes:
      messages index build

    \b
    Check index status:
      messages index stats
    """
    pass


@index.command()
@click.option("--semantic", is_flag=True, help="Also build semantic search index (requires sentence-transformers)")
@click.option("--rebuild", is_flag=True, help="Rebuild indexes from scratch")
@click.pass_context
def build(ctx: click.Context, semantic: bool, rebuild: bool) -> None:
    """Build or update the search index.

    By default, only builds the full-text and stemmed search indexes.
    Use --semantic to also build the semantic search index (requires
    sentence-transformers to be installed).

    \b
    Examples:
      messages index build              Build FTS and stemmed indexes
      messages index build --semantic   Also build semantic index
      messages index build --rebuild    Rebuild from scratch
    """
    from messages.hybrid_search import HybridSearch

    db = ctx.obj["db"]
    hybrid = HybridSearch(db)

    def progress_callback(stage: str, indexed: int, total: int | None) -> None:
        if total:
            click.echo(f"  {stage}: {indexed}/{total} messages indexed", nl=False)
            click.echo("\r", nl=False)
        else:
            click.echo(f"Building {stage} index...")

    click.echo("Building search indexes...")

    try:
        stats = hybrid.build_indexes(
            include_semantic=semantic,
            full_rebuild=rebuild,
            progress_callback=progress_callback,
        )

        click.echo()
        click.echo(f"FTS index: {stats['fts_indexed']} messages indexed")

        if semantic:
            if stats.get("semantic_available", True):
                click.echo(f"Semantic index: {stats.get('semantic_indexed', 0)} messages indexed")
            else:
                click.echo("Semantic index: sentence-transformers not installed")
                click.echo("  Install with: pip install macos-messages[semantic]")

        click.echo("Done!")

    except Exception as e:
        click.echo(f"Error building index: {e}", err=True)
        sys.exit(1)


@index.command()
@click.option("--json", "as_json", is_flag=True, help="Output as JSON")
@click.pass_context
def stats(ctx: click.Context, as_json: bool) -> None:
    """Show search index statistics.

    Displays information about the search indexes including:
    - Number of indexed messages
    - Index file sizes
    - Stemmer and embedding model status
    """
    from messages.hybrid_search import HybridSearch

    db = ctx.obj["db"]
    hybrid = HybridSearch(db)

    index_stats = hybrid.get_stats()

    if as_json:
        click.echo(json.dumps(index_stats, default=json_serializer, indent=2))
    else:
        # FTS stats
        fts = index_stats.get("fts", {})
        click.echo("Full-text Search Index:")
        click.echo(f"  Indexed messages: {fts.get('indexed_messages', 0)}")
        if fts.get("index_size_bytes"):
            size_mb = fts["index_size_bytes"] / (1024 * 1024)
            click.echo(f"  Index size: {size_mb:.2f} MB")

        stemmer = fts.get("stemmer", {})
        if stemmer.get("available"):
            click.echo(f"  Stemmer: {stemmer.get('algorithm', 'unknown')}")
        else:
            click.echo("  Stemmer: not available")

        click.echo()

        # Semantic stats
        semantic = index_stats.get("semantic", {})
        click.echo("Semantic Search Index:")
        if semantic.get("available", semantic.get("model_available")):
            click.echo(f"  Indexed messages: {semantic.get('indexed_messages', 0)}")
            if semantic.get("embedding_dimension"):
                click.echo(f"  Embedding dimension: {semantic['embedding_dimension']}")
            if semantic.get("model_name"):
                click.echo(f"  Model: {semantic['model_name']}")
            if semantic.get("index_size_bytes"):
                size_mb = semantic["index_size_bytes"] / (1024 * 1024)
                click.echo(f"  Index size: {size_mb:.2f} MB")
        else:
            click.echo("  Not available (sentence-transformers not installed)")
            click.echo("  Install with: pip install macos-messages[semantic]")
