"""Phone number normalization and matching."""

import subprocess
from functools import lru_cache

import phonenumbers
from phonenumbers import NumberParseException


@lru_cache(maxsize=1)
def get_system_region() -> str:
    """Get the user's region code from macOS system settings.

    Returns:
        Two-letter region code (e.g., "US", "GB")
    """
    try:
        # Try AppleLocale first (e.g., "en_US")
        result = subprocess.run(
            ["defaults", "read", "NSGlobalDomain", "AppleLocale"],
            capture_output=True,
            text=True,
            timeout=5,
        )
        if result.returncode == 0:
            locale = result.stdout.strip()
            # Extract region from locale (e.g., "en_US" -> "US")
            if "_" in locale:
                return locale.split("_")[1][:2].upper()
            elif "-" in locale:
                return locale.split("-")[1][:2].upper()
    except (subprocess.TimeoutExpired, FileNotFoundError):
        pass

    try:
        # Fall back to AppleGeo
        result = subprocess.run(
            ["defaults", "read", "NSGlobalDomain", "AppleGeo"],
            capture_output=True,
            text=True,
            timeout=5,
        )
        if result.returncode == 0:
            return result.stdout.strip()[:2].upper()
    except (subprocess.TimeoutExpired, FileNotFoundError):
        pass

    # Default to US if we can't determine
    return "US"


def normalize_phone(number: str, default_region: str | None = None) -> str:
    """Normalize a phone number to E.164 format for matching.

    Args:
        number: Phone number in any format
        default_region: Region code for numbers without country code.
                       Auto-detected from system if not provided.

    Returns:
        E.164 formatted number (e.g., "+15551234567")

    Raises:
        ValueError: If number cannot be parsed
    """
    if not number:
        raise ValueError("Phone number cannot be empty")

    number = number.strip()
    if any(char.isalpha() for char in number):
        raise ValueError(f"Could not parse phone number: {number}")

    if default_region is None:
        default_region = get_system_region()

    try:
        parsed = phonenumbers.parse(number, default_region)
        if not phonenumbers.is_valid_number(parsed):
            # Try to be lenient - some numbers might be valid but not "possible"
            if not phonenumbers.is_possible_number(parsed):
                raise ValueError(f"Could not parse phone number: {number}")
        return phonenumbers.format_number(parsed, phonenumbers.PhoneNumberFormat.E164)
    except NumberParseException as e:
        raise ValueError(f"Could not parse phone number: {number}") from e


def phone_match(query: str, stored: str, default_region: str | None = None) -> bool:
    """Check if a phone number query matches a stored number.

    Handles cases like:
    - "07XXX XXXXXX" matching "+44 7XXX XXXXXX"
    - "555-1234" matching "+1 555 555 1234" (with area code inference)
    - Full E.164 exact matches
    - Email addresses (exact match, case-insensitive)

    Args:
        query: User's search query (any format)
        stored: Number stored in database
        default_region: Region for parsing numbers without country code

    Returns:
        True if numbers match
    """
    if not query or not stored:
        return False

    # Check if it's an email (contains @ and no digits at start)
    if "@" in query or "@" in stored:
        return query.lower() == stored.lower()

    if default_region is None:
        default_region = get_system_region()

    try:
        query_normalized = normalize_phone(query, default_region)
        stored_normalized = normalize_phone(stored, default_region)
        return query_normalized == stored_normalized
    except ValueError:
        # If we can't parse, fall back to simple string comparison
        # Strip common formatting characters
        query_clean = "".join(c for c in query if c.isdigit())
        stored_clean = "".join(c for c in stored if c.isdigit())

        # Check if one ends with the other (partial match)
        if len(query_clean) >= 7 and len(stored_clean) >= 7:
            if query_clean.endswith(stored_clean[-7:]):
                return True
            if stored_clean.endswith(query_clean[-7:]):
                return True

        return False
