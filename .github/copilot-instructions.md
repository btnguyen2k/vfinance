# Copilot instructions for vfinance

## Build, test, and lint

Run commands from the repository root. Python 3.12+ is required. Use uv for
Python environments, dependency management, building, and publishing; the build
backend is `uv_build`.

```sh
uv sync --locked --python 3.12
uv run --locked ruff check .
uv run --locked ruff format --check --diff .
uv run --locked pytest --cov=src --cov-report=term-missing
uv build --no-sources
uv publish --dry-run
```

Run a single existing test:

```sh
uv run --locked pytest -k test_fetch_follows_redirects_by_default
```

Apply formatting with `uv run --locked ruff format .`.
See the [development guide](../docs/development.md) for dependency and release
procedures.

CI tests Python 3.12 and the latest stable Python on Linux x86-64, Linux ARM,
and Windows. Inspect the selected project interpreter with
`uv run --no-sync python --version`; bare `python` can still be the runner's host
interpreter.

The distribution job replaces the editable installation with the built wheel,
then runs `uv run --no-sync pytest`. Preserve `--no-sync` for this check:
ordinary `uv run` can replace the wheel with the editable source installation.
Keep source coverage in the source-test command, not the wheel check.

## Architecture

- vfinance is a typed, `src`-layout library for Vietnam stock-market data.
  Implemented APIs include private HTTP utilities and async symbol information
  and quotes in `vfinance.stocks`; the history and event APIs are tracked in the
  [roadmap](../docs/roadmap.md).
- `pyproject.toml` owns package metadata, dependency ranges, tool configuration,
  and the package version. `vfinance.__version__` reads installed distribution
  metadata rather than duplicating a version literal. Bump package versions with
  `uv version --bump patch` (or `minor`/`major`).
- `vfinance._utils` is the internal transport boundary. The CloudScraper helper
  offloads synchronous requests, decoding, and cleanup with `asyncio.to_thread`.
  The Playwright helper uses the async browser API and returns rendered HTML
  from an isolated context/page. The standard-library `fetch_url_async` uses
  urllib for GET, with copied headers, a validated seconds-based timeout,
  optional redirect following, and text decoding/cleanup in its worker.
  Keep all HTTP helpers private rather than re-exporting them from the package root.
- `vfinance._cache` defines internal `Cache` and `CacheEntry` classes. Each
  `Cache` instance represents one cachetools LRU domain with a per-instance
  lock and key-only set/get/delete methods. A synchronized module-level registry
  maps domain names to shared `Cache` instances; module create_domain,
  delete_domain, set, get, and delete functions manage and dispatch through it.
  Invalid/non-positive domain capacities use 1000; existing domains retain their
  instances, contents, and read-only capacity. Writes reset per-entry monotonic
  TTLs; non-positive/non-integer TTLs disable expiry. None deletes a key, and
  module set creates missing domains. Reads unwrap values and remove expired
  entries without renewing TTLs. Get/delete misses do not create domains.
  Cache tests isolate the module registry and advance a controlled clock rather
  than sleeping.
- `vfinance.models` defines immutable Pydantic v2 business models `SymbolInfo`
  and `StockQuote`. Keep strict validation, forbid unexpected fields, and reject
  non-finite prices. `StockQuote.timestamp_str` is a read-only computed ISO field
  included in normal dumps. Use `model_dump`/`model_dump_json`, not dataclass
  helpers; use `round_trip=True` when serializing quotes for input validation.
  Consumers import these types from `vfinance.models`; API modules reference
  them through normal module imports rather than re-exporting imported types.
- `vfinance.utils.normalize_ticker` accepts `CODE`, `CODE.VN`, or `EXCHANGE:CODE`
  without validating the exchange prefix or symbol's existence. Codes may have
  single dots between nonempty alphanumeric parts, but extracted codes must not
  end with `.VN`. An exchange prefix and `.VN` suffix cannot be combined.
  `vfinance._dnse.get_info` uses the standard-library HTTP helper to fetch DNSE
  JSON profiles, matching the normalized code. It returns `None` for HTTP 404
  or no match; normalization, transport, parsing, and profile exceptions
  propagate unchanged. Other HTTP failures raise `RuntimeError`.
  Exchange, instrument type, and index code are uppercase;
  GICS labels and other supplied text stay unchanged, including empty strings.
  Missing/null optional values are `None` and an unavailable overview is empty.
  `vfinance._dnse.get_quote` reads the latest aligned one-minute OHLCV bar,
  starting from UTC+7 midnight and following `nextTime` backward over empty
  periods for at most 14 previous calendar days. JSON missing any of `t`, `o`,
  `h`, `l`, or `c` is an error response and returns `None`, independent of
  status/code/message fields. Keep request ranges valid while stepping back:
  reversed ranges return null arrays that resemble invalid symbols. It returns
  UTC+7 datetimes and VND prices (response prices times 1000), preserves null
  closing prices, validates whole-unit volume, and uses `get_info` for the
  authoritative listing exchange. Missing symbols/history/profiles return
  `None`; service/data/transport errors and cancellation propagate.
  `vfinance.stocks.get_info` caches successful profiles in `SYMBOL-INFO`, keyed
  by the normalized symbol, for 86400 seconds (24 hours). Cache misses delegate
  to this adapter; missing symbols and lookup errors are not cached.
  Ordinary errors are logged with ticker context, exception type and message,
  and the original traceback through the `vfinance.stocks` logger, without
  configuring application handlers.
  They return `None` unless the `raise_on_error` keyword is supplied, regardless
  of its value, in which case the original exception is re-raised. Missing
  symbols still return `None`; cancellation propagates without failure logging.
  `vfinance.stocks.get_quote` follows the same normalization and error policy,
  caching only successful quotes in `STOCK-QUOTE` for 300 seconds (5 minutes).
  Missing quotes and lookup failures are not cached.
- Tests exercise the installed editable package during development and the
  installed wheel in the distribution job. Package smoke tests also import with
  Python's `-I` isolation from a temporary directory and verify `py.typed`.
  Preserve installed-package testing rather than adding source-path workarounds.

## Public API documentation

- Use Google-style docstrings for public functions and methods, with `Args`,
  `Returns`, `Raises`, and `Notes` sections as applicable. Document public
  returned models with `Attributes`.
- Start with a concise description of the business purpose. Do not expose
  underlying data sources or implementation details unless explicitly requested
  for that public documentation.
- A request to implement or change a technical feature is not permission to
  explain its internals in public documentation. Keep implementation details
  in the development guide unless technical public documentation is explicitly
  requested.
- Document every input: type, accepted formats or values, units, defaults,
  normalization, and validation rules where relevant, including supported kwargs.
- Document the output type and meaning, returned model fields, and missing-data
  behavior such as `None`, empty strings, or empty collections. Put complete
  field descriptions and defaults on the returned model.
- Document each deliberate exception and expected exception that can propagate,
  with its type and trigger. Use qualified names for dependency exceptions.
  Distinguish not-found results from failures and document async cancellation.
- Do not add a `Notes` section automatically because a template supports it.
  Use it only for essential business-facing limitations or known workarounds,
  not implementation mechanics or repeated input/output/exception details.
  Describe temporary behavior only when supported by an existing plan; do not
  invent future guarantees. Keep internal design details in the development guide.
- Keep documentation aligned with the implementation and existing tests; do not
  claim validation, defaults, or behavior the API does not implement.
- Before declaring a change complete, review the entire affected public
  docstring, including unchanged text, against these rules rather than checking
  only the diff. Functional correctness and documentation compliance are
  separate acceptance gates; both must pass.
- When a documentation violation is reported, reassess the whole affected
  section against the ground rule and correct all related violations. Do not
  limit the correction to the last offending sentence.

## Key conventions

- Never deliberately re-export an import, including through compatibility
  aliases or `__all__`. Declared public exports must be defined in the exporting
  module. Import shared models from their defining module and use normal module
  imports, such as `from . import models`, in consumers.
- Use normal dependency imports. Do not introduce underscore aliases solely to
  hide imported dependencies; an ordinary import is not a deliberate re-export.
  Keep genuinely private module, helper, and implementation-state names private.
- Keep `pyproject.toml` and `uv.lock` aligned when changing dependencies. Routine
  commands use `--locked`; dependency updates use `uv add`, `uv remove`, or
  `uv lock --upgrade`. The lockfile fixes development/CI versions, while package
  consumers use the declared runtime ranges. Generate committed lockfiles with
  `uv lock --default-index https://pypi.org/simple`; do not persist undeclared
  local index overrides in package registry sources.
- Cap direct dependencies below their next major. Pre-1.0 development tools use
  `<1`, not a cap at the next minor. Runtime minimums use `major.minor.0`, such as
  `cloudscraper>=1.2.0,<2`; retain the specific patch for `0.0.x` minimums.
  The runtime minimum rule excludes build-backend and dev dependencies.
- Preserve the CloudScraper helper's ownership and error contract: close each
  response, leave the caller's scraper open, return HTTP error statuses, and propagate
  request/body-reading exceptions. Serialize shared-scraper access or use
  separate instances; cancelling the await does not stop the blocking worker.
- Use WebKit by default for Playwright-based fetching and browser setup. Launch
  it with `await playwright.webkit.launch(headless=True)`, while keeping the
  helper browser-agnostic and its async `Browser` caller-owned.
- The Playwright helper leaves its caller-owned browser open and closes its own
  context/page on success, error, and cancellation. Its `timeout` uses native
  milliseconds (30,000 by default; 0 disables it). Browser binaries are needed
  for real browser use, not the mocked unit tests; see the development guide.
- `HttpResponse.is_successful()` includes statuses 100-399. CloudScraper follows
  redirects by default; `allow_redirects=False` exposes an unfollowed redirect's
  `Location` as an absolute `redirect_url`, resolved against the response URL.
- HTTP tests use `asyncio.run` with mocked responses or transport adapters,
  including real urllib and CloudScraper redirect handling without live website
  requests.
- Keep the [README](../README.md) business-focused. Contributor internals belong
  in the development guide; planned capabilities and implementation status
  belong in the roadmap.
- For commit-message requests, follow the installed
  [Angular-style agent](agents/angular-style-commit-message-generator.agent.md).
  CI's `ReleaseDryRun` uses `action-semrelease`; its normal-mode rules treat
  `refactor` as minor-release-significant. The workflow previews releases rather
  than publishing distributions.
