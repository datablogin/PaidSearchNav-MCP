"""Internationalization (i18n) support for PaidSearchNav."""

# Re-export main components for easier access
from paidsearchnav.i18n.config import I18nConfig
from paidsearchnav.i18n.formatters import (
    format_currency,
    format_date,
    format_number,
    format_percentage,
)
from paidsearchnav.i18n.translator import Translator

# Module-level translator instance
_translator = None


def init_i18n(config=None):
    """Initialize the i18n system with the given configuration."""
    global _translator
    _translator = Translator(config or I18nConfig())


def get_translator():
    """Get the current translator instance."""
    global _translator
    if _translator is None:
        init_i18n()
    return _translator


# Convenience functions
def gettext(message, **kwargs):
    """Translate a message with optional formatting."""
    return get_translator().gettext(message, **kwargs)


def ngettext(singular, plural, n, **kwargs):
    """Translate a message with plural forms."""
    return get_translator().ngettext(singular, plural, n, **kwargs)


def lazy_gettext(message, **kwargs):
    """Lazy translation for messages that should be translated at render time."""
    return get_translator().lazy_gettext(message, **kwargs)


# Alias for convenience
_ = gettext
_n = ngettext
_lazy = lazy_gettext

__all__ = [
    # Core functions
    "init_i18n",
    "get_translator",
    "gettext",
    "ngettext",
    "lazy_gettext",
    # Aliases
    "_",
    "_n",
    "_lazy",
    # Formatters
    "format_currency",
    "format_date",
    "format_number",
    "format_percentage",
    # Classes
    "I18nConfig",
    "Translator",
]
