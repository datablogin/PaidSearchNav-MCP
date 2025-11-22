"""Tests for formatting utilities."""

from datetime import date, datetime, time
from decimal import Decimal

from paidsearchnav.i18n.formatters import (
    format_currency,
    format_date,
    format_datetime,
    format_number,
    format_percentage,
    format_time,
)


class TestCurrencyFormatting:
    """Test currency formatting functions."""

    def test_format_usd(self):
        """Test USD formatting."""
        assert format_currency(1234.56, "USD") == "$1,234.56"
        assert format_currency(1234567.89, "USD") == "$1,234,567.89"
        assert format_currency(0.99, "USD") == "$0.99"

    def test_format_eur(self):
        """Test EUR formatting."""
        assert format_currency(1234.56, "EUR", "es-ES") == "1.234,56 €"
        assert format_currency(1234567.89, "EUR", "de-DE") == "1.234.567,89 €"

    def test_format_jpy(self):
        """Test JPY formatting (no decimals)."""
        assert format_currency(1234, "JPY", "ja-JP") == "¥1,234"
        assert format_currency(1234.56, "JPY", "ja-JP") == "¥1,235"  # Rounded

    def test_format_brl(self):
        """Test BRL formatting."""
        assert format_currency(1234.56, "BRL", "pt-BR") == "R$1.234,56"

    def test_decimal_precision(self):
        """Test handling of Decimal type."""
        amount = Decimal("1234.56")
        assert format_currency(amount, "USD") == "$1,234.56"

        # Very precise decimal
        amount = Decimal("1234.567890")
        assert format_currency(amount, "USD") == "$1,234.57"  # Rounded to 2 places


class TestNumberFormatting:
    """Test number formatting functions."""

    def test_format_us_numbers(self):
        """Test US number formatting."""
        assert format_number(1234.56, language="en-US") == "1,234.56"
        assert format_number(1234567.89, language="en-US") == "1,234,567.89"
        assert format_number(1000, language="en-US") == "1,000"

    def test_format_eu_numbers(self):
        """Test European number formatting."""
        assert format_number(1234.56, language="de-DE") == "1.234,56"
        assert format_number(1234567.89, language="es-ES") == "1.234.567,89"

    def test_format_fr_numbers(self):
        """Test French number formatting (space separator)."""
        assert format_number(1234.56, language="fr-FR") == "1 234,56"
        assert format_number(1234567.89, language="fr-FR") == "1 234 567,89"

    def test_decimal_places(self):
        """Test custom decimal places."""
        assert format_number(1234.5678, decimal_places=0) == "1,235"
        assert format_number(1234.5678, decimal_places=1) == "1,234.6"
        assert format_number(1234.5678, decimal_places=3) == "1,234.568"

    def test_integer_formatting(self):
        """Test integer formatting."""
        assert format_number(1234) == "1,234"
        assert format_number(1234, decimal_places=2) == "1,234.00"


class TestPercentageFormatting:
    """Test percentage formatting."""

    def test_format_percentages(self):
        """Test basic percentage formatting."""
        assert format_percentage(0.1234) == "12.3%"
        assert format_percentage(0.5) == "50.0%"
        assert format_percentage(1.0) == "100.0%"

    def test_percentage_decimal_places(self):
        """Test percentage with custom decimal places."""
        assert format_percentage(0.12345, decimal_places=0) == "12%"
        assert format_percentage(0.12345, decimal_places=2) == "12.34%"
        assert format_percentage(0.12345, decimal_places=3) == "12.345%"

    def test_percentage_locales(self):
        """Test percentage formatting in different locales."""
        assert format_percentage(0.1234, language="de-DE") == "12,3%"
        assert format_percentage(0.1234, language="fr-FR") == "12,3%"


class TestDateFormatting:
    """Test date and time formatting."""

    def test_format_date_us(self):
        """Test US date formatting."""
        test_date = date(2024, 3, 15)
        assert format_date(test_date, language="en-US") == "03/15/2024"

    def test_format_date_eu(self):
        """Test European date formatting."""
        test_date = date(2024, 3, 15)
        assert format_date(test_date, language="es-ES") == "15/03/2024"
        assert format_date(test_date, language="fr-FR") == "15/03/2024"

    def test_format_date_de(self):
        """Test German date formatting."""
        test_date = date(2024, 3, 15)
        assert format_date(test_date, language="de-DE") == "15.03.2024"

    def test_format_date_jp(self):
        """Test Japanese date formatting."""
        test_date = date(2024, 3, 15)
        assert format_date(test_date, language="ja-JP") == "2024年03月15日"

    def test_format_datetime_from_datetime(self):
        """Test formatting date from datetime object."""
        test_datetime = datetime(2024, 3, 15, 14, 30, 45)
        assert format_date(test_datetime, language="en-US") == "03/15/2024"


class TestDateTimeFormatting:
    """Test datetime formatting."""

    def test_format_datetime_us(self):
        """Test US datetime formatting."""
        test_dt = datetime(2024, 3, 15, 14, 30)
        assert format_datetime(test_dt, language="en-US") == "03/15/2024 02:30 PM"

    def test_format_datetime_eu(self):
        """Test European datetime formatting."""
        test_dt = datetime(2024, 3, 15, 14, 30)
        assert format_datetime(test_dt, language="es-ES") == "15/03/2024 14:30"
        assert format_datetime(test_dt, language="fr-FR") == "15/03/2024 14:30"

    def test_format_datetime_de(self):
        """Test German datetime formatting."""
        test_dt = datetime(2024, 3, 15, 14, 30)
        assert format_datetime(test_dt, language="de-DE") == "15.03.2024 14:30"


class TestTimeFormatting:
    """Test time formatting."""

    def test_format_time_us(self):
        """Test US time formatting (12-hour)."""
        test_time = time(14, 30)
        assert format_time(test_time, language="en-US") == "02:30 PM"

        test_time = time(9, 15)
        assert format_time(test_time, language="en-US") == "09:15 AM"

    def test_format_time_eu(self):
        """Test European time formatting (24-hour)."""
        test_time = time(14, 30)
        assert format_time(test_time, language="es-ES") == "14:30"
        assert format_time(test_time, language="fr-FR") == "14:30"
        assert format_time(test_time, language="de-DE") == "14:30"

    def test_format_time_from_datetime(self):
        """Test formatting time from datetime object."""
        test_dt = datetime(2024, 3, 15, 14, 30, 45)
        assert format_time(test_dt, language="en-US") == "02:30 PM"
        assert format_time(test_dt, language="de-DE") == "14:30"
