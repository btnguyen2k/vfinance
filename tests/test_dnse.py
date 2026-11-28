import asyncio
import json
from datetime import datetime, timedelta, tzinfo
from unittest.mock import AsyncMock, call
from urllib.error import URLError

import pytest

from vfinance import _dnse
from vfinance._utils import HttpResponse
from vfinance.models import StockQuote, SymbolInfo


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


@pytest.fixture
def quote_now(monkeypatch: pytest.MonkeyPatch) -> datetime:
    now = datetime(2026, 11, 30, 10, 30, 0, 654321, tzinfo=_dnse._MARKET_TIMEZONE)

    class FixedDateTime(datetime):
        @classmethod
        def now(cls, tz: tzinfo | None = None) -> datetime:
            return now.astimezone(tz) if tz is not None else now.replace(tzinfo=None)

    monkeypatch.setattr(_dnse, "datetime", FixedDateTime)
    return now


@pytest.fixture
def quote_payload(quote_now: datetime) -> dict[str, object]:
    end = int(quote_now.timestamp())
    return {
        "t": [end - 120, end - 60],
        "o": [44.0, 44.6],
        "h": [44.4, 44.9],
        "l": [43.9, 44.5],
        "c": [44.3, 44.7],
        "v": [123, 456.0],
        "nextTime": 0,
    }


@pytest.fixture
def quote_transport(
    monkeypatch: pytest.MonkeyPatch, quote_payload: dict[str, object]
) -> AsyncMock:
    fetch = AsyncMock(
        return_value=HttpResponse(status=200, content=json.dumps(quote_payload))
    )
    monkeypatch.setattr(_dnse._utils, "fetch_url_async", fetch)
    return fetch


@pytest.fixture
def quote_profile(monkeypatch: pytest.MonkeyPatch) -> AsyncMock:
    lookup = AsyncMock(
        return_value=SymbolInfo(
            exchange="HOSE", symbol="FPT", name="CTCP FPT", overview=""
        )
    )
    monkeypatch.setattr(_dnse, "get_info", lookup)
    return lookup


@pytest.mark.parametrize(
    ("ticker", "symbol"),
    [("fpt", "FPT"), (" HNX:Fpt ", "FPT"), ("FPT.vn", "FPT"), ("ABC.Z.VN", "ABC.Z")],
)
def test_get_quote_reads_the_latest_bar_in_vnd_and_market_time(
    ticker: str,
    symbol: str,
    quote_now: datetime,
    quote_transport: AsyncMock,
    quote_profile: AsyncMock,
) -> None:
    result = asyncio.run(_dnse.get_quote(ticker))
    end = int(quote_now.timestamp())
    start = int(
        quote_now.replace(hour=0, minute=0, second=0, microsecond=0).timestamp()
    )

    assert result == StockQuote(
        timestamp=datetime.fromtimestamp(end - 60, tz=_dnse._MARKET_TIMEZONE),
        exchange="HOSE",
        symbol=symbol,
        open=44_600.0,
        high=44_900.0,
        low=44_500.0,
        volume=456,
        close=44_700.0,
    )
    quote_transport.assert_awaited_once_with(
        f"https://api.dnse.com.vn/chart-api/v2/ohlcs/stock"
        f"?symbol={symbol}&resolution=1&from={start}&to={end}"
    )
    quote_profile.assert_awaited_once_with(symbol)
    assert result.timestamp.utcoffset() == timedelta(hours=7)
    assert result.timestamp_str == "2026-11-30T10:29:00+07:00"


@pytest.mark.parametrize("has_history", [False, True])
def test_get_quote_searches_back_over_non_trading_days_without_reversed_ranges(
    has_history: bool,
    quote_now: datetime,
    quote_payload: dict[str, object],
    quote_transport: AsyncMock,
    quote_profile: AsyncMock,
) -> None:
    history_end = datetime(2026, 11, 27, 15, tzinfo=_dnse._MARKET_TIMEZONE)
    empty = {field: [] for field in ("t", "o", "h", "l", "c", "v")}
    if has_history:
        history = {
            **quote_payload,
            "t": [
                int(history_end.timestamp()) - 960,
                int(history_end.timestamp()) - 900,
            ],
        }
    else:
        history = {**empty, "nextTime": 0}
    quote_transport.side_effect = [
        HttpResponse(
            status=200,
            content=json.dumps({**empty, "nextTime": int(history_end.timestamp())}),
        ),
        HttpResponse(status=200, content=json.dumps(history)),
    ]

    result = asyncio.run(_dnse.get_quote("FPT"))

    start = int(
        quote_now.replace(hour=0, minute=0, second=0, microsecond=0).timestamp()
    )
    history_start = int(history_end.replace(hour=0).timestamp())
    prefix = "https://api.dnse.com.vn/chart-api/v2/ohlcs/stock?symbol=FPT&resolution=1"
    assert quote_transport.await_args_list == [
        call(f"{prefix}&from={start}&to={int(quote_now.timestamp())}"),
        call(f"{prefix}&from={history_start}&to={int(history_end.timestamp())}"),
    ]
    if has_history:
        assert result is not None
        assert result.timestamp == history_end - timedelta(minutes=15)
        assert result.close == 44_700.0
        quote_profile.assert_awaited_once_with("FPT")
    else:
        assert result is None
        quote_profile.assert_not_awaited()


@pytest.mark.parametrize(
    ("status", "payload"),
    [
        (404, "Not found"),
        (400, {"status": 400, "code": "BAD_REQUEST", "message": "invalid symbol"}),
        (200, {"status": 400, "code": "BAD_REQUEST", "message": "invalid symbol"}),
        (400, {"status": 400, "code": "BAD_REQUEST", "message": "invalid resolution"}),
        (200, {"status": 503, "message": "Upstream error"}),
        (503, {"message": "Service unavailable"}),
        (200, []),
        (200, {}),
        (200, {field: None for field in ("t", "o", "h", "l", "c", "v")}),
        (
            200,
            {**{field: [] for field in ("t", "o", "h", "l", "c", "v")}, "nextTime": 0},
        ),
    ],
)
def test_get_quote_returns_none_when_the_symbol_or_history_is_unavailable(
    status: int,
    payload: object,
    quote_transport: AsyncMock,
    quote_profile: AsyncMock,
) -> None:
    quote_transport.return_value = HttpResponse(
        status=status,
        content=payload if isinstance(payload, str) else json.dumps(payload),
    )

    assert asyncio.run(_dnse.get_quote("UNKNOWN")) is None
    quote_transport.assert_awaited_once()
    quote_profile.assert_not_awaited()


@pytest.mark.parametrize("field", ["t", "o", "h", "l", "c"])
def test_get_quote_returns_none_for_any_missing_required_response_field(
    field: str,
    quote_payload: dict[str, object],
    quote_transport: AsyncMock,
    quote_profile: AsyncMock,
) -> None:
    quote_payload.pop(field)
    quote_transport.return_value = HttpResponse(
        status=200, content=json.dumps(quote_payload)
    )

    assert asyncio.run(_dnse.get_quote("FPT")) is None
    quote_transport.assert_awaited_once()
    quote_profile.assert_not_awaited()


@pytest.mark.parametrize("days_back", [14, 15])
def test_get_quote_limits_cursor_jumps_to_fourteen_previous_days(
    days_back: int,
    quote_now: datetime,
    quote_payload: dict[str, object],
    quote_transport: AsyncMock,
    quote_profile: AsyncMock,
) -> None:
    today = quote_now.replace(hour=0, minute=0, second=0, microsecond=0)
    history_start = today - timedelta(days=days_back)
    history_end = history_start + timedelta(hours=15)
    empty = {field: [] for field in ("t", "o", "h", "l", "c", "v")}
    responses = [
        HttpResponse(
            status=200,
            content=json.dumps({**empty, "nextTime": int(history_end.timestamp())}),
        )
    ]
    if days_back == 14:
        responses.append(
            HttpResponse(
                status=200,
                content=json.dumps(
                    {
                        **quote_payload,
                        "t": [
                            int(history_end.timestamp()) - 960,
                            int(history_end.timestamp()) - 900,
                        ],
                    }
                ),
            )
        )
    quote_transport.side_effect = responses

    result = asyncio.run(_dnse.get_quote("FPT"))

    if days_back == 14:
        assert result is not None
        assert result.timestamp == history_end - timedelta(minutes=15)
        prefix = (
            "https://api.dnse.com.vn/chart-api/v2/ohlcs/stock?symbol=FPT&resolution=1"
        )
        assert quote_transport.await_args_list[-1] == call(
            f"{prefix}&from={int(history_start.timestamp())}&to={int(history_end.timestamp())}"
        )
        assert quote_transport.await_count == 2
        quote_profile.assert_awaited_once_with("FPT")
    else:
        assert result is None
        quote_transport.assert_awaited_once()
        quote_profile.assert_not_awaited()


def test_get_quote_stops_after_fourteen_days_of_empty_history(
    quote_now: datetime,
    quote_transport: AsyncMock,
    quote_profile: AsyncMock,
) -> None:
    today = quote_now.replace(hour=0, minute=0, second=0, microsecond=0)
    empty = {field: [] for field in ("t", "o", "h", "l", "c", "v")}
    quote_transport.side_effect = [
        HttpResponse(
            status=200,
            content=json.dumps(
                {
                    **empty,
                    "nextTime": int(
                        (today - timedelta(days=day) + timedelta(hours=15)).timestamp()
                    ),
                }
            ),
        )
        for day in range(1, 16)
    ]

    assert asyncio.run(_dnse.get_quote("FPT")) is None
    assert quote_transport.await_count == 15
    last_start = int((today - timedelta(days=14)).timestamp())
    assert f"&from={last_start}&" in quote_transport.await_args_list[-1].args[0]
    quote_profile.assert_not_awaited()


@pytest.mark.parametrize("close", [None, 0.0])
def test_get_quote_preserves_null_and_zero_closing_prices(
    close: float | None,
    quote_payload: dict[str, object],
    quote_transport: AsyncMock,
    quote_profile: AsyncMock,
) -> None:
    quote_payload["c"] = [44.3, close]
    quote_transport.return_value = HttpResponse(
        status=200, content=json.dumps(quote_payload)
    )

    result = asyncio.run(_dnse.get_quote("FPT"))

    assert result is not None
    assert result.close == close
    assert result.open == 44_600.0


@pytest.mark.parametrize(
    ("ticker", "error_type"), [("HOSE:FPT.VN", ValueError), (None, TypeError)]
)
def test_get_quote_rejects_invalid_input_before_fetching(
    ticker: object,
    error_type: type[Exception],
    quote_transport: AsyncMock,
    quote_profile: AsyncMock,
) -> None:
    with pytest.raises(error_type):
        asyncio.run(_dnse.get_quote(ticker))  # type: ignore[arg-type]

    quote_transport.assert_not_awaited()
    quote_profile.assert_not_awaited()


@pytest.mark.parametrize(
    ("status", "payload"),
    [
        (400, "Bad request"),
        (503, "Upstream error"),
    ],
)
def test_get_quote_propagates_server_failures(
    status: int,
    payload: object,
    quote_transport: AsyncMock,
    quote_profile: AsyncMock,
) -> None:
    quote_transport.return_value = HttpResponse(
        status=status,
        content=payload if isinstance(payload, str) else json.dumps(payload),
    )

    with pytest.raises(RuntimeError, match="DNSE quote"):
        asyncio.run(_dnse.get_quote("FPT"))
    quote_profile.assert_not_awaited()


def test_get_quote_propagates_invalid_json(
    quote_transport: AsyncMock, quote_profile: AsyncMock
) -> None:
    quote_transport.return_value = HttpResponse(status=200, content="{invalid")

    with pytest.raises(json.JSONDecodeError):
        asyncio.run(_dnse.get_quote("FPT"))
    quote_profile.assert_not_awaited()


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("c", None),
        ("v", [123]),
        ("o", [44.0, "44.6"]),
        ("h", [44.4, float("nan")]),
        ("v", [123, 1.5]),
        ("t", [0, True]),
        ("t", [0, 1e300]),
        ("o", [44.0, 1e308]),
    ],
)
def test_get_quote_rejects_malformed_arrays_and_quote_values(
    field: str,
    value: object,
    quote_payload: dict[str, object],
    quote_transport: AsyncMock,
    quote_profile: AsyncMock,
) -> None:
    quote_payload[field] = value
    quote_transport.return_value = HttpResponse(
        status=200, content=json.dumps(quote_payload)
    )

    with pytest.raises(ValueError):
        asyncio.run(_dnse.get_quote("FPT"))
    quote_profile.assert_not_awaited()


@pytest.mark.parametrize("next_time", [None, 1.5, "now"])
def test_get_quote_rejects_invalid_or_non_progressing_pagination(
    next_time: object,
    quote_now: datetime,
    quote_transport: AsyncMock,
    quote_profile: AsyncMock,
) -> None:
    if next_time == "now":
        next_time = int(quote_now.timestamp())
    quote_transport.return_value = HttpResponse(
        status=200,
        content=json.dumps(
            {
                **{field: [] for field in ("t", "o", "h", "l", "c", "v")},
                "nextTime": next_time,
            }
        ),
    )

    with pytest.raises(ValueError, match="DNSE quote"):
        asyncio.run(_dnse.get_quote("FPT"))
    quote_transport.assert_awaited_once()
    quote_profile.assert_not_awaited()


@pytest.mark.parametrize(
    "error",
    [
        URLError("Connection failed"),
        TimeoutError("Request timed out"),
        asyncio.CancelledError(),
    ],
)
def test_get_quote_propagates_transport_failures_and_cancellation(
    error: BaseException, quote_transport: AsyncMock, quote_profile: AsyncMock
) -> None:
    quote_transport.side_effect = error

    with pytest.raises(type(error)) as raised:
        asyncio.run(_dnse.get_quote("FPT"))
    assert raised.value is error
    quote_profile.assert_not_awaited()


def test_get_quote_returns_none_without_a_listing_profile(
    quote_transport: AsyncMock, quote_profile: AsyncMock
) -> None:
    quote_profile.return_value = None

    assert asyncio.run(_dnse.get_quote("FPT")) is None
    quote_transport.assert_awaited_once()
    quote_profile.assert_awaited_once_with("FPT")


def test_get_quote_propagates_listing_lookup_failures(
    quote_transport: AsyncMock, quote_profile: AsyncMock
) -> None:
    error = TimeoutError("Listing lookup timed out")
    quote_profile.side_effect = error

    with pytest.raises(TimeoutError) as raised:
        asyncio.run(_dnse.get_quote("FPT"))
    assert raised.value is error
    quote_transport.assert_awaited_once()
