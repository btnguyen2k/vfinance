# Run tests with a specific mirror URL.

#!/bin/sh
set -eu

mirror="${1:?Usage: $0 MIRROR_URL}"
req=$(mktemp "${TMPDIR:-/tmp}/vfinance.XXXXXX")

trap 'rm -f "$req"' 0
trap 'exit 129' HUP
trap 'exit 130' INT
trap 'exit 143' TERM

uv export -q --frozen --all-groups --no-emit-project \
    --format requirements.txt -o "$req"

uv pip sync "$req" --python .venv \
    --default-index "$mirror" --require-hashes

uv pip install --python .venv --default-index "$mirror" \
    --no-deps --editable .

uv run --frozen --no-sync pytest --cov=src --cov-report=term-missing
