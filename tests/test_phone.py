"""Tests for phone number normalization and matching."""

import pytest

from messages.phone import get_system_region, normalize_phone, phone_match


class TestNormalizePhone:
    """Tests for normalize_phone function."""

    @pytest.mark.parametrize(
        "input_number,region,expected",
        [
            # US formats
            ("+15551234567", "US", "+15551234567"),  # Already E.164
            ("5551234567", "US", "+15551234567"),  # 10-digit
            ("555-123-4567", "US", "+15551234567"),  # Dashes
            ("(555) 123-4567", "US", "+15551234567"),  # Parens
            ("555.123.4567", "US", "+15551234567"),  # Dots
            ("1-555-123-4567", "US", "+15551234567"),  # With country code
            ("+1 555 123 4567", "US", "+15551234567"),  # Spaces
            ("1 (555) 123-4567", "US", "+15551234567"),  # Mixed format
        ],
    )
    def test_normalize_us_formats(self, input_number, region, expected, monkeypatch):
        """US phone numbers in various formats should normalize to E.164."""
        monkeypatch.setattr("messages.phone.get_system_region", lambda: region)
        assert normalize_phone(input_number) == expected

    @pytest.mark.parametrize(
        "input_number,region,expected",
        [
            # UK formats
            ("+447700900123", "GB", "+447700900123"),  # Already E.164
            ("07700 900123", "GB", "+447700900123"),  # Local mobile
            ("07700900123", "GB", "+447700900123"),  # No spaces
            ("+44 7700 900123", "GB", "+447700900123"),  # International with spaces
            ("00447700900123", "GB", "+447700900123"),  # International with 00
        ],
    )
    def test_normalize_uk_formats(self, input_number, region, expected, monkeypatch):
        """UK phone numbers in various formats should normalize to E.164."""
        monkeypatch.setattr("messages.phone.get_system_region", lambda: region)
        assert normalize_phone(input_number) == expected

    def test_normalize_phone_invalid(self, mock_region):
        """Invalid phone number should raise ValueError."""
        with pytest.raises(ValueError):
            normalize_phone("not a phone number")

    def test_normalize_phone_empty(self, mock_region):
        """Empty string should raise ValueError."""
        with pytest.raises(ValueError):
            normalize_phone("")

    def test_normalize_phone_too_short(self, mock_region):
        """Too-short number should raise ValueError."""
        with pytest.raises(ValueError):
            normalize_phone("123")

    def test_normalize_phone_with_letters(self, mock_region):
        """Number with letters should raise ValueError."""
        with pytest.raises(ValueError):
            normalize_phone("555-ABC-1234")

    def test_normalize_preserves_plus(self, mock_region):
        """E.164 numbers should start with +."""
        result = normalize_phone("5551234567")
        assert result.startswith("+")


class TestPhoneMatch:
    """Tests for phone_match function."""

    @pytest.mark.parametrize(
        "query,stored,should_match",
        [
            # Exact matches
            ("+15551234567", "+15551234567", True),
            # Local format matches E.164
            ("555-123-4567", "+15551234567", True),
            ("5551234567", "+15551234567", True),
            ("(555) 123-4567", "+15551234567", True),
            # International format matches
            ("+1 555 123 4567", "+15551234567", True),
            ("1-555-123-4567", "+15551234567", True),
            # Non-matches
            ("555-123-4567", "+15559999999", False),
            ("555-123-4567", "+15551234568", False),  # Off by one
            # UK numbers
            ("07700 900123", "+447700900123", True),
            ("+44 7700 900 123", "+447700900123", True),
        ],
    )
    def test_phone_match(self, query, stored, should_match, monkeypatch):
        """Phone matching should handle various format combinations."""
        # Use US region by default, GB for UK numbers
        region = "GB" if "7700" in query else "US"
        monkeypatch.setattr("messages.phone.get_system_region", lambda: region)
        assert phone_match(query, stored) == should_match

    def test_phone_match_email_exact(self, mock_region):
        """Email addresses should match exactly."""
        assert phone_match("jane@example.com", "jane@example.com") is True
        assert phone_match("jane@example.com", "john@example.com") is False

    def test_phone_match_email_case_insensitive(self, mock_region):
        """Email matching should be case-insensitive."""
        assert phone_match("Jane@Example.COM", "jane@example.com") is True

    def test_phone_match_invalid_query_returns_false(self, mock_region):
        """Invalid query should return False, not raise."""
        # This depends on implementation - might want to be lenient
        result = phone_match("invalid", "+15551234567")
        assert result is False


class TestGetSystemRegion:
    """Tests for get_system_region function."""

    def test_get_system_region_returns_string(self):
        """Should return a valid region code string."""
        region = get_system_region()
        assert isinstance(region, str)
        assert len(region) == 2  # ISO country codes are 2 letters

    def test_get_system_region_uppercase(self):
        """Region code should be uppercase."""
        region = get_system_region()
        assert region == region.upper()


class TestPhoneNumberEdgeCases:
    """Tests for edge cases in phone number handling."""

    def test_normalize_with_extension(self, mock_region):
        """Phone numbers with extensions might be handled specially."""
        # This behavior depends on requirements
        # Could strip extension, raise error, or preserve it
        try:
            result = normalize_phone("555-123-4567 x123")
            # If it succeeds, should still be valid E.164
            assert result.startswith("+")
        except ValueError:
            # Or it might reject extensions
            pass

    def test_normalize_international_format(self, mock_region):
        """International format with + should work from any region."""
        # +44 number should work even with US region
        result = normalize_phone("+447700900123")
        assert result == "+447700900123"

    def test_normalize_strips_whitespace(self, mock_region):
        """Should handle leading/trailing whitespace."""
        result = normalize_phone("  555-123-4567  ")
        assert result == "+15551234567"

    def test_match_handles_none_gracefully(self, mock_region):
        """Matching with None should not crash."""
        # Behavior depends on implementation
        try:
            result = phone_match(None, "+15551234567")
            assert result is False
        except (TypeError, ValueError):
            pass  # Also acceptable to raise
