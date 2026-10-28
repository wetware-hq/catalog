#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
python3 -m pip install -e ".[dev]" -q
python3 -m ecatalog.cli references refresh
python3 -m ecatalog.cli lint --json
python3 -m pytest -q
