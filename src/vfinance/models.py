"""Shared instrument profiles for Vietnamese market research."""

from dataclasses import dataclass as _dataclass

__all__ = ["SymbolInfo"]


@_dataclass(frozen=True, slots=True)
class SymbolInfo:
    """Immutable profile details for researching a Vietnamese market instrument.

    The exchange, symbol, name, and overview fields are required. All remaining
    fields default to None. Directly supplied values are preserved.

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

    """

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
