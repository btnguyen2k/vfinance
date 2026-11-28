import json
import subprocess
import sys
from datetime import UTC, datetime, timedelta, timezone
from importlib.resources import files
from pathlib import Path

import pytest
from pydantic import ValidationError

import vfinance
from vfinance.models import StockQuote, SymbolInfo


def test_package_imports_without_repository_on_python_path(tmp_path: Path) -> None:
    result = subprocess.run(
        [
            sys.executable,
            "-I",
            "-c",
            "import vfinance; "
            "import vfinance._cache as cache; "
            "import vfinance._dnse as dnse; "
            "import vfinance.models as models; "
            "import vfinance.stocks as stocks; "
            "from vfinance._dnse import get_quote; "
            "from vfinance.models import StockQuote, SymbolInfo; "
            "from vfinance.stocks import get_info, get_quote; "
            "from vfinance._utils import fetch_url_async; "
            "from vfinance.utils import normalize_ticker; "
            "assert all(getattr(cache, name).__module__ == 'vfinance._cache' "
            "for name in cache.__all__); "
            "assert all(getattr(models, name).__module__ == 'vfinance.models' "
            "for name in models.__all__); "
            "assert all(getattr(dnse, name).__module__ == 'vfinance._dnse' "
            "for name in dnse.__all__); "
            "assert all(getattr(stocks, name).__module__ == 'vfinance.stocks' "
            "for name in stocks.__all__); "
            "cache.set('isolated', 'key', 'value'); "
            "assert cache.get('isolated', 'key') == 'value'; "
            "cache.delete('isolated', 'key'); "
            "assert cache.get('isolated', 'key') is None; "
            "cache.delete_domain('isolated'); "
            "assert not hasattr(cache, 'LRUCache'); "
            "assert not hasattr(vfinance, 'Cache'); "
            "assert not hasattr(dnse, 'SymbolInfo'); "
            "assert not hasattr(stocks, 'SymbolInfo'); "
            "assert not hasattr(vfinance, 'SymbolInfo'); "
            "assert not hasattr(stocks, 'StockQuote'); "
            "assert not hasattr(vfinance, 'StockQuote')",
        ],
        cwd=tmp_path,
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr


def test_symbol_info_omits_removed_profile_fields() -> None:
    info = SymbolInfo(exchange="HOSE", symbol="FPT", name="CTCP FPT", overview="")

    assert {
        "address",
        "phone",
        "fax",
        "email",
        "tax_id",
        "business_status",
    }.isdisjoint(info.model_dump())


@pytest.mark.parametrize("close", [None, 120_000.0])
def test_stock_quote_captures_values_with_an_optional_final_close(
    close: float | None,
) -> None:
    timestamp = datetime(2026, 11, 27, 15, 0, tzinfo=timezone(timedelta(hours=7)))
    kwargs = {} if close is None else {"close": close}

    quote = StockQuote(
        timestamp=timestamp,
        exchange="HOSE",
        symbol="FPT",
        open=119_000.0,
        high=122_000.0,
        low=118_000.0,
        volume=123_456,
        **kwargs,
    )

    assert quote.model_dump() == {
        "timestamp": timestamp,
        "timestamp_str": "2026-11-27T15:00:00+07:00",
        "exchange": "HOSE",
        "symbol": "FPT",
        "open": 119_000.0,
        "high": 122_000.0,
        "low": 118_000.0,
        "volume": 123_456,
        "close": close,
    }


@pytest.mark.parametrize(
    ("timestamp", "expected"),
    [
        (datetime(2026, 11, 27, 15, 0), "2026-11-27T15:00:00"),
        (
            datetime(
                2026, 11, 27, 15, 0, 0, 654321, tzinfo=timezone(timedelta(hours=-4))
            ),
            "2026-11-27T15:00:00.654321-04:00",
        ),
    ],
)
def test_stock_quote_formats_timestamp_as_iso8601(
    timestamp: datetime, expected: str
) -> None:
    quote = StockQuote(
        timestamp=timestamp,
        exchange="HOSE",
        symbol="FPT",
        open=119_000.0,
        high=122_000.0,
        low=118_000.0,
        volume=123_456,
    )

    assert quote.timestamp is timestamp
    assert quote.timestamp_str == expected


def test_stock_quote_derives_timestamp_string_after_replacing_timestamp() -> None:
    quote = StockQuote(
        timestamp=datetime(2026, 11, 27, 15, 0, tzinfo=timezone(timedelta(hours=7))),
        exchange="HOSE",
        symbol="FPT",
        open=119_000.0,
        high=122_000.0,
        low=118_000.0,
        volume=123_456,
    )

    utc_quote = quote.model_copy(update={"timestamp": quote.timestamp.astimezone(UTC)})

    assert quote.timestamp_str == "2026-11-27T15:00:00+07:00"
    assert utc_quote.timestamp_str == "2026-11-27T08:00:00+00:00"
    assert quote == utc_quote


def test_symbol_info_dumps_unicode_json_and_validates_it() -> None:
    info = SymbolInfo(
        exchange="HOSE",
        symbol="FPT",
        name="C\u00f4ng ty FPT",
        overview="",
        short_name=" Fpt ",
        website="",
    )

    encoded = info.model_dump_json()
    payload = json.loads(encoded)

    assert payload == info.model_dump(mode="json")
    assert payload["name"] == info.name
    assert payload["short_name"] == " Fpt "
    assert payload["website"] == ""
    assert payload["english_name"] is None
    assert "\\u" not in encoded
    assert SymbolInfo.model_validate_json(encoded) == info


def test_stock_quote_dumps_iso_json_and_validates_round_trip_data() -> None:
    quote = StockQuote(
        timestamp=datetime(
            2026, 11, 27, 15, 0, 0, 654321, tzinfo=timezone(timedelta(hours=7))
        ),
        exchange="HOSE",
        symbol="FPT",
        open=119_000.0,
        high=122_000.0,
        low=118_000.0,
        volume=123_456,
    )

    payload = json.loads(quote.model_dump_json())
    restored = StockQuote.model_validate_json(quote.model_dump_json(round_trip=True))

    assert payload == quote.model_dump(mode="json")
    assert payload["timestamp"] == "2026-11-27T15:00:00.654321+07:00"
    assert payload["timestamp_str"] == quote.timestamp_str
    assert payload["close"] is None
    assert restored == quote
    assert restored.timestamp_str == quote.timestamp_str


@pytest.mark.parametrize(
    ("field", "value", "error_type"),
    [
        ("name", 123, "string_type"),
        ("website", False, "string_type"),
        ("unexpected", "value", "extra_forbidden"),
    ],
)
def test_symbol_info_rejects_invalid_fields(
    field: str, value: object, error_type: str
) -> None:
    data = {"exchange": "HOSE", "symbol": "FPT", "name": "FPT", "overview": ""}
    data[field] = value

    with pytest.raises(ValidationError) as raised:
        SymbolInfo.model_validate(data)

    assert raised.value.errors()[0]["loc"] == (field,)
    assert raised.value.errors()[0]["type"] == error_type


@pytest.mark.parametrize(
    ("field", "value", "error_type"),
    [
        ("timestamp", "2026-11-27T15:00:00+07:00", "datetime_type"),
        ("open", "119000", "float_type"),
        ("volume", "123456", "int_type"),
        ("volume", True, "int_type"),
        ("high", float("inf"), "finite_number"),
        ("close", float("nan"), "finite_number"),
        ("timestamp_str", "incorrect", "extra_forbidden"),
    ],
)
def test_stock_quote_rejects_invalid_fields(
    field: str, value: object, error_type: str
) -> None:
    data = {
        "timestamp": datetime(2026, 11, 27, 15, 0),
        "exchange": "HOSE",
        "symbol": "FPT",
        "open": 119_000.0,
        "high": 122_000.0,
        "low": 118_000.0,
        "volume": 123_456,
    }
    data[field] = value

    with pytest.raises(ValidationError) as raised:
        StockQuote.model_validate(data)

    assert raised.value.errors()[0]["loc"] == (field,)
    assert raised.value.errors()[0]["type"] == error_type


@pytest.mark.parametrize(
    "model",
    [
        SymbolInfo(exchange="HOSE", symbol="FPT", name="FPT", overview=""),
        StockQuote(
            timestamp=datetime(2026, 11, 27, 15, 0),
            exchange="HOSE",
            symbol="FPT",
            open=119_000.0,
            high=122_000.0,
            low=118_000.0,
            volume=123_456,
        ),
    ],
)
def test_models_remain_immutable(model: SymbolInfo | StockQuote) -> None:
    with pytest.raises(ValidationError) as raised:
        model.symbol = "OTHER"

    assert raised.value.errors()[0]["type"] == "frozen_instance"
    assert model.symbol == "FPT"


def test_typing_marker_is_packaged() -> None:
    assert files(vfinance).joinpath("py.typed").is_file()
