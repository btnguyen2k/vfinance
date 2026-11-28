"""Shared instrument profiles for Vietnamese market research."""

from dataclasses import dataclass as _dataclass

__all__ = ["SymbolInfo"]


@_dataclass(frozen=True, slots=True)
class SymbolInfo:
    """Profile details for researching a Vietnamese market instrument.

    Attributes:
        exchange (str): Listing exchange, such as HOSE, HNX, or UPCOM.
        symbol (str): Instrument code without an exchange prefix or .VN suffix.
        name (str): Instrument or company name.
        overview (str): Instrument or issuer description; empty if unavailable.
        english_name (str | None): English-language name, if available.
        short_name (str | None): Abbreviated name, if available.
        address (str | None): Reported contact address, if available.
        phone (str | None): Reported telephone number, if available.
        fax (str | None): Reported fax number, if available.
        email (str | None): Reported email contact, if available.
        website (str | None): Reported website address, if available.
        tax_id (str | None): Tax registration identifier as text, if available.
        business_status (str | None): Reported business-status label, if available.
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

    Notes:
        The first four fields are required constructor arguments. All remaining
        fields default to None. Profiles returned by get_info have uppercase
        exchange and symbol values, an empty overview when absent, and None for
        missing or null optional details. Available instrument types and index
        codes are uppercase; other supplied text may include empty strings.

        Instances are immutable. Direct construction does not normalize or
        validate the supplied values.
    """

    exchange: str
    symbol: str
    name: str
    overview: str
    english_name: str | None = None
    short_name: str | None = None
    address: str | None = None
    phone: str | None = None
    fax: str | None = None
    email: str | None = None
    website: str | None = None
    tax_id: str | None = None
    business_status: str | None = None
    symbol_type: str | None = None
    index_code: str | None = None
    industry: str | None = None
    sub_industry: str | None = None
    sector: str | None = None
    industry_group: str | None = None
    industry_group_slug: str | None = None
