"""Translation functionality for i18n."""

import gettext
import threading
from functools import lru_cache
from typing import Dict, Union

from paidsearchnav.i18n.config import I18nConfig


class LazyString:
    """Lazy string for deferred translation."""

    def __init__(self, func, *args, **kwargs):
        self.func = func
        self.args = args
        self.kwargs = kwargs

    def __str__(self):
        return self.func(*self.args, **self.kwargs)

    def __repr__(self):
        return f"<LazyString: {self.func.__name__}>"


class Translator:
    """Main translator class handling all translation operations."""

    def __init__(self, config: I18nConfig):
        self.config = config
        self._translations: Dict[str, gettext.GNUTranslations] = {}
        self._current_language = threading.local()
        self._load_translations()

    def _load_translations(self) -> None:
        """Load all available translations."""
        for lang in self.config.supported_languages:
            try:
                lang_path = self.config.translation_directory / lang / "LC_MESSAGES"
                if lang_path.exists():
                    translation = gettext.translation(
                        self.config.domain,
                        localedir=str(self.config.translation_directory),
                        languages=[lang],
                    )
                    self._translations[lang] = translation
            except FileNotFoundError:
                # No translation file for this language yet
                pass

    @property
    def current_language(self) -> str:
        """Get the current language for this thread."""
        return getattr(self._current_language, "value", self.config.default_language)

    @current_language.setter
    def current_language(self, language: str) -> None:
        """Set the current language for this thread."""
        if language in self.config.supported_languages:
            self._current_language.value = language
        else:
            self._current_language.value = self.config.fallback_language

    def set_language(self, language: str) -> None:
        """Set the active language for translations."""
        self.current_language = language

    @lru_cache(maxsize=1000)
    def _get_translation(
        self, language: str
    ) -> Union[gettext.GNUTranslations, gettext.NullTranslations]:
        """Get translation object for a language with caching."""
        if language in self._translations:
            return self._translations[language]

        # Try to load translation if not already loaded
        try:
            translation = gettext.translation(
                self.config.domain,
                localedir=str(self.config.translation_directory),
                languages=[language],
            )
            self._translations[language] = translation
            return translation
        except FileNotFoundError:
            # Fall back to null translations (returns original text)
            return gettext.NullTranslations()

    def gettext(self, message: str, **kwargs) -> str:
        """Translate a message with optional formatting."""
        translation = self._get_translation(self.current_language)
        translated = translation.gettext(message)

        # Apply formatting if kwargs provided
        if kwargs:
            try:
                return translated.format(**kwargs)
            except KeyError:
                # If formatting fails, return translated string without formatting
                return translated

        return translated

    def ngettext(self, singular: str, plural: str, n: int, **kwargs) -> str:
        """Translate a message with plural forms."""
        translation = self._get_translation(self.current_language)
        translated = translation.ngettext(singular, plural, n)

        # Apply formatting
        kwargs["n"] = n  # Always include count in formatting
        try:
            return translated.format(**kwargs)
        except KeyError:
            return translated

    def lazy_gettext(self, message: str, **kwargs) -> LazyString:
        """Lazy translation for messages that should be translated at render time."""
        return LazyString(self.gettext, message, **kwargs)

    def get_available_languages(self) -> Dict[str, str]:
        """Get all available languages with their display names."""
        result = {}
        for lang_code in self.config.supported_languages:
            locale = self.config.get_locale(lang_code)
            result[lang_code] = locale.name
        return result

    def is_language_supported(self, language: str) -> bool:
        """Check if a language is supported."""
        return language in self.config.supported_languages

    def extract_language_from_header(self, accept_language: str) -> str:
        """Extract the best matching language from Accept-Language header."""
        if not accept_language:
            return self.config.default_language

        # Parse Accept-Language header
        # Example: "fr-FR, fr;q=0.9, en;q=0.8"
        languages = []
        for lang_spec in accept_language.split(","):
            parts = lang_spec.strip().split(";")
            lang = parts[0].strip()

            # Get quality factor (default to 1.0)
            quality = 1.0
            if len(parts) > 1:
                for part in parts[1:]:
                    if part.strip().startswith("q="):
                        try:
                            quality = float(part.strip()[2:])
                        except ValueError:
                            quality = 1.0

            languages.append((lang, quality))

        # Sort by quality factor (descending)
        languages.sort(key=lambda x: x[1], reverse=True)

        # Find best matching supported language
        for lang, _ in languages:
            # Try exact match first
            if lang in self.config.supported_languages:
                return lang

            # Try language code without region
            base_lang = lang.split("-")[0]
            for supported in self.config.supported_languages:
                if supported.startswith(base_lang + "-"):
                    return supported

        return self.config.default_language
