"""macOS Accessibility helpers.

Currently this exposes a single privacy-focused capability: detecting when
the focused UI element is a secure (password) text field, so the app can
avoid capturing those keystrokes at all.

All functions degrade gracefully to ``False`` on non-macOS systems or when
the Accessibility APIs are unavailable, so callers never need to guard the
import themselves.
"""

import time

# macOS reports password fields with this Accessibility subrole.
SECURE_FIELD_SUBROLE = "AXSecureTextField"

_CACHE_TTL_SECONDS = 0.4
_cache = {"value": False, "at": 0.0}


def _query_secure_field() -> bool:
    """Ask macOS whether the system-wide focused element is a secure field."""
    try:
        from ApplicationServices import (
            AXUIElementCreateSystemWide,
            AXUIElementCopyAttributeValue,
            kAXFocusedUIElementAttribute,
            kAXRoleAttribute,
            kAXSubroleAttribute,
        )
    except Exception:
        return False

    try:
        system = AXUIElementCreateSystemWide()
        err, focused = AXUIElementCopyAttributeValue(
            system, kAXFocusedUIElementAttribute, None
        )
        if err != 0 or focused is None:
            return False

        for attribute in (kAXSubroleAttribute, kAXRoleAttribute):
            err, value = AXUIElementCopyAttributeValue(focused, attribute, None)
            if err == 0 and value == SECURE_FIELD_SUBROLE:
                return True
        return False
    except Exception:
        return False


def is_secure_field_focused(use_cache: bool = True) -> bool:
    """Return True when a password/secure text field currently has focus.

    Results are cached briefly so this can be called on every keystroke
    without repeatedly crossing into the Accessibility API.
    """
    now = time.time()
    if use_cache and (now - _cache["at"]) < _CACHE_TTL_SECONDS:
        return _cache["value"]

    value = _query_secure_field()
    _cache["value"] = value
    _cache["at"] = now
    return value


def reset_cache() -> None:
    """Clear the cached secure-field result (used mainly by tests)."""
    _cache["value"] = False
    _cache["at"] = 0.0
