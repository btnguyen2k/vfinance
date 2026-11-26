import asyncio
import math
from threading import get_ident
from typing import Any
from unittest.mock import Mock, PropertyMock

import pytest
from cloudscraper import CloudScraper
from requests import PreparedRequest, Response
from requests.adapters import HTTPAdapter
from requests.exceptions import ChunkedEncodingError, ConnectionError, Timeout

from vfinance._utils import HttpResponse, fetch_url_cloudscraper_async


@pytest.fixture
def response() -> Response:
    response = Response()
    response.status_code = 200
    response.url = "https://example.test/market/quote"
    response.encoding = "utf-8"
    response._content = "Gi\u00e1: 123".encode("utf-8")
    response._content_consumed = True
    return response


@pytest.fixture
def scraper(response: Response) -> Mock:
    scraper = Mock(spec=CloudScraper)
    scraper.get.return_value = response
    return scraper


@pytest.mark.parametrize(
    ("status", "expected"),
    [
        (99, False),
        (100, True),
        (199, True),
        (200, True),
        (299, True),
        (300, True),
        (399, True),
        (400, False),
        (503, False),
    ],
)
def test_is_successful(status: int, expected: bool) -> None:
    assert HttpResponse(status=status, content="").is_successful() is expected


@pytest.mark.parametrize("status", [200, 503])
def test_fetch_reads_and_closes_response_in_worker(
    status: int, response: Response, scraper: Mock, monkeypatch: pytest.MonkeyPatch
) -> None:
    response.status_code = status
    event_loop_thread = get_ident()
    worker_threads: list[int] = []
    original_text = Response.text
    original_close = response.close

    def get_response(*args, **kwargs) -> Response:
        worker_threads.append(get_ident())
        return response

    def read_content() -> str:
        worker_threads.append(get_ident())
        return original_text.__get__(response, Response)

    def close_response() -> None:
        worker_threads.append(get_ident())
        original_close()

    scraper.get.side_effect = get_response
    text = PropertyMock(side_effect=read_content)
    close = Mock(side_effect=close_response)
    monkeypatch.setattr(Response, "text", text)
    monkeypatch.setattr(response, "close", close)

    result = asyncio.run(fetch_url_cloudscraper_async(response.url, scraper))

    assert result == HttpResponse(status=status, content="Gi\u00e1: 123")
    scraper.get.assert_called_once_with(response.url, timeout=(5, 30))
    text.assert_called_once_with()
    close.assert_called_once_with()
    scraper.close.assert_not_called()
    assert all(thread != event_loop_thread for thread in worker_threads)


@pytest.mark.parametrize(
    ("timeout_options", "timeout"),
    [
        ({}, (5, 30)),
        ({"connect_timeout": 2.5}, (2.5, 30)),
        ({"read_timeout": 1.5}, (5, 1.5)),
        ({"connect_timeout": 2, "read_timeout": 10}, (2, 10)),
    ],
)
def test_fetch_copies_supported_kwargs(
    timeout_options: dict[str, int | float],
    timeout: tuple[int | float, int | float],
    response: Response,
    scraper: Mock,
) -> None:
    options = {
        "params": {"ticker": "VNM"},
        "data": {"market": "VN"},
        "headers": {"Accept": "text/html"},
        "cookies": {"session": "example"},
        "files": None,
        "auth": None,
        "allow_redirects": False,
        "proxies": {},
        "hooks": {},
        "stream": True,
        "verify": False,
        "cert": None,
        "json": None,
    }
    kwargs = {
        **options,
        **timeout_options,
        "timeout": (99, 99),
        "unknown_option": "ignored",
    }

    result = asyncio.run(fetch_url_cloudscraper_async(response.url, scraper, **kwargs))

    assert result.content == "Gi\u00e1: 123"
    scraper.get.assert_called_once_with(response.url, timeout=timeout, **options)


@pytest.mark.parametrize("option", ["connect_timeout", "read_timeout"])
@pytest.mark.parametrize(
    "value",
    [None, 0, -1, "5", True, False, (1, 2), math.nan, math.inf, -math.inf],
)
def test_fetch_defaults_invalid_timeout(
    option: str, value: Any, response: Response, scraper: Mock
) -> None:
    kwargs = {"connect_timeout": 2, "read_timeout": 10, option: value}

    asyncio.run(fetch_url_cloudscraper_async(response.url, scraper, **kwargs))

    expected = (5, 10) if option == "connect_timeout" else (2, 30)
    scraper.get.assert_called_once_with(response.url, timeout=expected)


@pytest.mark.parametrize(
    ("status", "location", "expected"),
    [
        (302, "../events", "https://example.test/events"),
        (301, "https://other.test/quote", "https://other.test/quote"),
        (307, "//other.test/quote", "https://other.test/quote"),
        (302, None, None),
        (302, "", None),
        (200, "/not-a-redirect", None),
        (304, "/not-a-redirect", None),
    ],
)
def test_fetch_resolves_unfollowed_redirect_target(
    status: int,
    location: str | None,
    expected: str | None,
    response: Response,
    scraper: Mock,
) -> None:
    response.status_code = status
    if location is not None:
        response.headers["location"] = location

    result = asyncio.run(
        fetch_url_cloudscraper_async(
            "https://example.test/start", scraper, allow_redirects=False
        )
    )

    assert result.status == status
    assert result.redirect_url == expected


def test_fetch_follows_redirects_by_default(response: Response) -> None:
    redirect = Response()
    redirect.status_code = 302
    redirect.url = "https://example.test/start"
    redirect.headers["Location"] = "/market/quote"
    redirect._content = b""
    redirect._content_consumed = True
    adapter = Mock(spec=HTTPAdapter)
    responses = iter([redirect, response])

    def send(request: PreparedRequest, **kwargs) -> Response:
        result = next(responses)
        result.request = request
        return result

    adapter.send.side_effect = send

    with CloudScraper() as scraper:
        scraper.mount("https://", adapter)
        result = asyncio.run(fetch_url_cloudscraper_async(redirect.url, scraper))

    assert result == HttpResponse(status=200, content="Gi\u00e1: 123")
    assert [call.args[0].url for call in adapter.send.call_args_list] == [
        redirect.url,
        response.url,
    ]


@pytest.mark.parametrize("error", [ConnectionError("offline"), Timeout("timed out")])
def test_fetch_propagates_request_errors(scraper: Mock, error: Exception) -> None:
    scraper.get.side_effect = error

    with pytest.raises(type(error)) as caught:
        asyncio.run(fetch_url_cloudscraper_async("https://example.test", scraper))

    assert caught.value is error
    scraper.close.assert_not_called()


def test_fetch_closes_response_when_body_reading_fails(
    response: Response, scraper: Mock, monkeypatch: pytest.MonkeyPatch
) -> None:
    error = ChunkedEncodingError("incomplete body")
    monkeypatch.setattr(Response, "text", PropertyMock(side_effect=error))
    close = Mock(wraps=response.close)
    monkeypatch.setattr(response, "close", close)

    with pytest.raises(ChunkedEncodingError) as caught:
        asyncio.run(fetch_url_cloudscraper_async(response.url, scraper, stream=True))

    assert caught.value is error
    close.assert_called_once_with()
    scraper.close.assert_not_called()
