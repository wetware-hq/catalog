from __future__ import annotations

import json
from typing import Any

from ecatalog.graph import EDGES_PATH, NODES_PATH, current_observation, entry_curie, read_jsonl
from ecatalog.io import ENTRIES_DIR, SOURCES_DIR, iter_entries

# References:
# [15] Query only returns existing ids.


def _entry_path(entry_id: str):
    for path in ENTRIES_DIR.rglob("*.json"):
        if path.stem == entry_id:
            return path
    return None


def _node_index() -> dict[str, dict[str, Any]]:
    return {n["id"]: n for n in read_jsonl(NODES_PATH)}


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
    curie = entry_curie(entry_id)
    nodes = _node_index()
    node = nodes.get(curie)
    edges = [
        e
        for e in read_jsonl(EDGES_PATH)
        if e.get("subject") == curie or e.get("object") == curie
    ]
    attrs: dict[str, Any] = {}
    for e in edges:
        if e.get("predicate") != "biolink:has_attribute":
            continue
        obj = nodes.get(e["object"], {})
        obs = obj.get("observations") or []
        if obs:
            attrs[obj.get("name", "")] = current_observation(obs)["value"]
    return {"entry": entry, "sources": sources, "graph": {"node": node, "edges": edges, "current_specs": attrs}}


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
    nodes = read_jsonl(NODES_PATH)
    entry_by_curie = {entry_curie(e["id"]): e for e in iter_entries()}
    for node in nodes:
        if not node["id"].startswith("catalog:") or "#" in node["id"]:
            continue
        entry_id = node["id"].removeprefix("catalog:")
        entry = entry_by_curie.get(node["id"])
        if not entry:
            continue
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
            [entry_id, node.get("name", ""), entry["category"], entry["maker"]["name"], " ".join(entry.get("tags") or [])]
        ).lower()
        if needle and needle not in blob:
            continue
        hits.append(
            {
                "id": entry_id,
                "curie": node["id"],
                "name": node.get("name"),
                "category": entry["category"],
                "biolink_category": node.get("category"),
                "maker": entry["maker"]["name"],
                "tags": entry.get("tags", []),
                "updated_at": entry["updated_at"],
                "confidence": entry.get("confidence", 0),
            }
        )
    return hits
