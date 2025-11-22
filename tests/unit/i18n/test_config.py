"""Tests for i18n configuration."""

from pathlib import Path

from paidsearchnav_mcp.i18n.config import CurrencyConfig, I18nConfig, LocaleConfig


class TestI18nConfig:
    """Test i18n configuration."""

    def test_default_config(self):
        """Test default configuration values."""
        config = I18nConfig()

        assert config.default_language == "en-US"
        assert config.fallback_language == "en-US"
        assert len(config.supported_languages) == 6
        assert "en-US" in config.supported_languages
        assert "es-ES" in config.supported_languages
        assert config.domain == "paidsearchnav"
        assert config.cache_translations is True
        assert config.cache_size == 1000

    def test_locale_configs(self):
        """Test locale configurations."""
        config = I18nConfig()

        # Check all locales are configured
        for lang in config.supported_languages:
            assert lang in config.locales
            locale = config.locales[lang]
            assert isinstance(locale, LocaleConfig)
            assert locale.code == lang
            assert locale.name
            assert locale.currency
            assert locale.date_format
            assert locale.time_format
            assert locale.datetime_format

    def test_currency_configs(self):
        """Test currency configurations."""
        config = I18nConfig()

        # Check major currencies
        currencies = ["USD", "EUR", "JPY", "BRL", "GBP", "CAD"]
        for currency in currencies:
            assert currency in config.currencies
            curr_config = config.currencies[currency]
            assert isinstance(curr_config, CurrencyConfig)
            assert curr_config.symbol
            assert curr_config.position in ["before", "after"]
            assert curr_config.decimal_sep
            assert curr_config.thousand_sep

        # Check JPY has no decimal places
        assert config.currencies["JPY"].decimal_places == 0

    def test_get_locale(self):
        """Test getting locale configuration."""
        config = I18nConfig()

        # Get specific locale
        locale = config.get_locale("es-ES")
        assert locale.code == "es-ES"
        assert locale.name == "Español (España)"
        assert locale.currency == "EUR"

        # Get default locale
        locale = config.get_locale()
        assert locale.code == "en-US"

        # Get invalid locale (falls back)
        locale = config.get_locale("invalid-lang")
        assert locale.code == "en-US"

    def test_get_currency(self):
        """Test getting currency configuration."""
        config = I18nConfig()

        # Get specific currency
        currency = config.get_currency("EUR")
        assert currency.symbol == "€"
        assert currency.position == "after"

        # Get invalid currency (falls back to USD)
        currency = config.get_currency("INVALID")
        assert currency.symbol == "$"
        assert currency.position == "before"

    def test_translation_directory(self):
        """Test translation directory path."""
        config = I18nConfig()

        assert isinstance(config.translation_directory, Path)
        assert config.translation_directory.name == "translations"


class TestLocaleConfig:
    """Test LocaleConfig dataclass."""

    def test_locale_creation(self):
        """Test creating a locale configuration."""
        locale = LocaleConfig(
            code="test-TEST",
            name="Test Language",
            currency="TST",
            date_format="%Y-%m-%d",
            time_format="%H:%M:%S",
            datetime_format="%Y-%m-%d %H:%M:%S",
            decimal_sep=",",
            thousand_sep=".",
            rtl=False,
        )

        assert locale.code == "test-TEST"
        assert locale.name == "Test Language"
        assert locale.currency == "TST"
        assert locale.rtl is False


class TestCurrencyConfig:
    """Test CurrencyConfig dataclass."""

    def test_currency_creation(self):
        """Test creating a currency configuration."""
        currency = CurrencyConfig(
            symbol="T$",
            position="before",
            decimal_sep=".",
            thousand_sep=",",
            decimal_places=2,
        )

        assert currency.symbol == "T$"
        assert currency.position == "before"
        assert currency.decimal_places == 2
