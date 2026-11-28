"""Private module to fetch VN stock market data from DNSE/Entrade"""

import json
import math
from datetime import datetime, timedelta, timezone

from . import _utils, models, utils

__all__ = ["get_info", "get_quote"]

_BASE_URL = "https://api.dnse.com.vn/"
_MARKET_TIMEZONE = timezone(timedelta(hours=7), "Asia/Ho_Chi_Minh")
_SECONDS_PER_DAY = 24 * 60 * 60


async def get_info(ticker: str) -> models.SymbolInfo | None:
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
    symbol = utils.normalize_ticker(ticker)

    response = await _utils.fetch_url_async(
        f"{_BASE_URL.rstrip('/')}/market-api/tickers?symbol={symbol}"
    )
    if response.status == 404:
        return None
    if not response.is_successful():
        raise RuntimeError(f"DNSE ticker lookup returned HTTP {response.status}")

    payload = json.loads(response.content)
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
        return models.SymbolInfo(
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


async def get_quote(ticker: str) -> models.StockQuote | None:
    """Retrieve a VN stock symbol quote from DNSE/Entrade.

    Args:
        ticker (str): CODE, EXCHANGE:CODE, or CODE.VN, such as fpt,
            HOSE:FPT, or FPT.VN. Case and surrounding whitespace are ignored.
            CODE may contain single dots between nonempty ASCII alphanumeric
            parts, such as ABC.Z, but must not end with .VN. Exchange prefixes
            contain only ASCII letters and cannot be combined with .VN.

    Returns:
        vfinance.models.StockQuote | None: The latest available one-minute
            quote, with an Asia/Ho_Chi_Minh timestamp, prices in VND, and
            traded-unit volume. The reported listing exchange is uppercase.
            A null closing price remains None. Returns None for an invalid or
            missing symbol, an error response without the required quote fields,
            an unavailable listing profile, or no quote within today and the
            previous 14 days.

    Raises:
        TypeError: ticker is not a string.
        RuntimeError: The HTTP lookup fails, other than HTTP 404 or an error
            response without the required quote fields.
        json.JSONDecodeError: A successful HTTP response is not valid JSON.
        ValueError: ticker is empty or malformed, the volume array is missing,
            quote arrays are inconsistent, a timestamp, price, volume, or
            listing field is invalid, pagination cannot move backward, or
            the HTTP content encoding is unsupported.
        urllib.error.URLError: A connection or redirect failure occurs.
        OSError: A socket timeout, response-reading failure, or invalid gzip
            response occurs.
        http.client.HTTPException: An HTTP response is invalid or incomplete.
        EOFError: A compressed response is truncated.
        zlib.error: A compressed response cannot be decoded.
        asyncio.CancelledError: The task awaiting this lookup is canceled.
    """
    symbol = utils.normalize_ticker(ticker)
    now = datetime.now(_MARKET_TIMEZONE)
    start = int(now.replace(hour=0, minute=0, second=0, microsecond=0).timestamp())
    end = int(now.timestamp())
    earliest_start = start - 14 * _SECONDS_PER_DAY
    fields = ("t", "o", "h", "l", "c", "v")

    while True:
        if start < earliest_start:
            return None
        response = await _utils.fetch_url_async(
            f"{_BASE_URL.rstrip('/')}/chart-api/v2/ohlcs/stock"
            f"?symbol={symbol}&resolution=1&from={start}&to={end}"
        )
        if response.status == 404:
            return None
        try:
            payload = json.loads(response.content)
        except json.JSONDecodeError:
            if not response.is_successful():
                raise RuntimeError(
                    f"DNSE quote lookup returned HTTP {response.status}"
                ) from None
            raise
        if not isinstance(payload, dict) or any(
            field not in payload for field in ("t", "o", "h", "l", "c")
        ):
            return None
        if not response.is_successful():
            raise RuntimeError(f"DNSE quote lookup returned HTTP {response.status}")
        if "v" not in payload:
            raise ValueError("DNSE quote response must contain a volume array")

        columns = [payload[field] for field in fields]
        if all(column is None for column in columns):
            return None
        if any(not isinstance(column, list) for column in columns):
            raise ValueError("DNSE quote fields must be arrays")
        if any(len(column) != len(columns[0]) for column in columns):
            raise ValueError("DNSE quote arrays must have matching lengths")
        if columns[0]:
            break

        next_time = _get_quote_number(payload.get("nextTime"), "nextTime")
        if next_time != int(next_time):
            raise ValueError("DNSE quote nextTime must use whole seconds")
        next_time = int(next_time)
        if next_time == 0 or next_time < earliest_start:
            return None
        if next_time >= end:
            raise ValueError("DNSE quote pagination must move backward")
        end = next_time
        start -= _SECONDS_PER_DAY
        # Reversed ranges produce the same null arrays as invalid symbols.
        while start > end:
            start -= _SECONDS_PER_DAY

    timestamp = _get_quote_number(columns[0][-1], "t")
    try:
        quote_time = datetime.fromtimestamp(timestamp, tz=_MARKET_TIMEZONE)
    except (OverflowError, OSError) as error:
        raise ValueError("DNSE quote timestamp is out of range") from error
    open_price = _get_quote_price(columns[1][-1], "o")
    high_price = _get_quote_price(columns[2][-1], "h")
    low_price = _get_quote_price(columns[3][-1], "l")
    close = (
        _get_quote_price(columns[4][-1], "c") if columns[4][-1] is not None else None
    )
    volume = _get_quote_number(columns[5][-1], "v")
    if volume != int(volume):
        raise ValueError("DNSE quote volume must use whole traded units")

    info = await get_info(symbol)
    if info is None:
        return None
    return models.StockQuote(
        timestamp=quote_time,
        exchange=info.exchange,
        symbol=symbol,
        open=open_price,
        high=high_price,
        low=low_price,
        volume=int(volume),
        close=close,
    )


def _get_quote_number(value: object, field: str) -> int | float:
    if isinstance(value, bool) or not isinstance(value, (int, float)) or value < 0:
        raise ValueError(f"DNSE quote field {field!r} must be a non-negative number")
    try:
        finite = math.isfinite(value)
    except OverflowError:
        finite = False
    if not finite:
        raise ValueError(f"DNSE quote field {field!r} must be finite")
    return value


def _get_quote_price(value: object, field: str) -> float:
    price = float(_get_quote_number(value, field)) * 1000
    if not math.isfinite(price):
        raise ValueError(f"DNSE quote price {field!r} is out of range")
    return price
