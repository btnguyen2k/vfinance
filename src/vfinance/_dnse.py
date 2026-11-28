"""Private module to fetch VN stock market data from DNSE/Entrade"""

import json as _json

from . import _utils
from . import models as _models
from . import utils as _ticker_utils

_BASE_URL = "https://api.dnse.com.vn/"


async def get_info(ticker: str) -> _models.SymbolInfo | None:
    """Retrieve a VN stock symbol profile from DNSE/Entrade.

    Args:
        ticker (str): CODE, EXCHANGE:CODE, or CODE.VN, such as fpt,
            HOSE:FPT, or FPT.VN. Case and surrounding whitespace are ignored.
            CODE may contain single dots between nonempty ASCII alphanumeric
            parts, such as ABC.Z, but must not end with .VN. Exchange prefixes
            contain only ASCII letters and cannot be combined with .VN.

    Returns:
        vfinance.models.SymbolInfo | None: An immutable profile containing the
            symbol, reported exchange, company names, instrument type, index
            membership, and available GICS classifications. Returns None for
            HTTP 404 or no matching symbol.

    Raises:
        TypeError: ticker is not a string.
        RuntimeError: The lookup returns an HTTP error other than 404.
        json.JSONDecodeError: The response is not valid JSON.
        ValueError: ticker is empty or malformed, the response structure or
            required symbol, exchange, or company name is invalid, a supplied
            profile field is not text, or the HTTP content encoding is unsupported.
        urllib.error.URLError: A connection or redirect failure occurs.
        OSError: A socket timeout, response-reading failure, or invalid gzip
            response occurs.
        http.client.HTTPException: An HTTP response is invalid or incomplete.
        EOFError: A compressed response is truncated.
        zlib.error: A compressed response cannot be decoded.
        asyncio.CancelledError: The task awaiting this lookup is canceled.
    """
    symbol = _ticker_utils.normalize_ticker(ticker)

    response = await _utils.fetch_url_async(
        f"{_BASE_URL.rstrip('/')}/market-api/tickers?symbol={symbol}"
    )
    if response.status == 404:
        return None
    if not response.is_successful():
        raise RuntimeError(f"DNSE ticker lookup returned HTTP {response.status}")

    payload = _json.loads(response.content)
    if not isinstance(payload, dict) or not isinstance(payload.get("data"), list):
        raise ValueError("DNSE ticker response must contain a data list")

    for entry in payload["data"]:
        if not isinstance(entry, dict):
            raise ValueError("DNSE ticker entries must be objects")
        entry_symbol = _get_text(entry, "symbol")
        if not entry_symbol:
            raise ValueError("DNSE ticker entry is missing its symbol")
        if entry_symbol.upper() != symbol:
            continue

        exchange = _get_text(entry, "floor")
        name = _get_text(entry, "companyName")
        if not exchange or not exchange.strip() or not name or not name.strip():
            raise ValueError("DNSE ticker entry is missing its exchange or name")
        symbol_type = _get_text(entry, "type")
        index_code = _get_text(entry, "indexCode")
        return _models.SymbolInfo(
            exchange=exchange.upper(),
            symbol=symbol,
            name=name,
            overview="",
            english_name=_get_text(entry, "companyNameEng"),
            short_name=_get_text(entry, "shortName"),
            symbol_type=symbol_type.upper() if symbol_type is not None else None,
            index_code=index_code.upper() if index_code is not None else None,
            industry=_get_text(entry, "gicsIndustry"),
            sub_industry=_get_text(entry, "gicsSubIndustry"),
            sector=_get_text(entry, "gicsSector"),
            industry_group=_get_text(entry, "gicsIndustryGroup"),
            industry_group_slug=_get_text(entry, "gicsIndustryGroupSlug"),
        )
    return None


def _get_text(entry: dict[str, object], field: str) -> str | None:
    value = entry.get(field)
    if value is None or isinstance(value, str):
        return value
    raise ValueError(f"DNSE ticker field {field!r} must be text or null")
