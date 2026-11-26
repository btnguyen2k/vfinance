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
  The implemented runtime foundation is the private HTTP utility; data-source
  adapters and the public quote, history, and event APIs are tracked in the
  [roadmap](../docs/roadmap.md).
- `pyproject.toml` owns package metadata, dependency ranges, tool configuration,
  and the package version. `vfinance.__version__` reads installed distribution
  metadata rather than duplicating a version literal. Bump package versions with
  `uv version --bump patch` (or `minor`/`major`).
- `vfinance._utils` is the internal transport boundary. Its async fetcher wraps
  synchronous CloudScraper GET requests with `asyncio.to_thread`, including body
  decoding and response cleanup. Keep these helpers private rather than
  re-exporting them from the package root.
- Tests exercise the installed editable package during development and the
  installed wheel in the distribution job. Package smoke tests also import with
  Python's `-I` isolation from a temporary directory and verify `py.typed`.
  Preserve installed-package testing rather than adding source-path workarounds.

## Key conventions

- Keep `pyproject.toml` and `uv.lock` aligned when changing dependencies. Routine
  commands use `--locked`; dependency updates use `uv add`, `uv remove`, or
  `uv lock --upgrade`. The lockfile fixes development/CI versions, while package
  consumers use the declared runtime ranges.
- Cap direct dependencies below their next major. Pre-1.0 development tools use
  `<1`, not a cap at the next minor. Runtime minimums use `major.minor.0`, such as
  `cloudscraper>=1.2.0,<2`; retain the specific patch for `0.0.x` minimums.
  The runtime minimum rule excludes build-backend and dev dependencies.
- Preserve the HTTP helper's ownership and error contract: close each response,
  leave the caller's scraper open, return HTTP error statuses, and propagate
  request/body-reading exceptions. Serialize shared-scraper access or use
  separate instances; cancelling the await does not stop the blocking worker.
- `HttpResponse.is_successful()` includes statuses 100-399. Redirects follow by
  default; `allow_redirects=False` exposes an unfollowed redirect's `Location`
  as an absolute `redirect_url`, resolved against the response URL.
- HTTP tests use `asyncio.run` with mocked responses or transport adapters,
  including real CloudScraper redirect handling without live website requests.
- Keep the [README](../README.md) business-focused. Contributor internals belong
  in the development guide; planned capabilities and implementation status
  belong in the roadmap.
- For commit-message requests, follow the installed
  [Angular-style agent](agents/angular-style-commit-message-generator.agent.md).
  CI's `ReleaseDryRun` uses `action-semrelease`; its normal-mode rules treat
  `refactor` as minor-release-significant. The workflow previews releases rather
  than publishing distributions.
