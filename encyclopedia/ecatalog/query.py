from __future__ import annotations

import json
from typing import Any

from ecatalog.io import ENTRIES_DIR, SOURCES_DIR, iter_entries

# References:
# [15] Query only returns existing ids.


def _entry_path(entry_id: str):
    for path in ENTRIES_DIR.rglob("*.json"):
        if path.stem == entry_id:
            return path
    return None


def _summary_row(entry: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": entry["id"],
        "name": entry["name"],
        "category": entry["category"],
        "maker": entry["maker"]["name"],
        "tags": entry.get("tags", []),
        "updated_at": entry["updated_at"],
        "confidence": entry.get("confidence", 0),
    }


def get_entry(entry_id: str, *, include_unverified: bool = False) -> dict[str, Any]:
    path = _entry_path(entry_id)
    if not path:
        raise KeyError(entry_id)
    entry = json.loads(path.read_text(encoding="utf-8"))
    if not include_unverified and entry.get("confidence", 0) < 0.6:
        raise KeyError(entry_id)
    sources = []
    for sha in entry.get("sources", []):
        meta = SOURCES_DIR / f"{sha}.json"
        if meta.is_file():
            sources.append(json.loads(meta.read_text(encoding="utf-8")))
    return {"entry": entry, "sources": sources}


def search(
    text: str,
    *,
    category: str | None = None,
    kind: str | None = None,
    maker: str | None = None,
    tag: str | None = None,
    include_unverified: bool = False,
) -> list[dict[str, Any]]:
    needle = text.lower()
    hits: list[dict[str, Any]] = []
    for entry in iter_entries():
        if not include_unverified and entry.get("confidence", 0) < 0.6:
            continue
        if category and entry["category"] != category:
            continue
        if kind and entry.get("kind") != kind:
            continue
        if maker and maker.lower() not in entry.get("maker", {}).get("name", "").lower():
            continue
        if tag and tag not in (entry.get("tags") or []):
            continue
        blob = " ".join(
            [
                entry["id"],
                entry["name"],
                entry["category"],
                entry["maker"]["name"],
                " ".join(entry.get("tags") or []),
                entry.get("description", ""),
            ]
        ).lower()
        if needle and needle not in blob:
            continue
        hits.append(_summary_row(entry))
    return hits
