"""macOS Contacts.app integration for resolving phone numbers to names."""

import subprocess
import sys
from functools import lru_cache
from typing import Optional


def _get_contact_name_impl(identifier: str) -> Optional[str]:
    """Look up a display name from macOS Contacts.app.

    Uses the identifier (phone number or email) to find the contact
    and returns the display name matching Messages.app behavior:
    - Nickname if set
    - Otherwise first name (or full name depending on system settings)

    Args:
        identifier: Phone number or email address

    Returns:
        Display name if found, None otherwise

    Note:
        May require Contacts permission on first use.
        Returns None silently if permission denied.
    """
    if not identifier:
        return None

    # Use AppleScript to query Contacts.app
    # This triggers the permission dialog on first use
    script = f'''
    tell application "Contacts"
        set matchingPeople to {{}}

        -- Search by phone number
        set matchingPeople to (people whose value of phones contains "{identifier}")

        -- If no match, try email
        if (count of matchingPeople) = 0 then
            set matchingPeople to (people whose value of emails contains "{identifier}")
        end if

        if (count of matchingPeople) > 0 then
            set thePerson to item 1 of matchingPeople

            -- Try nickname first
            set theNickname to nickname of thePerson
            if theNickname is not "" and theNickname is not missing value then
                return theNickname
            end if

            -- Fall back to first name
            set theFirstName to first name of thePerson
            if theFirstName is not "" and theFirstName is not missing value then
                return theFirstName
            end if

            -- Fall back to last name
            set theLastName to last name of thePerson
            if theLastName is not "" and theLastName is not missing value then
                return theLastName
            end if

            -- Fall back to organization
            set theOrg to organization of thePerson
            if theOrg is not "" and theOrg is not missing value then
                return theOrg
            end if
        end if

        return ""
    end tell
    '''

    try:
        result = subprocess.run(
            ["osascript", "-e", script],
            capture_output=True,
            text=True,
            timeout=5,
        )
        if result.returncode == 0:
            name = result.stdout.strip()
            if name:
                return name
    except (subprocess.TimeoutExpired, FileNotFoundError, OSError):
        pass

    return None


@lru_cache(maxsize=256)
def _get_contact_name_cached(identifier: str) -> Optional[str]:
    return _get_contact_name_impl(identifier)


def _make_get_contact_name():
    def _get_contact_name(identifier: str) -> Optional[str]:
        module = sys.modules[__name__]
        current = module.__dict__.get("get_contact_name")
        if current is not wrapper:
            return current(identifier)
        return _get_contact_name_cached(identifier)

    wrapper = _get_contact_name
    return _get_contact_name


get_contact_name = _make_get_contact_name()


def clear_contact_cache() -> None:
    """Clear the contact name cache.

    Useful if contacts have been updated and you want fresh lookups.
    """
    _get_contact_name_cached.cache_clear()
