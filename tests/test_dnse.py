import asyncio
import json
from unittest.mock import AsyncMock
from urllib.error import URLError

import pytest

from vfinance import _dnse
from vfinance._utils import HttpResponse
from vfinance.models import SymbolInfo


@pytest.fixture
def record() -> dict[str, object]:
    return {
        "symbol": "fpt",
        "floor": "hoSe",
        "type": "stock",
        "companyName": "CTCP FPT",
        "companyNameEng": "FPT Corporation",
        "shortName": " FPT ",
        "indexCode": "vn30",
        "industry": "Non-GICS industry",
        "sector": "Non-GICS sector",
        "gicsIndustry": "Ph\u1ea7n m\u1ec1m",
        "gicsSubIndustry": "Ph\u1ea7n m\u1ec1m h\u1ec7 th\u1ed1ng",
        "gicsSector": "C\u00f4ng ngh\u1ec7 th\u00f4ng tin",
        "gicsIndustryGroup": "Ph\u1ea7n m\u1ec1m ",
        "gicsIndustryGroupSlug": "phan-mem-va-dich-vu",
    }


@pytest.fixture
def transport(monkeypatch: pytest.MonkeyPatch, record: dict[str, object]) -> AsyncMock:
    fetch = AsyncMock(
        return_value=HttpResponse(
            status=200,
            content=json.dumps({"data": [{"symbol": "OTHER"}, record]}),
        )
    )
    monkeypatch.setattr(_dnse._utils, "fetch_url_async", fetch)
    return fetch


@pytest.mark.parametrize("ticker", ["fpt", " HOSE:Fpt ", "FPT.vn"])
def test_get_info_reads_matching_profile(ticker: str, transport: AsyncMock) -> None:
    result = asyncio.run(_dnse.get_info(ticker))

    assert result == SymbolInfo(
        exchange="HOSE",
        symbol="FPT",
        name="CTCP FPT",
        overview="",
        english_name="FPT Corporation",
        short_name=" FPT ",
        symbol_type="STOCK",
        index_code="VN30",
        industry="Ph\u1ea7n m\u1ec1m",
        sub_industry="Ph\u1ea7n m\u1ec1m h\u1ec7 th\u1ed1ng",
        sector="C\u00f4ng ngh\u1ec7 th\u00f4ng tin",
        industry_group="Ph\u1ea7n m\u1ec1m ",
        industry_group_slug="phan-mem-va-dich-vu",
    )
    transport.assert_awaited_once_with(
        "https://api.dnse.com.vn/market-api/tickers?symbol=FPT"
    )


@pytest.mark.parametrize("ticker", ["ABC.Z.VN", "HOSE:ABC.Z"])
def test_get_info_preserves_dotted_codes(
    ticker: str, record: dict[str, object], transport: AsyncMock
) -> None:
    record["symbol"] = "ABC.Z"
    record["floor"] = "UPCoM"
    transport.return_value = HttpResponse(
        status=200, content=json.dumps({"data": [record]})
    )

    result = asyncio.run(_dnse.get_info(ticker))

    assert result is not None
    assert result.symbol == "ABC.Z"
    assert result.exchange == "UPCOM"
    transport.assert_awaited_once_with(
        "https://api.dnse.com.vn/market-api/tickers?symbol=ABC.Z"
    )


def test_get_info_preserves_empty_index_and_optional_text(transport: AsyncMock) -> None:
    transport.return_value = HttpResponse(
        status=200,
        content=json.dumps(
            {
                "data": [
                    {
                        "symbol": "E1VFVN30",
                        "floor": "hose",
                        "type": "etf",
                        "companyName": "Example ETF",
                        "shortName": "",
                        "indexCode": "",
                        "gicsIndustry": "",
                        "gicsIndustryGroupSlug": None,
                    }
                ]
            }
        ),
    )

    assert asyncio.run(_dnse.get_info("E1VFVN30.VN")) == SymbolInfo(
        exchange="HOSE",
        symbol="E1VFVN30",
        name="Example ETF",
        overview="",
        short_name="",
        symbol_type="ETF",
        index_code="",
        industry="",
    )


def test_get_info_handles_absent_optional_fields(transport: AsyncMock) -> None:
    transport.return_value = HttpResponse(
        status=200,
        content=json.dumps(
            {"data": [{"symbol": "FPT", "floor": "HOSE", "companyName": "CTCP FPT"}]}
        ),
    )

    assert asyncio.run(_dnse.get_info("FPT")) == SymbolInfo(
        exchange="HOSE", symbol="FPT", name="CTCP FPT", overview=""
    )


@pytest.mark.parametrize("ticker", ["HOSE:FPT.VN", "ABC.VN.VN", "ABC..Z"])
def test_get_info_propagates_invalid_ticker_errors(
    ticker: str, transport: AsyncMock
) -> None:
    with pytest.raises(ValueError, match="Invalid ticker format"):
        asyncio.run(_dnse.get_info(ticker))
    transport.assert_not_awaited()


def test_get_info_rejects_non_string_input(transport: AsyncMock) -> None:
    with pytest.raises(TypeError, match="ticker must be a string"):
        asyncio.run(_dnse.get_info(None))  # type: ignore[arg-type]
    transport.assert_not_awaited()


@pytest.mark.parametrize("data", [[], [{"symbol": "OTHER"}]])
def test_get_info_returns_none_without_a_matching_symbol(
    data: list[dict[str, object]], transport: AsyncMock
) -> None:
    transport.return_value = HttpResponse(
        status=200, content=json.dumps({"data": data})
    )

    assert asyncio.run(_dnse.get_info("UNKNOWN")) is None


def test_get_info_returns_none_for_http_not_found(transport: AsyncMock) -> None:
    transport.return_value = HttpResponse(status=404, content="Not found")

    assert asyncio.run(_dnse.get_info("UNKNOWN")) is None


@pytest.mark.parametrize("status", [403, 429, 503])
def test_get_info_does_not_hide_http_failures(
    status: int, transport: AsyncMock
) -> None:
    transport.return_value = HttpResponse(status=status, content="Upstream error")

    with pytest.raises(RuntimeError, match=f"HTTP {status}"):
        asyncio.run(_dnse.get_info("FPT"))


def test_get_info_propagates_invalid_json(transport: AsyncMock) -> None:
    transport.return_value = HttpResponse(status=200, content="{invalid")

    with pytest.raises(json.JSONDecodeError):
        asyncio.run(_dnse.get_info("FPT"))


@pytest.mark.parametrize(
    "payload",
    [[], {}, {"data": {}}, {"data": [None]}, {"data": [{"symbol": None}]}],
)
def test_get_info_rejects_invalid_response_structures(
    payload: object, transport: AsyncMock
) -> None:
    transport.return_value = HttpResponse(status=200, content=json.dumps(payload))

    with pytest.raises(ValueError, match="DNSE"):
        asyncio.run(_dnse.get_info("FPT"))


@pytest.mark.parametrize(
    "updates",
    [
        {"floor": " "},
        {"companyName": None},
        {"type": 123},
        {"gicsSector": ["Unexpected list"]},
    ],
)
def test_get_info_rejects_invalid_profile_fields(
    updates: dict[str, object], record: dict[str, object], transport: AsyncMock
) -> None:
    record.update(updates)
    transport.return_value = HttpResponse(
        status=200, content=json.dumps({"data": [record]})
    )

    with pytest.raises(ValueError, match="DNSE"):
        asyncio.run(_dnse.get_info("FPT"))


@pytest.mark.parametrize(
    "error", [URLError("Connection failed"), TimeoutError("Request timed out")]
)
def test_get_info_propagates_transport_errors(
    error: Exception, transport: AsyncMock
) -> None:
    transport.side_effect = error

    with pytest.raises(type(error)) as raised:
        asyncio.run(_dnse.get_info("FPT"))
    assert raised.value is error


def test_get_info_propagates_cancellation(transport: AsyncMock) -> None:
    transport.side_effect = asyncio.CancelledError

    with pytest.raises(asyncio.CancelledError):
        asyncio.run(_dnse.get_info("FPT"))
