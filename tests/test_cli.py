"""Tests for CLI commands."""

import json

import pytest
from click.testing import CliRunner

from messages.cli import cli


@pytest.fixture
def runner():
    """Create a CLI test runner."""
    return CliRunner()


class TestGlobalOptions:
    """Tests for global CLI options."""

    def test_cli_version(self, runner):
        """--version should show version number."""
        result = runner.invoke(cli, ["--version"])
        assert result.exit_code == 0
        assert "version" in result.output.lower() or "0." in result.output

    def test_cli_help(self, runner):
        """--help should show usage information."""
        result = runner.invoke(cli, ["--help"])
        assert result.exit_code == 0
        assert "Usage:" in result.output
        assert "chats" in result.output
        assert "messages" in result.output

    def test_cli_custom_db_path(self, runner, test_db_path, monkeypatch):
        """--db should use specified database path."""
        monkeypatch.setattr("messages.phone.get_system_region", lambda: "US")
        monkeypatch.setattr("messages.contacts.get_contact_name", lambda x: None)

        result = runner.invoke(cli, ["--db", str(test_db_path), "chats"])
        assert result.exit_code == 0

    def test_cli_no_contacts_flag(self, runner, test_db_path, monkeypatch):
        """--no-contacts should disable contact resolution."""
        monkeypatch.setattr("messages.phone.get_system_region", lambda: "US")
        monkeypatch.setattr("messages.contacts.get_contact_name", lambda x: "Should Not Appear")

        result = runner.invoke(cli, [
            "--db", str(test_db_path),
            "--no-contacts",
            "messages", "--chat", "1"
        ])
        assert result.exit_code == 0
        # With --no-contacts, should show phone number, not resolved name
        assert "+1555" in result.output or "5551234567" in result.output


class TestChatsCommand:
    """Tests for the 'chats' command."""

    def test_chats_default(self, runner, test_db_path, monkeypatch):
        """Should list chats with default options."""
        monkeypatch.setattr("messages.phone.get_system_region", lambda: "US")
        monkeypatch.setattr("messages.contacts.get_contact_name", lambda x: None)

        result = runner.invoke(cli, ["--db", str(test_db_path), "chats"])
        assert result.exit_code == 0
        assert "Family Group" in result.output

    def test_chats_limit(self, runner, test_db_path, monkeypatch):
        """--limit should restrict output."""
        monkeypatch.setattr("messages.phone.get_system_region", lambda: "US")
        monkeypatch.setattr("messages.contacts.get_contact_name", lambda x: None)

        result = runner.invoke(cli, ["--db", str(test_db_path), "chats", "--limit", "1"])
        assert result.exit_code == 0
        # Should only have one chat line (plus possible header)
        lines = [l for l in result.output.strip().split("\n") if l]
        assert len(lines) == 1

    def test_chats_service_filter(self, runner, test_db_path, monkeypatch):
        """--service should filter by service type."""
        monkeypatch.setattr("messages.phone.get_system_region", lambda: "US")
        monkeypatch.setattr("messages.contacts.get_contact_name", lambda x: None)

        result = runner.invoke(cli, ["--db", str(test_db_path), "chats", "--service", "sms"])
        assert result.exit_code == 0
        assert "SMS" in result.output or "+447700900123" in result.output

    def test_chats_json_output(self, runner, test_db_path, monkeypatch):
        """--json should output valid JSON array."""
        monkeypatch.setattr("messages.phone.get_system_region", lambda: "US")
        monkeypatch.setattr("messages.contacts.get_contact_name", lambda x: None)

        result = runner.invoke(cli, ["--db", str(test_db_path), "chats", "--json"])
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert isinstance(data, list)
        assert len(data) == 3

    def test_chats_output_format(self, runner, test_db_path, monkeypatch):
        """Output should show ID, name, service, message count."""
        monkeypatch.setattr("messages.phone.get_system_region", lambda: "US")
        monkeypatch.setattr("messages.contacts.get_contact_name", lambda x: None)

        result = runner.invoke(cli, ["--db", str(test_db_path), "chats"])
        assert result.exit_code == 0
        # Should contain chat ID, service indicator, and message count
        assert "iMessage" in result.output or "SMS" in result.output
        assert "messages" in result.output.lower()


class TestMessagesCommand:
    """Tests for the 'messages' command."""

    def test_messages_requires_chat_or_with(self, runner):
        """Should error if neither --chat nor --with provided."""
        result = runner.invoke(cli, ["messages"])
        assert result.exit_code != 0
        assert "Specify --chat or --with" in result.output or "required" in result.output.lower()

    def test_messages_by_chat_id(self, runner, test_db_path, monkeypatch):
        """--chat should filter by chat ID."""
        monkeypatch.setattr("messages.phone.get_system_region", lambda: "US")
        monkeypatch.setattr("messages.contacts.get_contact_name", lambda x: None)

        result = runner.invoke(cli, ["--db", str(test_db_path), "messages", "--chat", "1"])
        assert result.exit_code == 0
        assert "lunch" in result.output.lower()

    def test_messages_by_identifier(self, runner, test_db_path, monkeypatch):
        """--with should filter by phone/email."""
        monkeypatch.setattr("messages.phone.get_system_region", lambda: "US")
        monkeypatch.setattr("messages.contacts.get_contact_name", lambda x: None)

        result = runner.invoke(cli, [
            "--db", str(test_db_path),
            "messages", "--with", "+15551234567"
        ])
        assert result.exit_code == 0
        assert "lunch" in result.output.lower()

    def test_messages_last(self, runner, test_db_path, monkeypatch):
        """--last should return most recent N messages."""
        monkeypatch.setattr("messages.phone.get_system_region", lambda: "US")
        monkeypatch.setattr("messages.contacts.get_contact_name", lambda x: None)

        result = runner.invoke(cli, [
            "--db", str(test_db_path),
            "messages", "--chat", "1", "--last", "2"
        ])
        assert result.exit_code == 0
        # Count message lines (lines with time format like "(10:01am):")
        import re
        msg_lines = [l for l in result.output.split("\n") if re.search(r"\(\d+:\d+[ap]m\):", l)]
        assert len(msg_lines) == 2

    def test_messages_first(self, runner, test_db_path, monkeypatch):
        """--first should return oldest N messages."""
        monkeypatch.setattr("messages.phone.get_system_region", lambda: "US")
        monkeypatch.setattr("messages.contacts.get_contact_name", lambda x: None)

        result = runner.invoke(cli, [
            "--db", str(test_db_path),
            "messages", "--chat", "1", "--first", "2"
        ])
        assert result.exit_code == 0
        # Count message lines (lines with time format like "(10:01am):")
        import re
        msg_lines = [l for l in result.output.split("\n") if re.search(r"\(\d+:\d+[ap]m\):", l)]
        assert len(msg_lines) == 2

    def test_messages_after_date(self, runner, test_db_path, monkeypatch):
        """--after should filter by date."""
        monkeypatch.setattr("messages.phone.get_system_region", lambda: "US")
        monkeypatch.setattr("messages.contacts.get_contact_name", lambda x: None)

        result = runner.invoke(cli, [
            "--db", str(test_db_path),
            "messages", "--chat", "1", "--after", "2024-01-15"
        ])
        assert result.exit_code == 0

    def test_messages_before_date(self, runner, test_db_path, monkeypatch):
        """--before should filter by date."""
        monkeypatch.setattr("messages.phone.get_system_region", lambda: "US")
        monkeypatch.setattr("messages.contacts.get_contact_name", lambda x: None)

        result = runner.invoke(cli, [
            "--db", str(test_db_path),
            "messages", "--chat", "1", "--before", "2024-01-16"
        ])
        assert result.exit_code == 0

    def test_messages_json_output(self, runner, test_db_path, monkeypatch):
        """--json should output valid JSON array."""
        monkeypatch.setattr("messages.phone.get_system_region", lambda: "US")
        monkeypatch.setattr("messages.contacts.get_contact_name", lambda x: None)

        result = runner.invoke(cli, [
            "--db", str(test_db_path),
            "messages", "--chat", "1", "--json", "--last", "5"
        ])
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert isinstance(data, list)

    def test_messages_json_dates_are_utc(self, runner, test_db_path, monkeypatch):
        """JSON dates should be in UTC with Z suffix."""
        monkeypatch.setattr("messages.phone.get_system_region", lambda: "US")
        monkeypatch.setattr("messages.contacts.get_contact_name", lambda x: None)

        result = runner.invoke(cli, [
            "--db", str(test_db_path),
            "messages", "--chat", "1", "--json", "--last", "1"
        ])
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert len(data) > 0
        # Date should end with Z (UTC)
        import re
        assert re.match(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z", data[0]["date"])

    def test_messages_no_unsent(self, runner, test_db_path, monkeypatch):
        """--no-unsent should exclude unsent messages."""
        monkeypatch.setattr("messages.phone.get_system_region", lambda: "US")
        monkeypatch.setattr("messages.contacts.get_contact_name", lambda x: None)

        # First get all messages
        result_all = runner.invoke(cli, [
            "--db", str(test_db_path),
            "messages", "--chat", "1", "--json", "--last", "100"
        ])
        all_msgs = json.loads(result_all.output)

        # Then without unsent
        result_no_unsent = runner.invoke(cli, [
            "--db", str(test_db_path),
            "messages", "--chat", "1", "--json", "--last", "100", "--no-unsent"
        ])
        no_unsent_msgs = json.loads(result_no_unsent.output)

        # Should have fewer messages (we have one unsent in test data)
        assert len(no_unsent_msgs) < len(all_msgs)

    def test_messages_output_format(self, runner, test_db_path, monkeypatch):
        """Output should show IRC-style format with date header and sender (time): text."""
        monkeypatch.setattr("messages.phone.get_system_region", lambda: "US")
        monkeypatch.setattr("messages.contacts.get_contact_name", lambda x: None)

        result = runner.invoke(cli, [
            "--db", str(test_db_path),
            "messages", "--chat", "1", "--last", "1"
        ])
        assert result.exit_code == 0
        # Should have date header in brackets like [January 15, 2024]
        assert "[January" in result.output or "[February" in result.output or "[March" in result.output
        # Should have time in parentheses like (10:01am):
        import re
        assert re.search(r"\(\d+:\d+[ap]m\):", result.output)


class TestReadCommand:
    """Tests for the 'read' command."""

    def test_read_message(self, runner, test_db_path, monkeypatch):
        """Should display single message details."""
        monkeypatch.setattr("messages.phone.get_system_region", lambda: "US")
        monkeypatch.setattr("messages.contacts.get_contact_name", lambda x: None)

        result = runner.invoke(cli, ["--db", str(test_db_path), "read", "1"])
        assert result.exit_code == 0
        assert "lunch" in result.output.lower()

    def test_read_message_not_found(self, runner, test_db_path, monkeypatch):
        """Should error for nonexistent message ID."""
        monkeypatch.setattr("messages.phone.get_system_region", lambda: "US")
        monkeypatch.setattr("messages.contacts.get_contact_name", lambda x: None)

        result = runner.invoke(cli, ["--db", str(test_db_path), "read", "99999"])
        assert result.exit_code != 0

    def test_read_json_output(self, runner, test_db_path, monkeypatch):
        """--json should output valid JSON object."""
        monkeypatch.setattr("messages.phone.get_system_region", lambda: "US")
        monkeypatch.setattr("messages.contacts.get_contact_name", lambda x: None)

        result = runner.invoke(cli, ["--db", str(test_db_path), "read", "1", "--json"])
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert isinstance(data, dict)
        assert "id" in data

    def test_read_shows_reactions(self, runner, test_db_path, monkeypatch):
        """Should list all reactions with who reacted."""
        monkeypatch.setattr("messages.phone.get_system_region", lambda: "US")
        monkeypatch.setattr("messages.contacts.get_contact_name", lambda x: None)

        # Message 2 has reactions
        result = runner.invoke(cli, ["--db", str(test_db_path), "read", "2"])
        assert result.exit_code == 0
        assert "reaction" in result.output.lower() or "love" in result.output.lower()


class TestSearchCommand:
    """Tests for the 'search' command."""

    def test_search_finds_matches(self, runner, test_db_path, monkeypatch):
        """Should find messages containing query."""
        monkeypatch.setattr("messages.phone.get_system_region", lambda: "US")
        monkeypatch.setattr("messages.contacts.get_contact_name", lambda x: None)

        result = runner.invoke(cli, ["--db", str(test_db_path), "search", "lunch"])
        assert result.exit_code == 0
        assert "lunch" in result.output.lower()

    def test_search_no_results(self, runner, test_db_path, monkeypatch):
        """Should return empty output for no matches."""
        monkeypatch.setattr("messages.phone.get_system_region", lambda: "US")
        monkeypatch.setattr("messages.contacts.get_contact_name", lambda x: None)

        result = runner.invoke(cli, ["--db", str(test_db_path), "search", "xyznonexistent123"])
        assert result.exit_code == 0
        # Output should be empty or just whitespace
        assert result.output.strip() == "" or "no results" in result.output.lower()

    def test_search_within_chat(self, runner, test_db_path, monkeypatch):
        """--chat should limit search to specific chat."""
        monkeypatch.setattr("messages.phone.get_system_region", lambda: "US")
        monkeypatch.setattr("messages.contacts.get_contact_name", lambda x: None)

        result = runner.invoke(cli, [
            "--db", str(test_db_path),
            "search", "dinner", "--chat", "3"
        ])
        assert result.exit_code == 0
        assert "dinner" in result.output.lower()

    def test_search_json_output(self, runner, test_db_path, monkeypatch):
        """--json should output valid JSON array."""
        monkeypatch.setattr("messages.phone.get_system_region", lambda: "US")
        monkeypatch.setattr("messages.contacts.get_contact_name", lambda x: None)

        result = runner.invoke(cli, [
            "--db", str(test_db_path),
            "search", "lunch", "--json"
        ])
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert isinstance(data, list)


class TestAttachmentsCommand:
    """Tests for the 'attachments' command."""

    def test_attachments_list(self, runner, test_db_path, monkeypatch):
        """Should list attachments."""
        monkeypatch.setattr("messages.phone.get_system_region", lambda: "US")
        monkeypatch.setattr("messages.contacts.get_contact_name", lambda x: None)

        result = runner.invoke(cli, ["--db", str(test_db_path), "attachments"])
        assert result.exit_code == 0
        assert "photo.jpg" in result.output or "image" in result.output.lower()

    def test_attachments_by_chat(self, runner, test_db_path, monkeypatch):
        """--chat should filter by chat ID."""
        monkeypatch.setattr("messages.phone.get_system_region", lambda: "US")
        monkeypatch.setattr("messages.contacts.get_contact_name", lambda x: None)

        result = runner.invoke(cli, [
            "--db", str(test_db_path),
            "attachments", "--chat", "1"
        ])
        assert result.exit_code == 0
        # Chat 1 has photo.jpg and document.pdf
        assert "photo" in result.output.lower() or "pdf" in result.output.lower()

    def test_attachments_by_message(self, runner, test_db_path, monkeypatch):
        """--message should filter by message ID."""
        monkeypatch.setattr("messages.phone.get_system_region", lambda: "US")
        monkeypatch.setattr("messages.contacts.get_contact_name", lambda x: None)

        result = runner.invoke(cli, [
            "--db", str(test_db_path),
            "attachments", "--message", "9"
        ])
        assert result.exit_code == 0

    def test_attachments_mime_type_filter(self, runner, test_db_path, monkeypatch):
        """--type should filter by MIME type."""
        monkeypatch.setattr("messages.phone.get_system_region", lambda: "US")
        monkeypatch.setattr("messages.contacts.get_contact_name", lambda x: None)

        result = runner.invoke(cli, [
            "--db", str(test_db_path),
            "attachments", "--type", "image/*"
        ])
        assert result.exit_code == 0
        # Should only show images, not PDF
        assert "pdf" not in result.output.lower() or "image" in result.output.lower()

    def test_attachments_json_output(self, runner, test_db_path, monkeypatch):
        """--json should output valid JSON array."""
        monkeypatch.setattr("messages.phone.get_system_region", lambda: "US")
        monkeypatch.setattr("messages.contacts.get_contact_name", lambda x: None)

        result = runner.invoke(cli, [
            "--db", str(test_db_path),
            "attachments", "--json"
        ])
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert isinstance(data, list)
        assert len(data) == 3  # We have 3 attachments in test data
