"""Private HTTP utilities for data-source implementations."""

import asyncio
import math
from dataclasses import dataclass
from typing import Any
from urllib.parse import urljoin

from cloudscraper import CloudScraper
from playwright.async_api import Browser


@dataclass(frozen=True, slots=True)
class HttpResponse:
    """HTTP status and text with an optional, unfollowed redirect target."""

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


async def fetch_url_playwright_async(
    url: str, browser: Browser, **kwargs: Any
) -> HttpResponse:
    """Fetch rendered HTML using a caller-owned async Playwright browser.

    Copy supported Browser.new_context options into a fresh context and
    supported Page.goto options into navigation kwargs. Nonnegative, finite
    int/float timeout values are milliseconds, defaulting to 30_000 when missing
    or invalid; 0 disables the timeout. Navigation waits for load unless
    wait_until is supplied.
    Unsupported kwargs are ignored.

    Return the navigation status and page.content(), not the raw response body.
    Redirects are followed by the browser. Close the context and its pages on
    success, failure, or cancellation, but leave the browser open.
    HTTP error statuses are returned normally; Playwright exceptions propagate.
    Raise ValueError if navigation produces no HTTP response, as with about:blank.
    """
    context_kwargs: dict[str, Any] = {}
    for option in (
        "accept_downloads",
        "base_url",
        "bypass_csp",
        "client_certificates",
        "color_scheme",
        "contrast",
        "default_browser_type",
        "device_scale_factor",
        "extra_http_headers",
        "forced_colors",
        "geolocation",
        "has_touch",
        "http_credentials",
        "ignore_https_errors",
        "is_mobile",
        "java_script_enabled",
        "locale",
        "no_viewport",
        "offline",
        "permissions",
        "proxy",
        "record_har_content",
        "record_har_mode",
        "record_har_omit_content",
        "record_har_path",
        "record_har_url_filter",
        "record_video_dir",
        "record_video_size",
        "reduced_motion",
        "screen",
        "service_workers",
        "storage_state",
        "strict_selectors",
        "timezone_id",
        "user_agent",
        "viewport",
    ):
        if option in kwargs:
            context_kwargs[option] = kwargs[option]

    goto_kwargs: dict[str, Any] = {}
    timeout = kwargs.get("timeout")
    if (
        isinstance(timeout, bool)
        or not isinstance(timeout, (int, float))
        or not 0 <= timeout < math.inf
    ):
        timeout = 30_000
    goto_kwargs["timeout"] = timeout
    for option in ("wait_until", "referer"):
        if option in kwargs:
            goto_kwargs[option] = kwargs[option]

    context = await browser.new_context(**context_kwargs)
    try:
        page = await context.new_page()
        response = await page.goto(url, **goto_kwargs)
        if response is None:
            raise ValueError("Navigation did not return an HTTP response")
        location = response.headers.get("location")
        redirect_url = (
            urljoin(response.url, location)
            if response.status in (301, 302, 303, 307, 308) and location
            else None
        )
        return HttpResponse(
            status=response.status,
            content=await page.content(),
            redirect_url=redirect_url,
        )
    finally:
        await context.close()
