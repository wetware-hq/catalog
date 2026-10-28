from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import jsonschema
import yaml

from ecatalog.io import (
    ENTRIES_DIR,
    SCHEMA_PATH,
    SOURCE_TEXT_DIR,
    SOURCES_DIR,
    TAXONOMY_PATH,
    evidence_in_source,
    load_taxonomy,
    required_specs,
)
from ecatalog.refs import check_references_sync

# References:
# [19] Line-level lint diagnostics.


def load_schema() -> dict[str, Any]:
    return json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))


def lint_entry(entry: dict[str, Any], schema: dict[str, Any], path: Path) -> list[str]:
    errors: list[str] = []
    validator = jsonschema.Draft202012Validator(schema)
    for err in sorted(validator.iter_errors(entry), key=lambda e: list(e.path)):
        loc = "/".join(str(p) for p in err.path) or "(root)"
        errors.append(f"{path}: {loc}: {err.message}")
    if entry["category"] not in load_taxonomy():
        errors.append(f"{path}: unknown category")
    else:
        for attr in required_specs(entry["category"]):
            if attr not in (entry.get("specs") or {}):
                errors.append(f"{path}: missing required spec '{attr}'")
    if list(entry.keys())[-1] != "sources":
        errors.append(f"{path}: 'sources' must be last key")
    for sha in entry.get("sources", []):
        if not (SOURCES_DIR / f"{sha}.json").is_file():
            errors.append(f"{path}: missing source {sha}")
    for attr, spec in (entry.get("specs") or {}).items():
        ev, sha = spec.get("evidence"), spec.get("source")
        if not ev:
            errors.append(f"{path}: specs.{attr}: empty evidence")
            continue
        text_path = SOURCE_TEXT_DIR / f"{sha}.txt"
        if not text_path.is_file():
            errors.append(f"{path}: specs.{attr}: missing source text")
        elif not evidence_in_source(ev, text_path.read_text(encoding="utf-8")):
            errors.append(f"{path}: specs.{attr}: evidence not in snapshot")
    if len(entry.get("description", "")) > 400:
        errors.append(f"{path}: description too long")
    return errors


def lint_catalog() -> list[str]:
    errors: list[str] = list(check_references_sync())
    schema = load_schema()
    ids: set[str] = set()
    for path in ENTRIES_DIR.rglob("*.json"):
        entry = json.loads(path.read_text(encoding="utf-8"))
        if entry["id"] in ids:
            errors.append(f"duplicate id {entry['id']}")
        ids.add(entry["id"])
        errors.extend(lint_entry(entry, schema, path))
    if not TAXONOMY_PATH.is_file():
        errors.append("missing taxonomy.yaml")
    else:
        yaml.safe_load(TAXONOMY_PATH.read_text(encoding="utf-8"))
    return errors
