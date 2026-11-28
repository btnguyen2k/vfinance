import asyncio
import logging
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, Mock

import pytest

from vfinance import _cache, stocks
from vfinance.models import StockQuote, SymbolInfo


@pytest.fixture(autouse=True)
def reset_cache_domains(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(_cache, "_domains", {})


@pytest.fixture
def lookup(monkeypatch: pytest.MonkeyPatch) -> AsyncMock:
    lookup = AsyncMock()
    monkeypatch.setattr(stocks._dnse, "get_info", lookup)
    return lookup


@pytest.fixture
def profile() -> SymbolInfo:
    return SymbolInfo(
        exchange="HOSE",
        symbol="FPT",
        name="CTCP FPT",
        overview="",
        symbol_type="STOCK",
        index_code="VN30",
    )


@pytest.mark.parametrize("ticker", ["FPT", "hose:fpt", "FPT.VN"])
def test_get_info_returns_the_adapter_profile(
    ticker: str, lookup: AsyncMock, profile: SymbolInfo
) -> None:
    lookup.return_value = profile

    assert asyncio.run(stocks.get_info(ticker)) is profile
    lookup.assert_awaited_once_with(ticker)


@pytest.mark.parametrize("code", ["FPT", "ABC.Z"])
def test_get_info_shares_cached_profiles_for_normalized_tickers(
    code: str, lookup: AsyncMock, profile: SymbolInfo
) -> None:
    profile = profile.model_copy(update={"symbol": code})
    lookup.return_value = profile
    first_ticker = f" hose:{code.lower()} "

    for ticker in [first_ticker, f"{code}.VN", code]:
        assert asyncio.run(stocks.get_info(ticker)) is profile

    lookup.assert_awaited_once_with(first_ticker)
    assert _cache.get("SYMBOL-INFO", code) is profile


def test_get_info_refreshes_after_24_hours(
    monkeypatch: pytest.MonkeyPatch, lookup: AsyncMock, profile: SymbolInfo
) -> None:
    clock = Mock(return_value=100.0)
    monkeypatch.setattr(_cache, "monotonic", clock)
    updated = profile.model_copy(update={"name": "Updated company name"})
    lookup.side_effect = [profile, updated]

    assert asyncio.run(stocks.get_info("FPT")) is profile
    clock.return_value = 100.0 + 86400 - 1
    assert asyncio.run(stocks.get_info("hose:fpt")) is profile
    clock.return_value = 100.0 + 86400
    assert asyncio.run(stocks.get_info("FPT.VN")) is updated

    assert lookup.await_count == 2


@pytest.mark.parametrize(
    "kwargs", [{}, {"raise_on_error": False}, {"raise_on_error": True}]
)
def test_get_info_returns_none_for_missing_symbols(
    kwargs: dict[str, object], lookup: AsyncMock, caplog: pytest.LogCaptureFixture
) -> None:
    lookup.return_value = None

    assert asyncio.run(stocks.get_info("UNKNOWN", **kwargs)) is None
    lookup.assert_awaited_once_with("UNKNOWN")
    assert not [record for record in caplog.records if record.name == "vfinance.stocks"]


def test_get_info_retries_missing_profiles(
    lookup: AsyncMock, profile: SymbolInfo
) -> None:
    lookup.side_effect = [None, profile]

    assert asyncio.run(stocks.get_info("FPT")) is None
    assert asyncio.run(stocks.get_info("FPT.VN")) is profile
    assert asyncio.run(stocks.get_info("hose:fpt")) is profile

    assert lookup.await_count == 2


@pytest.mark.parametrize(
    "error",
    [
        RuntimeError("HTTP 503"),
        ValueError("Invalid profile"),
        TypeError("ticker must be a string"),
        TimeoutError("Request timed out"),
    ],
)
def test_get_info_returns_none_for_lookup_failures(
    error: Exception,
    lookup: AsyncMock,
    profile: SymbolInfo,
    caplog: pytest.LogCaptureFixture,
) -> None:
    lookup.side_effect = [error, profile]

    assert asyncio.run(stocks.get_info("FPT")) is None
    lookup.assert_awaited_once_with("FPT")
    assert asyncio.run(stocks.get_info("FPT.VN")) is profile
    assert lookup.await_count == 2

    (record,) = [
        record for record in caplog.records if record.name == "vfinance.stocks"
    ]
    assert record.levelno == logging.ERROR
    assert record.exc_info is not None and record.exc_info[1] is error
    assert "FPT" in record.getMessage()
    assert f"{type(error).__name__}: {error}" in record.getMessage()


@pytest.mark.parametrize("raise_on_error", [False, None, 0, "", True, object()])
def test_get_info_raises_the_logged_original_error_when_keyword_is_supplied(
    raise_on_error: object, lookup: AsyncMock, caplog: pytest.LogCaptureFixture
) -> None:
    error = RuntimeError("Lookup failed")
    lookup.side_effect = error

    with pytest.raises(RuntimeError) as raised:
        asyncio.run(stocks.get_info("FPT", raise_on_error=raise_on_error))

    assert raised.value is error
    lookup.assert_awaited_once_with("FPT")
    (record,) = [
        record for record in caplog.records if record.name == "vfinance.stocks"
    ]
    assert record.exc_info is not None and record.exc_info[1] is error
    assert "FPT" in record.getMessage()
    assert "RuntimeError: Lookup failed" in record.getMessage()


def test_get_info_ignores_unrecognized_keywords(lookup: AsyncMock) -> None:
    lookup.side_effect = RuntimeError("Lookup failed")

    assert asyncio.run(stocks.get_info("FPT", unrelated=True)) is None
    lookup.assert_awaited_once_with("FPT")


@pytest.mark.parametrize("ticker", ["", "HOSE:FPT.VN", None, 123])
def test_get_info_rejects_invalid_tickers_before_using_the_cache(
    ticker: object, lookup: AsyncMock, profile: SymbolInfo
) -> None:
    _cache.set("SYMBOL-INFO", "FPT", profile)

    assert asyncio.run(stocks.get_info(ticker)) is None  # type: ignore[arg-type]
    lookup.assert_not_awaited()


@pytest.mark.parametrize(
    ("ticker", "error_type"),
    [
        ("", ValueError),
        ("HOSE:FPT.VN", ValueError),
        (None, TypeError),
        (123, TypeError),
    ],
)
def test_get_info_raises_input_errors_when_keyword_is_supplied(
    ticker: object, error_type: type[Exception], lookup: AsyncMock
) -> None:
    with pytest.raises(error_type):
        asyncio.run(stocks.get_info(ticker, raise_on_error=False))  # type: ignore[arg-type]

    lookup.assert_not_awaited()


@pytest.mark.parametrize("kwargs", [{}, {"raise_on_error": False}])
def test_get_info_propagates_cancellation(
    kwargs: dict[str, object], lookup: AsyncMock, caplog: pytest.LogCaptureFixture
) -> None:
    lookup.side_effect = asyncio.CancelledError

    with pytest.raises(asyncio.CancelledError):
        asyncio.run(stocks.get_info("FPT", **kwargs))
    assert not [record for record in caplog.records if record.name == "vfinance.stocks"]


@pytest.fixture
def quote_lookup(monkeypatch: pytest.MonkeyPatch) -> AsyncMock:
    lookup = AsyncMock()
    monkeypatch.setattr(stocks._dnse, "get_quote", lookup)
    return lookup


@pytest.fixture
def quote() -> StockQuote:
    return StockQuote(
        timestamp=datetime(2026, 11, 27, 15, 0, tzinfo=timezone(timedelta(hours=7))),
        exchange="HOSE",
        symbol="FPT",
        open=119_000.0,
        high=122_000.0,
        low=118_000.0,
        volume=123_456,
    )


@pytest.mark.parametrize("code", ["FPT", "ABC.Z"])
def test_get_quote_returns_and_caches_normalized_quotes(
    code: str, quote_lookup: AsyncMock, quote: StockQuote
) -> None:
    quote = quote.model_copy(update={"symbol": code})
    quote_lookup.return_value = quote
    first_ticker = f" hose:{code.lower()} "

    for ticker in [first_ticker, f"{code}.VN", code]:
        assert asyncio.run(stocks.get_quote(ticker)) is quote

    quote_lookup.assert_awaited_once_with(first_ticker)
    assert _cache.get("STOCK-QUOTE", code) is quote
    assert _cache.get("SYMBOL-INFO", code) is None


def test_get_quote_refreshes_after_five_minutes(
    monkeypatch: pytest.MonkeyPatch, quote_lookup: AsyncMock, quote: StockQuote
) -> None:
    clock = Mock(return_value=100.0)
    monkeypatch.setattr(_cache, "monotonic", clock)
    updated = quote.model_copy(
        update={"timestamp": quote.timestamp + timedelta(minutes=5)}
    )
    quote_lookup.side_effect = [quote, updated]

    assert asyncio.run(stocks.get_quote("FPT")) is quote
    clock.return_value = 100.0 + 300 - 1
    assert asyncio.run(stocks.get_quote("HOSE:FPT")) is quote
    clock.return_value = 100.0 + 300
    assert asyncio.run(stocks.get_quote("FPT.VN")) is updated
    assert quote_lookup.await_count == 2


@pytest.mark.parametrize("kwargs", [{}, {"raise_on_error": False}])
def test_get_quote_retries_unavailable_quotes_without_logging(
    kwargs: dict[str, object],
    quote_lookup: AsyncMock,
    quote: StockQuote,
    caplog: pytest.LogCaptureFixture,
) -> None:
    quote_lookup.side_effect = [None, quote]

    assert asyncio.run(stocks.get_quote("FPT", **kwargs)) is None
    assert _cache.get("STOCK-QUOTE", "FPT") is None
    assert asyncio.run(stocks.get_quote("FPT.VN", **kwargs)) is quote
    assert quote_lookup.await_count == 2
    assert not [record for record in caplog.records if record.name == "vfinance.stocks"]


@pytest.mark.parametrize(
    "error", [RuntimeError("HTTP 503"), ValueError("Invalid quote")]
)
def test_get_quote_logs_and_retries_lookup_failures(
    error: Exception,
    quote_lookup: AsyncMock,
    quote: StockQuote,
    caplog: pytest.LogCaptureFixture,
) -> None:
    quote_lookup.side_effect = [error, quote]

    assert asyncio.run(stocks.get_quote("FPT", unrelated=True)) is None
    assert _cache.get("STOCK-QUOTE", "FPT") is None
    assert asyncio.run(stocks.get_quote("FPT.VN")) is quote

    (record,) = [
        record for record in caplog.records if record.name == "vfinance.stocks"
    ]
    assert record.levelno == logging.ERROR
    assert record.exc_info is not None and record.exc_info[1] is error
    assert "FPT" in record.getMessage()
    assert f"{type(error).__name__}: {error}" in record.getMessage()


@pytest.mark.parametrize("raise_on_error", [False, None, 0, "", True, object()])
def test_get_quote_raises_the_original_error_when_keyword_is_supplied(
    raise_on_error: object,
    quote_lookup: AsyncMock,
    caplog: pytest.LogCaptureFixture,
) -> None:
    error = RuntimeError("Quote lookup failed")
    quote_lookup.side_effect = error

    with pytest.raises(RuntimeError) as raised:
        asyncio.run(stocks.get_quote("FPT", raise_on_error=raise_on_error))

    assert raised.value is error
    quote_lookup.assert_awaited_once_with("FPT")
    (record,) = [
        record for record in caplog.records if record.name == "vfinance.stocks"
    ]
    assert record.exc_info is not None and record.exc_info[1] is error
    assert "FPT" in record.getMessage()
    assert "RuntimeError: Quote lookup failed" in record.getMessage()


@pytest.mark.parametrize(
    ("ticker", "error_type"),
    [
        ("", ValueError),
        ("HOSE:FPT.VN", ValueError),
        (None, TypeError),
        (123, TypeError),
    ],
)
def test_get_quote_rejects_invalid_input_before_using_the_cache(
    ticker: object,
    error_type: type[Exception],
    quote_lookup: AsyncMock,
    quote: StockQuote,
) -> None:
    _cache.set("STOCK-QUOTE", "FPT", quote)

    assert asyncio.run(stocks.get_quote(ticker)) is None  # type: ignore[arg-type]
    with pytest.raises(error_type):
        asyncio.run(stocks.get_quote(ticker, raise_on_error=False))  # type: ignore[arg-type]
    quote_lookup.assert_not_awaited()


@pytest.mark.parametrize("kwargs", [{}, {"raise_on_error": False}])
def test_get_quote_propagates_cancellation(
    kwargs: dict[str, object],
    quote_lookup: AsyncMock,
    caplog: pytest.LogCaptureFixture,
) -> None:
    quote_lookup.side_effect = asyncio.CancelledError

    with pytest.raises(asyncio.CancelledError):
        asyncio.run(stocks.get_quote("FPT", **kwargs))
    assert not [record for record in caplog.records if record.name == "vfinance.stocks"]
