"""Configuration for i18n support."""

from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional


@dataclass
class CurrencyConfig:
    """Configuration for currency formatting."""

    symbol: str
    position: str  # "before" or "after"
    decimal_sep: str
    thousand_sep: str
    decimal_places: int = 2


@dataclass
class LocaleConfig:
    """Configuration for a specific locale."""

    code: str
    name: str
    currency: str
    date_format: str
    time_format: str
    datetime_format: str
    decimal_sep: str
    thousand_sep: str
    rtl: bool = False  # Right-to-left support


@dataclass
class I18nConfig:
    """Main i18n configuration."""

    default_language: str = "en-US"
    fallback_language: str = "en-US"
    supported_languages: List[str] = field(
        default_factory=lambda: [
            "en-US",
            "es-ES",
            "fr-FR",
            "de-DE",
            "ja-JP",
            "pt-BR",
        ]
    )

    translation_directory: Path = field(
        default_factory=lambda: Path(__file__).parent.parent.parent / "translations"
    )

    domain: str = "paidsearchnav"

    # Locale configurations
    locales: Dict[str, LocaleConfig] = field(
        default_factory=lambda: {
            "en-US": LocaleConfig(
                code="en-US",
                name="English (United States)",
                currency="USD",
                date_format="%m/%d/%Y",
                time_format="%I:%M %p",
                datetime_format="%m/%d/%Y %I:%M %p",
                decimal_sep=".",
                thousand_sep=",",
            ),
            "es-ES": LocaleConfig(
                code="es-ES",
                name="Español (España)",
                currency="EUR",
                date_format="%d/%m/%Y",
                time_format="%H:%M",
                datetime_format="%d/%m/%Y %H:%M",
                decimal_sep=",",
                thousand_sep=".",
            ),
            "fr-FR": LocaleConfig(
                code="fr-FR",
                name="Français (France)",
                currency="EUR",
                date_format="%d/%m/%Y",
                time_format="%H:%M",
                datetime_format="%d/%m/%Y %H:%M",
                decimal_sep=",",
                thousand_sep=" ",
            ),
            "de-DE": LocaleConfig(
                code="de-DE",
                name="Deutsch (Deutschland)",
                currency="EUR",
                date_format="%d.%m.%Y",
                time_format="%H:%M",
                datetime_format="%d.%m.%Y %H:%M",
                decimal_sep=",",
                thousand_sep=".",
            ),
            "ja-JP": LocaleConfig(
                code="ja-JP",
                name="日本語 (日本)",
                currency="JPY",
                date_format="%Y年%m月%d日",
                time_format="%H:%M",
                datetime_format="%Y年%m月%d日 %H:%M",
                decimal_sep=".",
                thousand_sep=",",
            ),
            "pt-BR": LocaleConfig(
                code="pt-BR",
                name="Português (Brasil)",
                currency="BRL",
                date_format="%d/%m/%Y",
                time_format="%H:%M",
                datetime_format="%d/%m/%Y %H:%M",
                decimal_sep=",",
                thousand_sep=".",
            ),
        }
    )

    # Currency configurations
    currencies: Dict[str, CurrencyConfig] = field(
        default_factory=lambda: {
            "USD": CurrencyConfig(
                symbol="$",
                position="before",
                decimal_sep=".",
                thousand_sep=",",
            ),
            "EUR": CurrencyConfig(
                symbol="€",
                position="after",
                decimal_sep=",",
                thousand_sep=".",
            ),
            "JPY": CurrencyConfig(
                symbol="¥",
                position="before",
                decimal_sep=".",
                thousand_sep=",",
                decimal_places=0,
            ),
            "BRL": CurrencyConfig(
                symbol="R$",
                position="before",
                decimal_sep=",",
                thousand_sep=".",
            ),
            "GBP": CurrencyConfig(
                symbol="£",
                position="before",
                decimal_sep=".",
                thousand_sep=",",
            ),
            "CAD": CurrencyConfig(
                symbol="CA$",
                position="before",
                decimal_sep=".",
                thousand_sep=",",
            ),
        }
    )

    # Translation caching
    cache_translations: bool = True
    cache_size: int = 1000

    @classmethod
    def from_settings(cls) -> "I18nConfig":
        """Create config from application settings."""
        try:
            from paidsearchnav.core.config import get_settings

            settings = get_settings()
            return cls(
                default_language=getattr(settings, "DEFAULT_LANGUAGE", "en-US"),
                supported_languages=getattr(
                    settings, "SUPPORTED_LANGUAGES", cls().supported_languages
                ),
            )
        except ImportError:
            # If can't import settings, use defaults
            return cls()

    def get_locale(self, language: Optional[str] = None) -> LocaleConfig:
        """Get locale config for a language."""
        lang = language or self.default_language
        return self.locales.get(lang, self.locales[self.fallback_language])

    def get_currency(self, currency_code: str) -> CurrencyConfig:
        """Get currency config."""
        return self.currencies.get(
            currency_code,
            self.currencies["USD"],  # Default to USD if not found
        )
