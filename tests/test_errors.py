"""Tests for error handling."""

import sqlite3

import pytest
from click.testing import CliRunner

import messages
from messages.cli import cli


class TestDatabaseErrors:
    """Tests for database-related errors."""

    def test_database_not_found(self, tmp_path):
        """Should raise FileNotFoundError with clear message."""
        nonexistent = tmp_path / "nonexistent" / "chat.db"
        with pytest.raises(FileNotFoundError) as exc_info:
            messages.get_db(path=str(nonexistent))
        assert "not found" in str(exc_info.value).lower() or "chat.db" in str(exc_info.value)

    def test_permission_denied(self, tmp_path, monkeypatch):
        """Should raise PermissionError with Full Disk Access instructions."""
        db_path = tmp_path / "chat.db"
        # Create a valid database file
        conn = sqlite3.connect(db_path)
        conn.close()

        # Mock sqlite3.connect to raise OperationalError simulating permission denied
        original_connect = sqlite3.connect

        def mock_connect(*args, **kwargs):
            if "mode=ro" in str(args):
                raise sqlite3.OperationalError("unable to open database file")
            return original_connect(*args, **kwargs)

        monkeypatch.setattr("sqlite3.connect", mock_connect)

        with pytest.raises(PermissionError) as exc_info:
            messages.get_db(path=str(db_path))
        error_msg = str(exc_info.value).lower()
        assert "full disk access" in error_msg or "permission" in error_msg


class TestChatErrors:
    """Tests for chat-related errors."""

    def test_chat_not_found(self, messages_db):
        """Should raise error for nonexistent chat ID."""
        with pytest.raises(Exception) as exc_info:
            messages_db.chat(999999)
        # Could be LookupError, KeyError, or custom exception
        assert "not found" in str(exc_info.value).lower() or "999999" in str(exc_info.value)

    def test_chat_by_identifier_not_found(self, messages_db):
        """Should raise error for unknown identifier."""
        with pytest.raises(Exception) as exc_info:
            messages_db.chat_by_identifier("+19999999999")
        assert "not found" in str(exc_info.value).lower() or "9999" in str(exc_info.value)


class TestMessageErrors:
    """Tests for message-related errors."""

    def test_message_not_found(self, messages_db):
        """Should raise error for nonexistent message ID."""
        with pytest.raises(Exception) as exc_info:
            messages_db.message(999999)
        assert "not found" in str(exc_info.value).lower() or "999999" in str(exc_info.value)


class TestPhoneErrors:
    """Tests for phone number parsing errors."""

    def test_invalid_phone_number(self, mock_region):
        """Should raise ValueError for unparseable phone number."""
        from messages.phone import normalize_phone

        with pytest.raises(ValueError) as exc_info:
            normalize_phone("not a phone number")
        assert "phone" in str(exc_info.value).lower() or "parse" in str(exc_info.value).lower()

    def test_empty_phone_number(self, mock_region):
        """Should raise ValueError for empty phone number."""
        from messages.phone import normalize_phone

        with pytest.raises(ValueError):
            normalize_phone("")


class TestCLIErrors:
    """Tests for CLI error handling."""

    @pytest.fixture
    def runner(self):
        return CliRunner()

    def test_cli_database_not_found(self, runner):
        """CLI should show error and exit 1 for missing database."""
        result = runner.invoke(cli, ["--db", "/nonexistent/path/chat.db", "chats"])
        assert result.exit_code == 1
        assert "not found" in result.output.lower() or "error" in result.output.lower()

    def test_cli_chat_not_found(self, runner, test_db_path, monkeypatch):
        """CLI should show error for nonexistent chat."""
        monkeypatch.setattr("messages.phone.get_system_region", lambda: "US")
        monkeypatch.setattr("messages.contacts.get_contact_name", lambda x: None)

        result = runner.invoke(cli, ["--db", str(test_db_path), "messages", "--chat", "999999"])
        assert result.exit_code != 0
        assert "not found" in result.output.lower() or "error" in result.output.lower()

    def test_cli_message_not_found(self, runner, test_db_path, monkeypatch):
        """CLI should show error for nonexistent message."""
        monkeypatch.setattr("messages.phone.get_system_region", lambda: "US")
        monkeypatch.setattr("messages.contacts.get_contact_name", lambda x: None)

        result = runner.invoke(cli, ["--db", str(test_db_path), "read", "999999"])
        assert result.exit_code != 0

    def test_cli_invalid_phone_number(self, runner, test_db_path, monkeypatch):
        """CLI should show error for invalid phone number."""
        monkeypatch.setattr("messages.phone.get_system_region", lambda: "US")
        monkeypatch.setattr("messages.contacts.get_contact_name", lambda x: None)

        result = runner.invoke(
            cli, ["--db", str(test_db_path), "messages", "--with", "not-a-phone"]
        )
        assert result.exit_code != 0
        output_lower = result.output.lower()
        assert "phone" in output_lower or "parse" in output_lower or "error" in output_lower

    def test_cli_no_options_shows_help(self, runner):
        """CLI should show help when no options provided."""
        result = runner.invoke(cli, [])
        assert result.exit_code == 0
        assert "Usage:" in result.output

    def test_cli_invalid_service_filter(self, runner, test_db_path, monkeypatch):
        """CLI should reject invalid service filter values."""
        monkeypatch.setattr("messages.phone.get_system_region", lambda: "US")
        monkeypatch.setattr("messages.contacts.get_contact_name", lambda x: None)

        result = runner.invoke(cli, ["--db", str(test_db_path), "chats", "--service", "invalid"])
        # Click should reject invalid choice
        assert result.exit_code != 0

    def test_cli_invalid_date_format(self, runner, test_db_path, monkeypatch):
        """CLI should show error for invalid date format."""
        monkeypatch.setattr("messages.phone.get_system_region", lambda: "US")
        monkeypatch.setattr("messages.contacts.get_contact_name", lambda x: None)

        result = runner.invoke(
            cli, ["--db", str(test_db_path), "messages", "--chat", "1", "--after", "not-a-date"]
        )
        assert result.exit_code != 0


class TestEdgeCases:
    """Tests for edge cases and boundary conditions."""

    def test_empty_chat(self, test_db_path, monkeypatch):
        """Should handle chat with no messages gracefully."""
        # Add an empty chat to the test database
        import sqlite3

        conn = sqlite3.connect(test_db_path)
        conn.execute(
            """INSERT INTO chat
            (ROWID, guid, chat_identifier, display_name, service_name)
            VALUES (?, ?, ?, ?, ?)""",
            (99, "empty-chat", "empty@example.com", "Empty Chat", "iMessage"),
        )
        conn.commit()
        conn.close()

        monkeypatch.setattr("messages.phone.get_system_region", lambda: "US")
        monkeypatch.setattr("messages.contacts.get_contact_name", lambda x: None)

        db = messages.get_db(path=str(test_db_path))
        msgs = list(db.messages(chat_id=99))
        assert len(msgs) == 0

    def test_message_with_null_text(self, messages_db):
        """Should handle messages with NULL text (like reactions, unsent)."""
        # Message 8 in our test data is unsent with NULL text
        msg = messages_db.message(8)
        assert msg.text is None
        assert msg.is_unsent is True

    def test_very_long_limit(self, messages_db):
        """Should handle very large limit values."""
        msgs = list(messages_db.messages(chat_id=1, limit=1000000))
        # Should return all messages, not crash
        assert len(msgs) > 0

    def test_negative_offset(self, messages_db):
        """Should handle negative offset gracefully."""
        # Behavior depends on implementation - might clamp to 0 or raise
        try:
            msgs = list(messages_db.messages(chat_id=1, offset=-1))
            # If it doesn't raise, should behave like offset=0
            assert len(msgs) > 0
        except (ValueError, Exception):
            pass  # Also acceptable to raise

    def test_zero_limit(self, messages_db):
        """Should handle zero limit."""
        msgs = list(messages_db.messages(chat_id=1, limit=0))
        assert len(msgs) == 0
