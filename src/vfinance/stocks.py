"""Vietnamese stock-market symbol information from public sources."""

import logging

from . import _cache, _dnse, models, utils

__all__ = ["get_info", "get_quote"]

_logger = logging.getLogger(__name__)
_INFO_CACHE_DOMAIN = "SYMBOL-INFO"
_INFO_CACHE_TTL = 24 * 60 * 60
_QUOTE_CACHE_DOMAIN = "STOCK-QUOTE"
_QUOTE_CACHE_TTL = 5 * 60


async def get_info(ticker: str, **kwargs: object) -> models.SymbolInfo | None:
    """Retrieve a VN stock symbol profile.

    Args:
        ticker (str): CODE, EXCHANGE:CODE, or CODE.VN, such as fpt,
            HOSE:FPT, or FPT.VN. Case and surrounding whitespace are ignored.
            CODE may contain single dots between nonempty ASCII alphanumeric
            parts, such as ABC.Z, but must not end with .VN. Exchange prefixes
            contain only ASCII letters and cannot be combined with .VN.
        **kwargs (object): Optional lookup preferences. Supported option:
            raise_on_error (object): Supplying this keyword requests exceptions
                on lookup failures instead of None, regardless of its value.
                Omit it to receive None on failure. Other keywords are ignored.

    Returns:
        vfinance.models.SymbolInfo | None: An immutable profile containing the
            symbol, reported exchange, company names, instrument type, index
            membership, and available GICS classifications. Returns None when
            the symbol is absent. Invalid input and lookup failures also return
            None unless raise_on_error is supplied.

    Raises:
        TypeError: ticker is not a string and raise_on_error is supplied.
        ValueError: ticker is malformed and raise_on_error is supplied.
        Exception: Another lookup failure occurs and raise_on_error is supplied.
            The original exception is raised.
        asyncio.CancelledError: The task awaiting this lookup is canceled.
    """
    try:
        key = utils.normalize_ticker(ticker)
        info = _cache.get(_INFO_CACHE_DOMAIN, key)
        if info is not None:
            return info

        info = await _dnse.get_info(ticker)
        if info is not None:
            _cache.set(_INFO_CACHE_DOMAIN, key, info, ttl=_INFO_CACHE_TTL)
        return info
    except Exception as error:
        _logger.exception(
            "Failed to retrieve symbol information for ticker %r: %s: %s",
            ticker,
            type(error).__name__,
            error,
        )
        if "raise_on_error" in kwargs:
            raise
        return None


async def get_quote(ticker: str, **kwargs: object) -> models.StockQuote | None:
    """Retrieve the latest available one-minute VN stock quote.

    Args:
        ticker (str): CODE, EXCHANGE:CODE, or CODE.VN, such as fpt,
            HOSE:FPT, or FPT.VN. Case and surrounding whitespace are ignored.
            CODE may contain single dots between nonempty ASCII alphanumeric
            parts, such as ABC.Z, but must not end with .VN. Exchange prefixes
            contain only ASCII letters and cannot be combined with .VN.
        **kwargs (object): Optional lookup preferences. Supported option:
            raise_on_error (object): Supplying this keyword requests exceptions
                on lookup failures instead of None, regardless of its value.
                Omit it to receive None on failure. Other keywords are ignored.

    Returns:
        vfinance.models.StockQuote | None: An immutable quote containing its
            date and time in Asia/Ho_Chi_Minh, reported listing exchange, symbol,
            OHLC prices in VND, and volume in traded units. The closing price
            may be None if it has not been finalized. Returns None when a quote
            is unavailable. Invalid input and lookup failures also return None
            unless raise_on_error is supplied.

    Raises:
        TypeError: ticker is not a string and raise_on_error is supplied.
        ValueError: ticker is malformed or quote values are invalid and
            raise_on_error is supplied.
        Exception: Another lookup failure occurs and raise_on_error is supplied.
            The original exception is raised.
        asyncio.CancelledError: The task awaiting this lookup is canceled.
    """
    try:
        key = utils.normalize_ticker(ticker)
        quote = _cache.get(_QUOTE_CACHE_DOMAIN, key)
        if quote is not None:
            return quote

        quote = await _dnse.get_quote(ticker)
        if quote is not None:
            _cache.set(_QUOTE_CACHE_DOMAIN, key, quote, ttl=_QUOTE_CACHE_TTL)
        return quote
    except Exception as error:
        _logger.exception(
            "Failed to retrieve stock quote for ticker %r: %s: %s",
            ticker,
            type(error).__name__,
            error,
        )
        if "raise_on_error" in kwargs:
            raise
        return None
