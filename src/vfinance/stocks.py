"""Vietnamese stock-market symbol information from public sources."""

import logging as _logging

from . import _cache, _dnse
from . import models as _models
from . import utils as _ticker_utils

__all__ = ["get_info"]

_logger = _logging.getLogger(__name__)
_INFO_CACHE_DOMAIN = "SYMBOL-INFO"
_INFO_CACHE_TTL = 24 * 60 * 60


async def get_info(ticker: str, **kwargs: object) -> _models.SymbolInfo | None:
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
        key = _ticker_utils.normalize_ticker(ticker)
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
