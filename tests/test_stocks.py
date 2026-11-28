import asyncio
from unittest.mock import AsyncMock

import pytest

from vfinance import stocks
from vfinance.models import SymbolInfo


@pytest.fixture
def lookup(monkeypatch: pytest.MonkeyPatch) -> AsyncMock:
    lookup = AsyncMock()
    monkeypatch.setattr(stocks._dnse, "get_info", lookup)
    return lookup


@pytest.mark.parametrize("ticker", ["FPT", "hose:fpt", "FPT.VN"])
def test_get_info_returns_the_adapter_profile(ticker: str, lookup: AsyncMock) -> None:
    profile = SymbolInfo(
        exchange="HOSE",
        symbol="FPT",
        name="CTCP FPT",
        overview="",
        symbol_type="STOCK",
        index_code="VN30",
    )
    lookup.return_value = profile

    assert asyncio.run(stocks.get_info(ticker)) is profile
    lookup.assert_awaited_once_with(ticker)


def test_get_info_returns_none_for_missing_symbols(lookup: AsyncMock) -> None:
    lookup.return_value = None

    assert asyncio.run(stocks.get_info("UNKNOWN")) is None
    lookup.assert_awaited_once_with("UNKNOWN")


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
    error: Exception, lookup: AsyncMock
) -> None:
    lookup.side_effect = error

    assert asyncio.run(stocks.get_info("FPT")) is None
    lookup.assert_awaited_once_with("FPT")


def test_get_info_propagates_cancellation(lookup: AsyncMock) -> None:
    lookup.side_effect = asyncio.CancelledError

    with pytest.raises(asyncio.CancelledError):
        asyncio.run(stocks.get_info("FPT"))
