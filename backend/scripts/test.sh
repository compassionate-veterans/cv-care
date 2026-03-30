#!/usr/bin/env bash

set -e
set -x

ENV_FILE="${TEST_ENV_FILE:-.env.test}"

if [ -f "$ENV_FILE" ]; then
    set -a
    source "$ENV_FILE"
    set +a
fi

uv run coverage run -m pytest tests/ "$@"
uv run coverage report
uv run coverage html --title "${@-coverage}"
