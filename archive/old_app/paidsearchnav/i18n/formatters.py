"""Formatting utilities for i18n."""

from datetime import date, datetime, time
from decimal import Decimal
from typing import Optional, Union

from paidsearchnav.i18n.config import I18nConfig


def format_currency(
    amount: Union[float, Decimal],
    currency: str = "USD",
    language: Optional[str] = None,
    config: Optional[I18nConfig] = None,
) -> str:
    """Format a currency amount according to locale rules."""
    if config is None:
        config = I18nConfig()

    locale = config.get_locale(language)
    currency_config = config.get_currency(currency)

    # Convert to Decimal for precise handling
    if not isinstance(amount, Decimal):
        amount = Decimal(str(amount))

    # Format the number part
    formatted = format_number(
        amount,
        decimal_places=currency_config.decimal_places,
        language=language,
        config=config,
    )

    # Add currency symbol
    if currency_config.position == "before":
        return f"{currency_config.symbol}{formatted}"
    else:
        return f"{formatted} {currency_config.symbol}"


def format_number(
    number: Union[int, float, Decimal],
    decimal_places: Optional[int] = None,
    language: Optional[str] = None,
    config: Optional[I18nConfig] = None,
) -> str:
    """Format a number according to locale rules."""
    if config is None:
        config = I18nConfig()

    locale = config.get_locale(language)

    # Convert to Decimal for precise handling
    if not isinstance(number, Decimal):
        number = Decimal(str(number))

    # Determine decimal places
    if decimal_places is None:
        # Use natural decimal places, but limit to 2 for display
        exponent = number.as_tuple().exponent
        decimal_places = min(2, -exponent if exponent < 0 else 0)

    # Format with proper decimal places
    format_str = f"{{:.{decimal_places}f}}"
    formatted = format_str.format(number)

    # Split into integer and decimal parts
    parts = formatted.split(".")
    integer_part = parts[0]
    decimal_part = parts[1] if len(parts) > 1 else ""

    # Add thousand separators
    if locale.thousand_sep:
        # Reverse the string for easier processing
        reversed_int = integer_part[::-1]
        groups = []
        for i in range(0, len(reversed_int), 3):
            groups.append(reversed_int[i : i + 3])
        integer_part = locale.thousand_sep.join(groups)[::-1]

    # Reconstruct with locale decimal separator
    if decimal_part:
        return f"{integer_part}{locale.decimal_sep}{decimal_part}"
    else:
        return integer_part


def format_percentage(
    value: Union[float, Decimal],
    decimal_places: int = 1,
    language: Optional[str] = None,
    config: Optional[I18nConfig] = None,
) -> str:
    """Format a percentage value."""
    if config is None:
        config = I18nConfig()

    # Convert to percentage
    percentage = float(value) * 100

    # Format as number
    formatted = format_number(
        percentage,
        decimal_places=decimal_places,
        language=language,
        config=config,
    )

    return f"{formatted}%"


def format_date(
    date_obj: Union[date, datetime],
    language: Optional[str] = None,
    config: Optional[I18nConfig] = None,
) -> str:
    """Format a date according to locale rules."""
    if config is None:
        config = I18nConfig()

    locale = config.get_locale(language)

    # Convert datetime to date if needed
    if isinstance(date_obj, datetime):
        date_obj = date_obj.date()

    return date_obj.strftime(locale.date_format)


def format_datetime(
    datetime_obj: datetime,
    language: Optional[str] = None,
    config: Optional[I18nConfig] = None,
) -> str:
    """Format a datetime according to locale rules."""
    if config is None:
        config = I18nConfig()

    locale = config.get_locale(language)
    return datetime_obj.strftime(locale.datetime_format)


def format_time(
    time_obj: Union[datetime, time],
    language: Optional[str] = None,
    config: Optional[I18nConfig] = None,
) -> str:
    """Format a time according to locale rules."""
    if config is None:
        config = I18nConfig()

    locale = config.get_locale(language)

    # Handle both datetime and time objects
    if isinstance(time_obj, datetime):
        return time_obj.strftime(locale.time_format)
    else:
        # For time objects, we need to create a datetime to use strftime
        from datetime import datetime as dt

        temp_dt = dt.combine(dt.today(), time_obj)
        return temp_dt.strftime(locale.time_format)
