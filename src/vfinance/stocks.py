"""Vietnamese stock-market symbol information from public sources."""

from . import _dnse
from . import models as _models

__all__ = ["get_info"]


async def get_info(ticker: str) -> _models.SymbolInfo | None:
    """Retrieve a VN stock symbol profile.

    Args:
        ticker (str): CODE, EXCHANGE:CODE, or CODE.VN, such as fpt,
            HOSE:FPT, or FPT.VN. Case and surrounding whitespace are ignored.
            CODE may contain single dots between nonempty ASCII alphanumeric
            parts, such as ABC.Z, but must not end with .VN. Exchange prefixes
            contain only ASCII letters and cannot be combined with .VN.

    Returns:
        vfinance.models.SymbolInfo | None: An immutable profile containing the
            symbol, reported exchange, company names, instrument type, index
            membership, and available GICS classifications. Returns None when
            the input is invalid, the symbol is absent, or the lookup fails.

    Raises:
        asyncio.CancelledError: The task awaiting this lookup is canceled.

    Notes:
        Exchange prefixes are discarded, not validated against the listing.
        Exchange, instrument type, and index code are uppercase. Other supplied
        text is unchanged; missing optional details are None and the unavailable
        overview is empty. None does not distinguish an unknown symbol from a
        failed lookup, including non-string input and transport or parsing errors.
        Canceling the await may not stop a lookup already in progress.
    """
    try:
        return await _dnse.get_info(ticker)
    except Exception:
        # TODO log the exception
        return None
