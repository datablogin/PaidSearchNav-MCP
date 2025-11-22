"""Tests for the translator module."""

from paidsearchnav.i18n import get_translator, gettext, init_i18n, ngettext
from paidsearchnav.i18n.config import I18nConfig
from paidsearchnav.i18n.translator import LazyString, Translator


class TestTranslator:
    """Test the Translator class."""

    def test_init_translator(self):
        """Test translator initialization."""
        config = I18nConfig()
        translator = Translator(config)

        assert translator.config == config
        assert translator.current_language == "en-US"

    def test_set_language(self):
        """Test language setting."""
        translator = Translator(I18nConfig())

        # Set valid language
        translator.set_language("es-ES")
        assert translator.current_language == "es-ES"

        # Set invalid language (should fall back)
        translator.set_language("invalid-lang")
        assert translator.current_language == "en-US"

    def test_gettext_basic(self):
        """Test basic gettext functionality."""
        translator = Translator(I18nConfig())

        # Without translations, should return original
        result = translator.gettext("Hello, world!")
        assert result == "Hello, world!"

    def test_gettext_with_formatting(self):
        """Test gettext with format parameters."""
        translator = Translator(I18nConfig())

        result = translator.gettext(
            "Add negative keywords to save {amount} per month", amount="$500"
        )
        assert result == "Add negative keywords to save $500 per month"

    def test_ngettext(self):
        """Test plural forms."""
        translator = Translator(I18nConfig())

        # Singular
        result = translator.ngettext("{n} keyword found", "{n} keywords found", 1)
        assert result == "1 keyword found"

        # Plural
        result = translator.ngettext("{n} keyword found", "{n} keywords found", 5)
        assert result == "5 keywords found"

    def test_lazy_gettext(self):
        """Test lazy translation."""
        translator = Translator(I18nConfig())

        lazy_str = translator.lazy_gettext("Hello, {name}!", name="World")

        # Should return LazyString instance
        assert isinstance(lazy_str, LazyString)

        # Should translate when converted to string
        assert str(lazy_str) == "Hello, World!"

    def test_extract_language_from_header(self):
        """Test Accept-Language header parsing."""
        translator = Translator(I18nConfig())

        # Simple case
        lang = translator.extract_language_from_header("es-ES")
        assert lang == "es-ES"

        # With quality factors
        lang = translator.extract_language_from_header("fr-FR, fr;q=0.9, en;q=0.8")
        assert lang == "fr-FR"

        # Fallback to base language
        lang = translator.extract_language_from_header("es-MX, en-GB")
        assert lang == "es-ES"  # Falls back to es-ES for es-*

        # Invalid language
        lang = translator.extract_language_from_header("invalid-lang")
        assert lang == "en-US"

        # Empty header
        lang = translator.extract_language_from_header("")
        assert lang == "en-US"

    def test_get_available_languages(self):
        """Test getting available languages."""
        translator = Translator(I18nConfig())

        languages = translator.get_available_languages()
        assert "en-US" in languages
        assert "es-ES" in languages
        assert "fr-FR" in languages
        assert languages["en-US"] == "English (United States)"
        assert languages["es-ES"] == "Español (España)"

    def test_is_language_supported(self):
        """Test language support check."""
        translator = Translator(I18nConfig())

        assert translator.is_language_supported("en-US")
        assert translator.is_language_supported("es-ES")
        assert not translator.is_language_supported("invalid-lang")


class TestModuleFunctions:
    """Test module-level convenience functions."""

    def test_init_i18n(self):
        """Test i18n initialization."""
        config = I18nConfig()
        init_i18n(config)

        translator = get_translator()
        assert isinstance(translator, Translator)
        assert translator.config.default_language == "en-US"

    def test_gettext_function(self):
        """Test module-level gettext function."""
        init_i18n()

        result = gettext("Test message")
        assert result == "Test message"

        # Test with formatting
        result = gettext("Hello, {name}!", name="User")
        assert result == "Hello, User!"

    def test_ngettext_function(self):
        """Test module-level ngettext function."""
        init_i18n()

        result = ngettext("{n} item", "{n} items", 1)
        assert result == "1 item"

        result = ngettext("{n} item", "{n} items", 3)
        assert result == "3 items"
