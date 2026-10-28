from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from ecatalog.graph import build_graph
from ecatalog.io import (
    ENTRIES_DIR,
    MERGE_CANDIDATES_PATH,
    SOURCES_DIR,
    SOURCE_TEXT_DIR,
    category_exists,
    fetch_url,
    normalize_source_text,
    order_entry,
    put_source_meta,
    put_text_object,
    required_specs,
    slugify_maker,
    evidence_in_source,
)


def research_urls(urls: list[str], run_id: str) -> dict[str, Any]:
    errors: list[str] = []
    lines: list[dict[str, Any]] = []
    for url in urls:
        try:
            raw, status = fetch_url(url)
            text = normalize_source_text(raw)
            digest = put_text_object(text)
            st = "manual" if url.endswith((".asc", ".txt", ".md")) else "maker_page"
            meta = {
                "sha256": digest,
                "url": url,
                "title": url,
                "publisher": "",
                "source_type": st,
                "retrieved_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
                "http_status": status,
                "excerpt_path": f"sources/text/{digest}.txt",
            }
            put_source_meta(meta)
            lines.append(
                {
                    "run_id": run_id,
                    "sha256": digest,
                    "url": url,
                    "source_type": st,
                    "http_status": status,
                }
            )
        except Exception as exc:  # noqa: BLE001
            errors.append(f"research: {url}: {exc}")
    return {"run_id": run_id, "sources": [x["sha256"] for x in lines], "lines": lines, "errors": errors}


def validate_draft(draft: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    for key in ("entry", "fields"):
        if key not in draft:
            errors.append(f"draft missing '{key}'")
    if "entry" in draft and "id" not in draft["entry"]:
        errors.append("draft.entry missing 'id'")
    return errors


def _load_source_text(sha: str) -> str:
    return (SOURCE_TEXT_DIR / f"{sha}.txt").read_text(encoding="utf-8")


def _verify_field(field_path: str, payload: dict[str, Any]) -> tuple[dict[str, Any] | None, str | None]:
    evidence = payload.get("evidence", "")
    source = payload.get("source", "")
    if not evidence or not source:
        return None, f"{field_path}: missing evidence or source"
    if not (SOURCES_DIR / f"{source}.json").is_file():
        return None, f"{field_path}: unknown source {source}"
    if not evidence_in_source(evidence, _load_source_text(source)):
        return None, f"{field_path}: evidence not found in source {source[:8]}"
    out = dict(payload)
    meta = json.loads((SOURCES_DIR / f"{source}.json").read_text(encoding="utf-8"))
    st = meta.get("source_type", "other")
    out["confidence"] = 0.9 if st in ("manual", "maker_datasheet") else 0.6
    return out, None


def verify_draft(draft: dict[str, Any]) -> tuple[dict[str, Any], list[str]]:
    errors: list[str] = []
    entry = dict(draft["entry"])
    fields = draft["fields"]
    specs: dict[str, Any] = {}
    for attr, spec in fields.get("specs", {}).items():
        v, err = _verify_field(f"specs.{attr}", spec)
        if err:
            errors.append(err)
        elif v:
            specs[attr] = v
    entry["specs"] = specs
    if "description" in fields:
        v, err = _verify_field("description", fields["description"])
        if err:
            errors.append(err)
        elif v:
            entry["description"] = v.get("value", v.get("raw"))
    source_hashes = set(entry.get("sources", []))
    for spec in specs.values():
        source_hashes.add(spec["source"])
    confidences = [s["confidence"] for s in specs.values()]
    if confidences:
        entry["confidence"] = min(confidences)
    else:
        errors.append("no verified spec fields")
    entry["sources"] = sorted(source_hashes)
    cat = entry.get("category")
    if cat:
        for req in required_specs(cat):
            if req not in specs:
                errors.append(f"missing required spec '{req}' after verify")
    return {"entry": entry, "run_id": draft.get("run_id")}, errors


def write_entry(verified: dict[str, Any], run_id: str) -> tuple[Path, bool]:
    entry = dict(verified["entry"])
    if not category_exists(entry["category"]):
        raise ValueError(f"unknown category: {entry['category']}")
    now = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    path = ENTRIES_DIR / entry["category"] / f"{entry['id']}.json"
    if path.is_file():
        existing = json.loads(path.read_text(encoding="utf-8"))
        entry.setdefault("created_at", existing["created_at"])
        history = list(existing.get("history", []))
    else:
        entry.setdefault("created_at", now)
        history = []
    entry["updated_at"] = now
    entry["last_verified_at"] = now
    history.append(
        {
            "change_id": str(uuid.uuid4()),
            "at": now,
            "run_id": run_id,
            "agent": "pipeline",
            "op": "create" if not path.is_file() else "set",
            "path": entry["id"],
            "reason": "verified write",
        }
    )
    entry["history"] = history
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(order_entry(entry), indent=2) + "\n", encoding="utf-8")
    build_graph()
    return path, False


def _strong_id_key(entry: dict[str, Any]) -> str | None:
    ids = entry.get("identifiers") or {}
    if ids.get("gtin"):
        return f"gtin:{ids['gtin']}"
    if ids.get("mpn") and entry.get("maker", {}).get("name"):
        return f"mpn:{slugify_maker(entry['maker']['name'])}:{ids['mpn'].lower()}"
    return None


def _append_flag(record: dict[str, Any]) -> None:
    MERGE_CANDIDATES_PATH.parent.mkdir(parents=True, exist_ok=True)
    with MERGE_CANDIDATES_PATH.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(record, separators=(",", ":")) + "\n")


def run_dedup(run_id: str) -> dict[str, Any]:
    entries = []
    for path in ENTRIES_DIR.rglob("*.json"):
        entries.append(json.loads(path.read_text(encoding="utf-8")))
    by_strong: dict[str, list[dict[str, Any]]] = {}
    for e in entries:
        key = _strong_id_key(e)
        if key:
            by_strong.setdefault(key, []).append(e)
    merged_ids: list[str] = []
    flags: list[dict[str, Any]] = []
    for group in by_strong.values():
        if len(group) < 2:
            continue
        primary = group[0]
        for other in group[1:]:
            merged = dict(primary)
            merged["sources"] = sorted(set(primary.get("sources", [])) | set(other.get("sources", [])))
            specs = dict(primary.get("specs", {}))
            specs.update(other.get("specs", {}))
            merged["specs"] = specs
            merged.setdefault("history", []).append(
                {
                    "change_id": f"merge-{run_id}",
                    "at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
                    "run_id": run_id,
                    "agent": "pipeline",
                    "op": "merge",
                    "path": other["id"],
                    "reason": "strong identifier match",
                }
            )
            out = ENTRIES_DIR / merged["category"] / f"{merged['id']}.json"
            out.write_text(json.dumps(order_entry(merged), indent=2) + "\n", encoding="utf-8")
            other_path = ENTRIES_DIR / other["category"] / f"{other['id']}.json"
            if other_path.is_file() and other["id"] != merged["id"]:
                other_path.unlink()
            merged_ids.append(other["id"])
    seen: set[frozenset[str]] = set()
    for i, a in enumerate(entries):
        for b in entries[i + 1 :]:
            if _strong_id_key(a) and _strong_id_key(a) == _strong_id_key(b):
                continue
            ka = slugify_maker(a.get("maker", {}).get("name", "")) + ":" + (a.get("identifiers", {}).get("mpn") or "")
            kb = slugify_maker(b.get("maker", {}).get("name", "")) + ":" + (b.get("identifiers", {}).get("mpn") or "")
            if ka and ka == kb:
                pair = frozenset({a["id"], b["id"]})
                if pair not in seen:
                    seen.add(pair)
                    rec = {"run_id": run_id, "reason": "maker_model_match", "ids": [a["id"], b["id"]]}
                    _append_flag(rec)
                    flags.append(rec)
    return {"auto_merged": merged_ids, "flagged": flags}

# References:
# [2] No source, no field — verify before write.
# [10] Strong-ID auto-merge only; other pairs flagged.
# [17] Write-after-verify gate.
