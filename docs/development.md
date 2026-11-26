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
|       |-- _utils.py       # Private async HTTP utilities
|       `-- py.typed        # PEP 561 typing marker
|-- tests
|   |-- test_package.py     # Installation and package-data smoke tests
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
