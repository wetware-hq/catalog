#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
python3 -m pip install -e ".[dev]" -q
python3 -m ecatalog.cli references refresh
python3 -m ecatalog.cli graph build --json
REF_N=$(mktemp)
REF_E=$(mktemp)
cp graph/nodes.jsonl "$REF_N"
cp graph/edges.jsonl "$REF_E"
rm -f graph/nodes.jsonl graph/edges.jsonl
python3 -m ecatalog.cli graph build --json
cmp -s "$REF_N" graph/nodes.jsonl
cmp -s "$REF_E" graph/edges.jsonl
rm -f "$REF_N" "$REF_E"
python3 -m ecatalog.cli lint --json
python3 -m pytest -q
