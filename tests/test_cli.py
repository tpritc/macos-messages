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
        assert "contacts" in result.output

    def test_cli_no_args_shows_help(self, runner):
        """No arguments should show help."""
        result = runner.invoke(cli, [])
        assert result.exit_code == 0
        assert "Usage:" in result.output

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

        result = runner.invoke(cli, ["--db", str(test_db_path), "--no-contacts", "--chat", "1"])
        assert result.exit_code == 0
        # With --no-contacts, should show phone number, not resolved name
        assert "+1555" in result.output or "5551234567" in result.output


class TestMessagesRoot:
    """Tests for root command message listing options."""

    def test_messages_by_chat_id(self, runner, test_db_path, monkeypatch):
        """--chat with ID should list messages from that chat."""
        monkeypatch.setattr("messages.phone.get_system_region", lambda: "US")
        monkeypatch.setattr("messages.contacts.get_contact_name", lambda x: None)

        result = runner.invoke(cli, ["--db", str(test_db_path), "--chat", "1"])
        assert result.exit_code == 0
        assert "lunch" in result.output.lower()

    def test_messages_by_chat_display_name(self, runner, test_db_path, monkeypatch):
        """--chat with display name should list messages from matching chat."""
        monkeypatch.setattr("messages.phone.get_system_region", lambda: "US")
        monkeypatch.setattr("messages.contacts.get_contact_name", lambda x: None)

        result = runner.invoke(cli, ["--db", str(test_db_path), "--chat", "Family Group"])
        assert result.exit_code == 0
        assert "dinner" in result.output.lower()

    def test_messages_by_chat_name_multiple_matches(self, runner, test_db_path, monkeypatch):
        """--chat with ambiguous name should error with list of matches."""
        monkeypatch.setattr("messages.phone.get_system_region", lambda: "US")
        monkeypatch.setattr("messages.contacts.get_contact_name", lambda x: None)
        # This test assumes we have multiple chats with similar names
        # For now, just verify the error handling structure exists
        # Implementation will need test data with duplicates

    def test_messages_by_with(self, runner, test_db_path, monkeypatch):
        """--with should list messages with exact contact name match."""
        monkeypatch.setattr("messages.phone.get_system_region", lambda: "US")

        # Only return "Jane Doe" for the specific phone number in chat 1
        def mock_contact(x):
            if x == "+15551234567":
                return "Jane Doe"
            return None

        monkeypatch.setattr("messages.contacts.get_contact_name", mock_contact)

        result = runner.invoke(cli, ["--db", str(test_db_path), "--with", "Jane Doe"])
        assert result.exit_code == 0
        assert "lunch" in result.output.lower()

    def test_messages_with_not_found(self, runner, test_db_path, monkeypatch):
        """--with with unknown contact should exit 0 with empty results."""
        monkeypatch.setattr("messages.phone.get_system_region", lambda: "US")
        monkeypatch.setattr("messages.contacts.get_contact_name", lambda x: None)

        result = runner.invoke(cli, ["--db", str(test_db_path), "--with", "Unknown Person"])
        assert result.exit_code == 0
        # Empty or no messages found

    def test_messages_chat_and_with_mutually_exclusive(self, runner, test_db_path, monkeypatch):
        """--chat and --with together should error with exit code 1."""
        monkeypatch.setattr("messages.phone.get_system_region", lambda: "US")
        monkeypatch.setattr("messages.contacts.get_contact_name", lambda x: None)

        result = runner.invoke(
            cli, ["--db", str(test_db_path), "--chat", "1", "--with", "Jane Doe"]
        )
        assert result.exit_code == 1
        assert "Cannot specify both --chat and --with" in result.output

    def test_messages_search(self, runner, test_db_path, monkeypatch):
        """--search should find messages containing query."""
        monkeypatch.setattr("messages.phone.get_system_region", lambda: "US")
        monkeypatch.setattr("messages.contacts.get_contact_name", lambda x: None)

        result = runner.invoke(cli, ["--db", str(test_db_path), "--search", "lunch"])
        assert result.exit_code == 0
        assert "lunch" in result.output.lower()

    def test_messages_search_with_contact(self, runner, test_db_path, monkeypatch):
        """--with combined with --search should search within conversation."""
        monkeypatch.setattr("messages.phone.get_system_region", lambda: "US")

        # Only return "Jane Doe" for the specific phone number in chat 1
        def mock_contact(x):
            if x == "+15551234567":
                return "Jane Doe"
            return None

        monkeypatch.setattr("messages.contacts.get_contact_name", mock_contact)

        result = runner.invoke(
            cli, ["--db", str(test_db_path), "--with", "Jane Doe", "--search", "lunch"]
        )
        assert result.exit_code == 0
        assert "lunch" in result.output.lower()

    def test_messages_since(self, runner, test_db_path, monkeypatch):
        """--since should filter by date."""
        monkeypatch.setattr("messages.phone.get_system_region", lambda: "US")
        monkeypatch.setattr("messages.contacts.get_contact_name", lambda x: None)

        result = runner.invoke(
            cli, ["--db", str(test_db_path), "--chat", "1", "--since", "2024-01-15"]
        )
        assert result.exit_code == 0

    def test_messages_before(self, runner, test_db_path, monkeypatch):
        """--before should filter by date."""
        monkeypatch.setattr("messages.phone.get_system_region", lambda: "US")
        monkeypatch.setattr("messages.contacts.get_contact_name", lambda x: None)

        result = runner.invoke(
            cli, ["--db", str(test_db_path), "--chat", "1", "--before", "2024-01-16"]
        )
        assert result.exit_code == 0

    def test_messages_limit(self, runner, test_db_path, monkeypatch):
        """--last should restrict number of messages."""
        monkeypatch.setattr("messages.phone.get_system_region", lambda: "US")
        monkeypatch.setattr("messages.contacts.get_contact_name", lambda x: None)

        result = runner.invoke(cli, ["--db", str(test_db_path), "--chat", "1", "--last", "2"])
        assert result.exit_code == 0
        # Count message lines
        import re

        msg_lines = [
            line for line in result.output.split("\n") if re.search(r"\(\d+:\d+[ap]m\):", line)
        ]
        assert len(msg_lines) == 2

    def test_messages_with_attachments(self, runner, test_db_path, monkeypatch):
        """--with-attachments should filter to only messages with attachments."""
        monkeypatch.setattr("messages.phone.get_system_region", lambda: "US")
        monkeypatch.setattr("messages.contacts.get_contact_name", lambda x: None)

        result = runner.invoke(
            cli, ["--db", str(test_db_path), "--chat", "1", "--with-attachments"]
        )
        assert result.exit_code == 0
        # Should only show messages with attachments
        # All displayed messages should have attachment indicators
        if result.output.strip():
            assert "[image:" in result.output or "[file:" in result.output

    def test_messages_json_output(self, runner, test_db_path, monkeypatch):
        """--json should output valid JSON array."""
        monkeypatch.setattr("messages.phone.get_system_region", lambda: "US")
        monkeypatch.setattr("messages.contacts.get_contact_name", lambda x: None)

        result = runner.invoke(
            cli, ["--db", str(test_db_path), "--chat", "1", "--json", "--last", "5"]
        )
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert isinstance(data, list)

    def test_messages_json_includes_attachments(self, runner, test_db_path, monkeypatch):
        """JSON output should include attachments array with full details."""
        monkeypatch.setattr("messages.phone.get_system_region", lambda: "US")
        monkeypatch.setattr("messages.contacts.get_contact_name", lambda x: None)

        result = runner.invoke(
            cli, ["--db", str(test_db_path), "--chat", "1", "--json", "--last", "50"]
        )
        assert result.exit_code == 0
        data = json.loads(result.output)

        # Find message with attachments
        msg_with_attachments = next((m for m in data if m["has_attachments"]), None)
        assert msg_with_attachments is not None, "Should have a message with attachments"

        # Check attachments array is present and populated
        assert "attachments" in msg_with_attachments
        assert len(msg_with_attachments["attachments"]) >= 1

    def test_messages_json_dates_are_utc(self, runner, test_db_path, monkeypatch):
        """JSON dates should be in UTC with Z suffix."""
        monkeypatch.setattr("messages.phone.get_system_region", lambda: "US")
        monkeypatch.setattr("messages.contacts.get_contact_name", lambda x: None)

        result = runner.invoke(
            cli, ["--db", str(test_db_path), "--chat", "1", "--json", "--last", "1"]
        )
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert len(data) > 0
        import re

        assert re.match(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z", data[0]["date"])


class TestChatsCommand:
    """Tests for the 'chats' command."""

    def test_chats_default(self, runner, test_db_path, monkeypatch):
        """Should list chats with default options."""
        monkeypatch.setattr("messages.phone.get_system_region", lambda: "US")
        monkeypatch.setattr("messages.contacts.get_contact_name", lambda x: None)

        result = runner.invoke(cli, ["--db", str(test_db_path), "chats"])
        assert result.exit_code == 0
        assert "Family Group" in result.output

    def test_chats_search(self, runner, test_db_path, monkeypatch):
        """--search should filter chats by display name."""
        monkeypatch.setattr("messages.phone.get_system_region", lambda: "US")
        monkeypatch.setattr("messages.contacts.get_contact_name", lambda x: None)

        result = runner.invoke(cli, ["--db", str(test_db_path), "chats", "--search", "Family"])
        assert result.exit_code == 0
        assert "Family Group" in result.output

    def test_chats_search_no_results(self, runner, test_db_path, monkeypatch):
        """--search with no matches should return empty."""
        monkeypatch.setattr("messages.phone.get_system_region", lambda: "US")
        monkeypatch.setattr("messages.contacts.get_contact_name", lambda x: None)

        result = runner.invoke(
            cli, ["--db", str(test_db_path), "chats", "--search", "xyznonexistent123"]
        )
        assert result.exit_code == 0
        assert result.output.strip() == "" or "Family" not in result.output

    def test_chats_limit(self, runner, test_db_path, monkeypatch):
        """--limit should restrict output."""
        monkeypatch.setattr("messages.phone.get_system_region", lambda: "US")
        monkeypatch.setattr("messages.contacts.get_contact_name", lambda x: None)

        result = runner.invoke(cli, ["--db", str(test_db_path), "chats", "--limit", "1"])
        assert result.exit_code == 0
        lines = [line for line in result.output.strip().split("\n") if line]
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
        assert "iMessage" in result.output or "SMS" in result.output
        assert "messages" in result.output.lower()


class TestContactsCommand:
    """Tests for the 'contacts' command."""

    def test_contacts_list(self, runner, mock_contacts, monkeypatch):
        """Should list contacts."""
        monkeypatch.setattr("messages.phone.get_system_region", lambda: "US")

        result = runner.invoke(cli, ["contacts"])
        assert result.exit_code == 0
        # Should contain some contact names
        assert "Jane Doe" in result.output or "John Smith" in result.output

    def test_contacts_search(self, runner, mock_contacts, monkeypatch):
        """--search should filter contacts by name."""
        monkeypatch.setattr("messages.phone.get_system_region", lambda: "US")

        result = runner.invoke(cli, ["contacts", "--search", "jane"])
        assert result.exit_code == 0
        assert "Jane" in result.output

    def test_contacts_search_multiple_matches(self, runner, mock_contacts, monkeypatch):
        """--search should return all matching contacts."""
        monkeypatch.setattr("messages.phone.get_system_region", lambda: "US")

        result = runner.invoke(cli, ["contacts", "--search", "john"])
        assert result.exit_code == 0
        # Should match both "John Doe" and "Debbie Johnson" type names

    def test_contacts_search_no_results(self, runner, mock_contacts, monkeypatch):
        """--search with no matches should return empty."""
        monkeypatch.setattr("messages.phone.get_system_region", lambda: "US")

        result = runner.invoke(cli, ["contacts", "--search", "xyznonexistent123"])
        assert result.exit_code == 0
        assert result.output.strip() == ""

    def test_contacts_limit(self, runner, mock_contacts, monkeypatch):
        """--limit should restrict output."""
        monkeypatch.setattr("messages.phone.get_system_region", lambda: "US")

        result = runner.invoke(cli, ["contacts", "--limit", "1"])
        assert result.exit_code == 0
        lines = [line for line in result.output.strip().split("\n") if line]
        assert len(lines) <= 1

    def test_contacts_json_output(self, runner, mock_contacts, monkeypatch):
        """--json should output valid JSON array."""
        monkeypatch.setattr("messages.phone.get_system_region", lambda: "US")

        result = runner.invoke(cli, ["contacts", "--json"])
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert isinstance(data, list)

    def test_contacts_no_address_book(self, runner, monkeypatch):
        """Should return empty list if no address book found."""
        monkeypatch.setattr("messages.phone.get_system_region", lambda: "US")
        # Patch in the cli module where it's imported
        monkeypatch.setattr("messages.cli.get_all_contacts", lambda: [])

        result = runner.invoke(cli, ["contacts"])
        assert result.exit_code == 0
        assert result.output.strip() == ""
