"""Shared instrument profiles and stock quotes for Vietnamese market research."""

from datetime import datetime

from pydantic import BaseModel, ConfigDict, computed_field

__all__ = ["SymbolInfo", "StockQuote"]


class SymbolInfo(BaseModel):
    """Immutable profile details for researching a Vietnamese market instrument.

    The exchange, symbol, name, and overview fields are required. All remaining
    fields default to None. Supplied text is preserved.

    Attributes:
        exchange (str): Listing exchange, such as HOSE, HNX, or UPCOM.
            Lookup results use uppercase.
        symbol (str): Instrument code without an exchange prefix or .VN suffix.
            Lookup results use uppercase.
        name (str): Instrument or company name.
        overview (str): Instrument or issuer description; empty if unavailable.
        english_name (str | None): English-language name, if available.
        short_name (str | None): Abbreviated name, if available.
        website (str | None): Reported website address, if available.
        symbol_type (str | None): Reported instrument type, uppercased by
            lookups, such as STOCK or ETF.
        index_code (str | None): Reported index membership code, uppercased by
            lookups, such as VN30. An explicitly empty code remains empty.
        industry (str | None): Reported GICS industry label, without changes.
        sub_industry (str | None): Reported GICS sub-industry label, without
            changes.
        sector (str | None): Reported GICS sector label, without changes.
        industry_group (str | None): Reported GICS industry-group label, without
            changes.
        industry_group_slug (str | None): Reported GICS industry-group slug,
            without changes.

    Raises:
        pydantic.ValidationError: A required field is missing, a value has an
            incorrect type, an unexpected field is supplied, or an immutable
            field is changed.
    """

    model_config = ConfigDict(
        frozen=True, strict=True, extra="forbid", allow_inf_nan=False
    )

    exchange: str
    symbol: str
    name: str
    overview: str
    english_name: str | None = None
    short_name: str | None = None
    website: str | None = None
    symbol_type: str | None = None
    index_code: str | None = None
    industry: str | None = None
    sub_industry: str | None = None
    sector: str | None = None
    industry_group: str | None = None
    industry_group_slug: str | None = None


class StockQuote(BaseModel):
    """Immutable stock prices and traded volume for a trading period.

    All input fields except close are required. Prices are in Vietnamese dong
    (VND) per traded unit, and volume counts traded units. Prices must be finite.
    Timestamp timezone information is preserved.

    Attributes:
        timestamp (datetime.datetime): Date and time represented by the quote.
        timestamp_str (str): Derived ISO 8601 representation of timestamp,
            preserving fractional seconds and any timezone offset.
        exchange (str): Listing exchange, such as HOSE, HNX, or UPCOM.
        symbol (str): Traded instrument code, such as FPT.
        open (float): Opening price for the trading period.
        high (float): Highest price reached during the trading period.
        low (float): Lowest price reached during the trading period.
        volume (int): Total traded volume for the trading period.
        close (float | None): Final closing price for the trading period.
            Defaults to None while trading is ongoing and the closing price
            has not been finalized.

    Raises:
        pydantic.ValidationError: A required field is missing, a value has an
            incorrect type, a price is not finite, an unexpected field is
            supplied, or an immutable field is changed.
    """

    model_config = ConfigDict(
        frozen=True, strict=True, extra="forbid", allow_inf_nan=False
    )

    timestamp: datetime
    exchange: str
    symbol: str
    open: float
    high: float
    low: float
    volume: int
    close: float | None = None

    @computed_field
    @property
    def timestamp_str(self) -> str:
        """Return the quote timestamp in ISO 8601 format."""
        return self.timestamp.isoformat()
