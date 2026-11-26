"""Private HTTP utilities for data-source implementations."""

import asyncio
import math
from dataclasses import dataclass
from typing import Any
from urllib.parse import urljoin

from cloudscraper import CloudScraper


@dataclass(frozen=True, slots=True)
class HttpResponse:
    """Decoded HTTP response with an optional, unfollowed redirect target."""

    status: int
    content: str
    redirect_url: str | None = None

    def is_successful(self) -> bool:
        """Return whether the status is in the non-error range 100-399."""
        return 100 <= self.status < 400


async def fetch_url_cloudscraper_async(
    url: str, scraper: CloudScraper, **kwargs: Any
) -> HttpResponse:
    """Fetch decoded text using GET without blocking the event loop.

    Build request options from supported GET kwargs. Positive, finite int/float
    connect_timeout and read_timeout values become the request timeout tuple;
    missing or invalid values (including bools) default to 5 and 30 seconds.
    Ignore unsupported kwargs and the raw timeout option.

    Redirects are followed by default; use allow_redirects=False to expose a
    redirect's Location as an absolute redirect_url, or None when there is no
    redirect target.

    Return HTTP error statuses normally; request and body-reading exceptions
    propagate. Close the response after reading, but leave the scraper open.
    Use separate scrapers for concurrent calls, or serialize access externally.
    Cancelling this coroutine does not stop the underlying blocking request.
    """
    get_kwargs: dict[str, Any] = {}
    timeouts: list[int | float] = []
    for option, default in (("connect_timeout", 5), ("read_timeout", 30)):
        value = kwargs.get(option)
        if (
            isinstance(value, bool)
            or not isinstance(value, (int, float))
            or not 0 < value < math.inf
        ):
            value = default
        timeouts.append(value)
    get_kwargs["timeout"] = tuple(timeouts)

    for option in (
        "params",
        "data",
        "headers",
        "cookies",
        "files",
        "auth",
        "allow_redirects",
        "proxies",
        "hooks",
        "stream",
        "verify",
        "cert",
        "json",
    ):
        if option in kwargs:
            get_kwargs[option] = kwargs[option]

    def fetch() -> HttpResponse:
        with scraper.get(url, **get_kwargs) as response:
            location = response.headers.get("Location")
            redirect_url = (
                urljoin(response.url, location)
                if response.is_redirect and location
                else None
            )
            return HttpResponse(
                status=response.status_code,
                content=response.text,
                redirect_url=redirect_url,
            )

    return await asyncio.to_thread(fetch)
