"""macOS Contacts.app integration for resolving phone numbers to names."""

import sqlite3
import sys
from dataclasses import dataclass
from pathlib import Path

from .phone import normalize_phone

# Default path to macOS AddressBook database
DEFAULT_CONTACTS_DB_PATH = Path.home() / "Library" / "Application Support" / "AddressBook"


@dataclass
class Contact:
    """A contact from the macOS Contacts database."""

    first_name: str | None = None
    last_name: str | None = None
    nickname: str | None = None
    organization: str | None = None

    @property
    def display_name(self) -> str | None:
        """Format the contact's display name as 'First Last'.

        Returns:
            Formatted name, or None if no name components available.
            Priority: first+last > first > last > organization
        """
        if self.first_name and self.last_name:
            return f"{self.first_name} {self.last_name}"
        elif self.first_name:
            return self.first_name
        elif self.last_name:
            return self.last_name
        elif self.organization:
            return self.organization
        return None


def _find_contacts_databases() -> list[Path]:
    """Find all AddressBook database files.

    macOS stores contacts in multiple locations:
    - Main database: ~/Library/Application Support/AddressBook/AddressBook-v22.abcddb
    - Per-source databases:
      ~/Library/Application Support/AddressBook/Sources/*/AddressBook-v22.abcddb

    Returns:
        List of paths to database files, with source databases first (they contain
        the actual synced contacts from iCloud, etc.)
    """
    base_path = DEFAULT_CONTACTS_DB_PATH
    databases = []

    # Check Sources directory first (contains iCloud synced contacts)
    sources_dir = base_path / "Sources"
    if sources_dir.exists():
        for source_dir in sources_dir.iterdir():
            if source_dir.is_dir():
                db_path = source_dir / "AddressBook-v22.abcddb"
                if db_path.exists():
                    databases.append(db_path)

    # Add main database as fallback
    main_db = base_path / "AddressBook-v22.abcddb"
    if main_db.exists():
        databases.append(main_db)

    return databases


def _normalize_for_comparison(phone: str) -> str:
    """Normalize a phone number to digits only for comparison.

    Args:
        phone: Phone number in any format

    Returns:
        Digits only, without leading + or country code variations
    """
    # Extract just digits
    digits = "".join(c for c in phone if c.isdigit())
    return digits


def _build_contact_lookup() -> dict[str, Contact]:
    """Build a lookup dictionary from the Contacts database.

    Returns:
        Dictionary mapping normalized phone numbers and emails to Contact objects
    """
    lookup: dict[str, Contact] = {}

    databases = _find_contacts_databases()
    if not databases:
        return lookup

    for db_path in databases:
        try:
            # Open database in read-only mode with URI
            uri = f"file:{db_path}?mode=ro"
            conn = sqlite3.connect(uri, uri=True, timeout=5)
            conn.row_factory = sqlite3.Row

            # Query phone numbers with contact names
            phone_query = """
                SELECT
                    p.ZFULLNUMBER as phone,
                    r.ZNICKNAME as nickname,
                    r.ZFIRSTNAME as first_name,
                    r.ZLASTNAME as last_name,
                    r.ZORGANIZATION as organization
                FROM ZABCDPHONENUMBER p
                JOIN ZABCDRECORD r ON p.ZOWNER = r.Z_PK
                WHERE p.ZFULLNUMBER IS NOT NULL
            """

            for row in conn.execute(phone_query):
                phone = row["phone"]
                if not phone:
                    continue

                contact = Contact(
                    first_name=row["first_name"],
                    last_name=row["last_name"],
                    nickname=row["nickname"],
                    organization=row["organization"],
                )

                if contact.display_name:
                    # Store with multiple normalized forms for matching
                    # 1. Raw phone number
                    lookup[phone] = contact
                    # 2. Digits only
                    digits = _normalize_for_comparison(phone)
                    if digits:
                        lookup[digits] = contact
                    # 3. Try E.164 normalization
                    try:
                        e164 = normalize_phone(phone)
                        lookup[e164] = contact
                    except ValueError:
                        pass

            # Query email addresses
            email_query = """
                SELECT
                    e.ZADDRESS as email,
                    r.ZNICKNAME as nickname,
                    r.ZFIRSTNAME as first_name,
                    r.ZLASTNAME as last_name,
                    r.ZORGANIZATION as organization
                FROM ZABCDEMAILADDRESS e
                JOIN ZABCDRECORD r ON e.ZOWNER = r.Z_PK
                WHERE e.ZADDRESS IS NOT NULL
            """

            for row in conn.execute(email_query):
                email = row["email"]
                if not email:
                    continue

                contact = Contact(
                    first_name=row["first_name"],
                    last_name=row["last_name"],
                    nickname=row["nickname"],
                    organization=row["organization"],
                )

                if contact.display_name:
                    # Store email in lowercase for case-insensitive matching
                    lookup[email.lower()] = contact

            conn.close()

        except (sqlite3.Error, OSError):
            # Database might be locked or inaccessible
            continue

    return lookup


# Global contact lookup cache
_contact_lookup: dict[str, Contact] | None = None


def _get_contact_lookup() -> dict[str, Contact]:
    """Get or build the contact lookup dictionary."""
    global _contact_lookup
    if _contact_lookup is None:
        _contact_lookup = _build_contact_lookup()
    return _contact_lookup


def _get_contact_impl(identifier: str) -> Contact | None:
    """Look up a Contact from the macOS Contacts database.

    Args:
        identifier: Phone number or email address

    Returns:
        Contact object if found, None otherwise
    """
    if not identifier:
        return None

    lookup = _get_contact_lookup()
    if not lookup:
        return None

    # Try direct lookup first
    if identifier in lookup:
        return lookup[identifier]

    # For emails, try lowercase
    if "@" in identifier:
        return lookup.get(identifier.lower())

    # For phone numbers, try various normalizations
    # 1. Digits only
    digits = _normalize_for_comparison(identifier)
    if digits in lookup:
        return lookup[digits]

    # 2. Try E.164 normalization
    try:
        e164 = normalize_phone(identifier)
        if e164 in lookup:
            return lookup[e164]
    except ValueError:
        pass

    return None


def _get_contact_name_impl(identifier: str) -> str | None:
    """Look up a display name from macOS Contacts database.

    Args:
        identifier: Phone number or email address

    Returns:
        Display name if found, None otherwise
    """
    contact = _get_contact_impl(identifier)
    if contact:
        return contact.display_name
    return None


def _make_get_contact_name():
    def _get_contact_name(identifier: str) -> str | None:
        module = sys.modules[__name__]
        current = module.__dict__.get("get_contact_name")
        if current is not wrapper:
            return current(identifier)
        return _get_contact_name_impl(identifier)

    wrapper = _get_contact_name
    return _get_contact_name


get_contact_name = _make_get_contact_name()


def clear_contact_cache() -> None:
    """Clear the contact name cache.

    Useful if contacts have been updated and you want fresh lookups.
    """
    global _contact_lookup
    _contact_lookup = None


def _get_all_contacts_from_lookup() -> list[Contact]:
    """Get unique contacts from the lookup dictionary.

    Returns:
        List of unique Contact objects with display names.
    """
    lookup = _get_contact_lookup()
    if not lookup:
        return []

    # Use a set to deduplicate contacts (same contact may be stored under multiple keys)
    seen_names: set[str] = set()
    contacts: list[Contact] = []

    for contact in lookup.values():
        name = contact.display_name
        if name and name not in seen_names:
            seen_names.add(name)
            contacts.append(contact)

    # Sort by display name for consistent output
    contacts.sort(key=lambda c: c.display_name or "")
    return contacts


def get_all_contacts() -> list[Contact]:
    """Get all contacts from the macOS Contacts database.

    Returns:
        List of Contact objects with display names.
    """
    return _get_all_contacts_from_lookup()


def search_contacts(query: str) -> list[Contact]:
    """Search contacts by name.

    Args:
        query: Search string to match against contact names (case-insensitive).

    Returns:
        List of Contact objects whose display_name contains the query.
    """
    if not query:
        return []

    all_contacts = get_all_contacts()
    query_lower = query.lower()

    return [c for c in all_contacts if c.display_name and query_lower in c.display_name.lower()]
