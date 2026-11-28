# Development and publishing

Contributor setup, repository conventions, and release procedures for vfinance.
See the [product overview](../README.md) and [roadmap](roadmap.md) for product scope
and implementation status.

## Repository layout

```text
vfinance
|-- .github
|   `-- workflows
|       `-- ci.yml          # Linux/Windows checks and distribution builds
|-- docs
|   |-- development.md     # Contributor and release guide
|   `-- roadmap.md         # Planned features and implementation status
|-- src
|   `-- vfinance
|       |-- __init__.py     # Package entry point and version
|       |-- _cache.py       # Private LRU domains and per-entry TTL
|       |-- _dnse.py        # Private DNSE/Entrade profiles and quotes
|       |-- _utils.py       # Private async HTTP utilities
|       |-- models.py       # Shared business data models
|       |-- stocks.py       # Public symbol information and quote APIs
|       |-- utils.py        # Public ticker normalization
|       `-- py.typed        # PEP 561 typing marker
|-- tests
|   |-- test_cache.py       # Domain lifecycle, LRU behavior, and TTL
|   |-- test_dnse.py        # Symbol JSON parsing and fetching
|   |-- test_package.py     # Installation and package-data smoke tests
|   |-- test_stocks.py      # Public symbol API delegation and errors
|   |-- test_ticker_utils.py # Public ticker normalization
|   `-- test_utils.py       # HTTP helper behavior and error handling
|-- .editorconfig
|-- .gitignore
|-- LICENSE.md
|-- README.md              # Product features and business value
|-- pyproject.toml         # Metadata, dependencies, build and tool settings
`-- uv.lock                # Reproducible development and CI dependencies
```

The `src` layout ensures imports use the installed package rather than accidentally
using a directory in the repository root. Add implementation modules under
`src/vfinance` and corresponding tests under `tests`.
uv is the single tool for Python installation, virtual environments, dependencies,
building, and publishing. The build backend is uv's native `uv_build`; no separate
build or upload tool is needed.

## Development environment

**Requires Python 3.12 or newer.** Install
[uv](https://docs.astral.sh/uv/getting-started/installation/) 0.13.10 or newer,
then run these commands from the repository root. Restart your terminal after
installation if `uv` is not yet on your PATH.

```sh
uv sync --locked --python 3.12
uv run --locked ruff check .
uv run --locked ruff format --check .
uv run --locked pytest --cov=src --cov-report=term-missing
```

These commands work in PowerShell, Linux, and macOS. uv installs Python when
needed, creates `.venv`, and installs the package in editable mode together with
the `dev` dependency group. Source changes are available without reinstalling.
Environment activation and a separate `venv` command are unnecessary: `uv run`
uses the project environment.

The `dev` group also includes uv, making it available when `.venv` is activated.
A fresh machine still needs an initial uv installation before `uv sync` can run;
GitHub Actions uses `astral-sh/setup-uv` for that bootstrap.

Use `uv run --locked ruff format .` to apply formatting. To use another supported
interpreter, replace `3.12` in the sync command with its version.
CI checks Python 3.12 and the latest stable Python on Linux and Windows, then
builds and tests the wheel separately.

Virtual environments, build output, caches, and local credentials are already
excluded by `.gitignore`. Do not commit them. Keep `uv.lock` in version control;
it makes contributor and CI environments reproducible without pinning the
dependencies of people installing the published package.

## Symbol information

`vfinance.stocks.get_info(ticker)` is async and returns a `SymbolInfo` from
`vfinance.models`, populated with DNSE/Entrade profiles for company stocks and
other instruments such as ETFs. It accepts `CODE`, `EXCHANGE:CODE`, or `CODE.VN`,
ignoring case and surrounding whitespace.
These forms cannot be combined: `EXCHANGE:CODE.VN` is invalid. Codes may contain
single dots between nonempty alphanumeric parts, such as `ABC.Z`; `ABC.Z.VN`
and `HOSE:ABC.Z` both identify `ABC.Z`. Extracted codes must not end with `.VN`,
so repeated suffixes such as `ABC.VN.VN` are invalid. Other dotted endings, such
as `.US`, remain part of the code rather than being treated as country suffixes.
`vfinance.utils.normalize_ticker` exposes the same uppercase code extraction
for reuse. Prefixes are discarded rather than validated against the source;
the returned exchange is the uppercase reported listing venue.

```python
import asyncio

from vfinance.stocks import get_info


async def main() -> None:
    info = await get_info("HOSE:BID")
    if info is not None:
        print(info.symbol, info.exchange, info.name)


asyncio.run(main())
```

Import the model with `from vfinance.models import SymbolInfo`; it is not
re-exported from `vfinance.stocks` or the package root. Public APIs expose only
objects defined in their own module. Use normal dependency imports rather than
underscore aliases added solely to hide imports; only declared API exports are
subject to the no-re-export rule.

`vfinance.models.SymbolInfo` contains `exchange`, `symbol`, `name`, and `overview`.
Optional fields are `english_name`, `short_name`, `website`, `symbol_type`,
`index_code`, `industry`, `sub_industry`, `sector`, `industry_group`, and
`industry_group_slug`.
Lookup results uppercase `symbol_type` and `index_code`. The classification fields contain
the unchanged GICS labels and industry-group slug, not the source's separate
non-GICS industry fields. Missing or null optional values are `None`; supplied
empty strings remain empty. This response has no overview or website, so the
overview is empty and the website remains `None`.

`vfinance.models.StockQuote` contains a `datetime.datetime` timestamp, its
ISO 8601 `timestamp_str`, exchange, symbol, float-valued `open`, `high`, and
`low` prices, integer `volume`, and an optional float-valued `close`. Prices use
VND per traded unit; volume counts traded units. All input fields except `close`
are required. `timestamp_str` is derived automatically from `timestamp`,
preserving fractional seconds and any timezone offset. Omitting `close` leaves
it as `None`, indicating trading is ongoing and the closing price is not finalized.
Like `SymbolInfo`, it is immutable. Timestamp timezone information is preserved.
Import it from `vfinance.models`, not the package root or an API module.

Both models inherit from Pydantic v2 `BaseModel`. Constructors use keyword
arguments and validate types strictly rather than accepting numeric strings or
other coercible values. Unexpected fields and non-finite prices are rejected
with `pydantic.ValidationError`. Source-specific parsing and normalization remain
in the adapters; models do not change text case or strip supplied whitespace.

Use `model_dump()` for Python dictionaries, `model_dump(mode="json")` for
JSON-compatible dictionaries, and `model_dump_json()` for JSON strings.
Date/time values are serialized in ISO format, and `None` becomes `null`.

```python
from vfinance.models import SymbolInfo

info = SymbolInfo(exchange="HOSE", symbol="FPT", name="FPT", overview="")
info_json = info.model_dump_json()
restored = SymbolInfo.model_validate_json(info_json)
```

`StockQuote.timestamp_str` is a computed output, not a constructor argument.
Normal dumps include it. To serialize a quote for validation back into
`StockQuote`, use `quote.model_dump_json(round_trip=True)`; this omits the
computed field, which is recreated from the validated timestamp.
For trusted updates, use `model_copy(update={...})` instead of
`dataclasses.replace`. Copy updates are not revalidated; use `model_validate`
or `model_validate_json` for untrusted input.

The private `vfinance._dnse.get_info` adapter fetches
`https://api.dnse.com.vn/market-api/tickers?symbol=<CODE>` and selects a matching
symbol from the JSON `data` list. It returns `None` for HTTP 404 or no match.
Malformed tickers raise `ValueError` (or `TypeError` for non-string input).
Other HTTP failures raise `RuntimeError`; normalization, JSON parsing, profile
validation, and transport exceptions propagate unchanged. The JSON uses
`gicsIndustryGroup` and `gicsIndustryGroupSlug` for the group fields.

The public `vfinance.stocks.get_info` wrapper also returns `None` for ordinary
lookup errors, including non-string input, HTTP failures, and transport/parsing
failures, and logs the ticker, exception type and message, and original traceback
through the `vfinance.stocks` logger. It does not configure logging handlers.
Supplying the `raise_on_error` keyword, regardless of its value, re-raises the
original exception after logging it. Missing symbols still return `None`, and
cancellation always propagates without being logged as a lookup failure.
By default, `None` does not distinguish an unknown symbol from a failed lookup.
The public normalization utility raises
`ValueError` for malformed strings and `TypeError` for non-string inputs; it
does not check whether a symbol exists.

Successful profiles are cached in the internal `SYMBOL-INFO` domain using the
normalized bare symbol as the key and a TTL of 86400 seconds (24 hours).
Equivalent ticker formats share a cached profile, and only cache misses reach
the adapter. Missing symbols and failed lookups are not cached, so they can be
retried immediately.

Fetching uses the standard-library HTTP helper and offloads network operations
from the event loop. No browser installation is needed. Symbol API tests use
synthetic JSON and mocked transports, not live requests.

## Stock quotes

`vfinance.stocks.get_quote(ticker)` is async and returns the latest available
one-minute `StockQuote`, or `None` when a quote is unavailable. It accepts the
same ticker formats and `raise_on_error` option as `get_info`, including
presence-based exception propagation regardless of the option's value.
Lookup failures are logged with ticker context and the original traceback;
cancellation propagates without failure logging.

```python
import asyncio

from vfinance import stocks


async def main():
    quote = await stocks.get_quote("FPT")
    if quote is not None:
        print(quote.model_dump_json())


asyncio.run(main())
```

Successful quotes are cached in `STOCK-QUOTE`, keyed by the normalized symbol,
for 300 seconds (5 minutes). Missing quotes and failures are not cached.
Equivalent ticker formats share the same cached quote without renewing its TTL.

## Private quote lookup

`vfinance._dnse.get_quote` retrieves the latest available one-minute OHLCV bar.
It normalizes the ticker and requests
`/chart-api/v2/ohlcs/stock?symbol=<CODE>&resolution=1&from=<START>&to=<END>`,
starting at midnight today in Asia/Ho_Chi_Minh (UTC+7) and ending at the current
time. Both bounds are Unix seconds. Empty arrays move the end to `nextTime`
and move the start backward in whole-day steps until the range is valid.
The search includes today and at most 14 previous calendar days; older cursors
return `None` without requesting an out-of-range day.
This matters on weekends and holidays: DNSE returns null arrays for reversed
ranges, which otherwise look like invalid-symbol responses.

The final aligned `t`, `o`, `h`, `l`, `c`, and `v` entries form the quote.
Timestamps become timezone-aware UTC+7 datetimes, and prices are multiplied by
1000 to convert the response's thousands of VND to VND. Volume must represent
whole traded units. A null final `c` stays `None`; zero remains zero.
`get_info` supplies the authoritative listing exchange, rather than trusting a
ticker prefix, and is fetched only after quote data is available.

HTTP 404, JSON that is not an object or lacks any of `t`, `o`, `h`, `l`, or `c`,
all-null arrays, exhausted history (`nextTime=0` or the 14-day limit), and an
unavailable listing profile return `None`. This does not depend on specific
error status/code/message fields. A usable quote also requires the `v` array.
Other HTTP failures, malformed quote data, transport errors, and cancellation
propagate. An empty response whose `nextTime` does not move backward is rejected
instead of looping indefinitely. Tests use a controlled market clock and
synthetic responses.

## Internal cache

`vfinance._cache` holds a process-wide dictionary of named `Cache` instances.
Each instance represents one domain backed by a cachetools `LRUCache`, counting
entries rather than bytes. Module-level `create_domain`, `delete_domain`, `set`,
`get`, and `delete` manage this registry and dispatch to the registered instance.
Domain names and keys are used unchanged. Creating a domain defaults to 1000
entries; non-positive or non-integer sizes, including booleans, use 1000.

cachetools exposes a [read-only maximum size](https://cachetools.readthedocs.io/en/stable/#cachetools.Cache.maxsize).
Creating an existing domain does nothing: its values and limit are retained.
Delete and recreate the domain to change its capacity, discarding its old values.
Deleting missing domains or keys is harmless.

```python
import vfinance._cache as cache

cache.create_domain("symbol-info", max_size=1000)
cache.set("symbol-info", "FPT", {"name": "CTCP FPT"}, ttl=300)
info = cache.get("symbol-info", "FPT")
cache.delete("symbol-info", "FPT")
cache.delete_domain("symbol-info")
```

Module-level `set` creates missing domains, including when its value is `None`;
`None` removes the key instead of being cached. Every write wraps the value in a new
`CacheEntry` and restarts its TTL, even if the key and value are unchanged.
Positive integer TTLs are seconds measured with a monotonic clock. Non-positive
or non-integer TTLs, including booleans, disable expiry. Unrepresentably large
positive TTLs use an infinite deadline.

`get` returns the original value or `None` for a missing domain/key or expired
entry. An expired entry is removed when read; there is no background expiry
sweep. Successful reads update LRU order without extending the TTL. A full
domain evicts its least recently used entry.

Module functions share named domains across all callers in the same process.
For independent storage outside the registry, construct `Cache(max_size=...)`
directly. Its `set(key, value, ttl=0)`, `get(key)`, and `delete(key)` methods do not
take a domain name.

A registry lock protects domain lifecycle and lookup, and a per-instance lock
protects each domain's cache operations across threads. Returned values are
references and are not protected against external mutation. Cache classes and
functions remain internal and are not re-exported from the package root.
Cache tests isolate the module registry and use a controlled clock rather than
sleeping.

## HTTP utilities

Private helpers in `vfinance._utils` return `HttpResponse` objects.
`fetch_url_async(url, **kwargs)` uses only standard-library HTTP operations:
it copies `headers` into a GET request and accepts a socket `timeout` in seconds
(30 by default; invalid values fall back to 30). HTTP(S) redirects are followed unless
`allow_redirects=False`, which returns an absolute pending `redirect_url`.
Unsupported kwargs are ignored. Fetching, decoding, and response cleanup run
in a worker thread; cancellation does not stop that blocking worker.

The standard-library helper decodes gzip/deflate content and the declared
charset, falling back to UTF-8 for missing or unknown charsets and replacing
undecodable characters. Unsupported content encodings raise `ValueError`.
It accepts only HTTP(S) URLs and does not render JavaScript.

The Playwright helper accepts a `Browser` from the async API and returns the rendered
DOM after navigation (`load` by default), rather than the raw response body.
It creates and closes an isolated context/page for each call, leaving the
caller's browser open. Its `timeout` is in milliseconds (30,000 by default;
0 disables it); supported context and navigation options are copied explicitly.
All helpers return ordinary HTTP error statuses and propagate request,
navigation, and content-reading exceptions to the awaiting caller.

**WebKit is the default browser for Playwright-based fetching.** Launch it with
`await playwright.webkit.launch(headless=True)` inside
`async with async_playwright() as playwright`, then pass it to
`fetch_url_playwright_async`. The helper itself remains browser-agnostic and does
not launch a browser; the caller is responsible for closing its browser.

For real browser use, install WebKit after syncing dependencies:

```sh
uv run --locked playwright install webkit
```

On Linux, including Docker builds, also install WebKit's system dependencies:

```sh
uv run --locked playwright install --with-deps webkit
```

The unit tests mock browser APIs and do not require browser downloads.

## Dependency management

Use `uv add <package>` for runtime dependencies and `uv add --dev <package>` for
development tools. Use `uv remove <package>` or `uv remove --dev <package>` to
remove them. uv updates `pyproject.toml`, `uv.lock`, and the environment together.

Keep an explicit upper bound on each direct dependency; raise it deliberately
when adopting a new major version. For example, use
`uv add --dev "pytest>=9.2.0,<10"` to keep pytest below version 10.
Pre-1.0 development tools use `<1`; the build backend retains its narrower range.

Set runtime dependency minimums to `major.minor.0`, for example
`cloudscraper>=1.2.0,<2`. For `0.0.x` versions, use the specific patch minimum
(for example `>=0.0.5`), not `>=0.0.0`. This minimum-version rule does not apply
to the build backend or the `dev` dependency group.

To update locked dependencies within the declared version ranges:

```sh
uv lock --upgrade
uv sync --locked
```

Commit `pyproject.toml` and `uv.lock` together when changing dependencies.
Generate committed lockfiles against public PyPI with
`uv lock --default-index https://pypi.org/simple`. An alternate local index
recorded in the lockfile will fail CI unless it is also configured in the project.
Use `--locked` for routine development and CI so stale lockfiles fail rather
than being silently rewritten.

## Build and publish

The version has a single source: `project.version` in `pyproject.toml`.
`vfinance.__version__` reads the installed package metadata.
Before a release, update the version using uv:

```sh
uv version --bump patch
```

Replace `patch` with `minor` or `major` as appropriate; add `--dry-run` to preview
the change. Commit the updated `pyproject.toml` and `uv.lock`.
Keep the license-file paths aligned with `LICENSE.md`.
Build into an empty `dist` directory so old releases are not accidentally uploaded:

```sh
uv build --no-sources
uv publish --dry-run --index testpypi
```

This creates a wheel and a source distribution under `dist`. `--no-sources`
ensures the build does not depend on local dependency-source overrides.
The publishing dry run checks the files and target without uploading; it does
not verify credentials or guarantee that an index will accept the release.

When ready, confirm ownership or availability of the `vfinance` name on each
index. Set `UV_PUBLISH_TOKEN` in your current shell to a **TestPyPI API token**,
then upload to the explicitly configured TestPyPI index:

```sh
uv publish --index testpypi
```

After reviewing that release, replace `UV_PUBLISH_TOKEN` with a **PyPI API token**
and publish to PyPI:

```sh
uv publish --dry-run
uv publish
```

Both upload commands use the artifacts in `dist`. TestPyPI is an explicit index:
it is not used to resolve project dependencies. Never commit tokens or store them
in `pyproject.toml` or `uv.lock`.

Publishing is manual; the current CI does not upload releases. Future release
automation can use [Trusted Publishing](https://docs.astral.sh/uv/guides/publish/#publishing-your-package)
instead of storing API tokens.
