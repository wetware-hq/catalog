from __future__ import annotations

import hashlib
import json
import re
import urllib.error
import urllib.request
from html import unescape
from pathlib import Path
from typing import Any

import yaml

ROOT = Path(__file__).resolve().parent.parent
CATALOG = ROOT / "catalog"
SCHEMA_PATH = CATALOG / "schema" / "entry.schema.json"
TAXONOMY_PATH = CATALOG / "schema" / "taxonomy.yaml"
ENTRIES_DIR = CATALOG / "entries"
SOURCES_DIR = CATALOG / "sources"
SOURCE_TEXT_DIR = SOURCES_DIR / "text"
MERGE_CANDIDATES_PATH = CATALOG / "queue" / "merge_candidates.jsonl"
REFERENCES_MD = ROOT / "REFERENCES.md"


class CasConflictError(Exception):
    pass


def normalize_source_text(raw: str) -> str:
    text = unescape(raw)
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def evidence_in_source(evidence: str, source_text: str) -> bool:
    ev = re.sub(r"\s+", " ", evidence.strip())
    src = re.sub(r"\s+", " ", source_text)
    return ev in src


def slugify_maker(name: str) -> str:
    s = name.lower().strip()
    s = re.sub(r"[^a-z0-9]+", "-", s)
    return s.strip("-") or "unknown"


def fetch_url(url: str, timeout: float = 60.0) -> tuple[str, int]:
    req = urllib.request.Request(url, headers={"User-Agent": "encyclopedia-catalog/0.1"})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        body = resp.read().decode("utf-8", errors="replace")
        return body, resp.status


def put_text_object(text: str) -> str:
    digest = sha256_text(text)
    SOURCE_TEXT_DIR.mkdir(parents=True, exist_ok=True)
    path = SOURCE_TEXT_DIR / f"{digest}.txt"
    if path.is_file():
        if path.read_text(encoding="utf-8") != text:
            raise CasConflictError(f"sha256 {digest}: content mismatch")
        return digest
    path.write_text(text, encoding="utf-8")
    return digest


def put_source_meta(meta: dict[str, Any]) -> None:
    digest = meta["sha256"]
    SOURCES_DIR.mkdir(parents=True, exist_ok=True)
    meta_path = SOURCES_DIR / f"{digest}.json"
    if meta_path.is_file():
        existing = json.loads(meta_path.read_text(encoding="utf-8"))
        for key in ("url", "title", "source_type", "http_status"):
            if key in existing and key in meta and existing[key] != meta[key]:
                raise CasConflictError(f"{digest}: immutable metadata conflict on {key}")
        return
    meta_path.write_text(json.dumps(meta, indent=2) + "\n", encoding="utf-8")


def load_taxonomy() -> dict[str, Any]:
    data = yaml.safe_load(TAXONOMY_PATH.read_text(encoding="utf-8"))
    return data["categories"]


def category_exists(category: str) -> bool:
    return category in load_taxonomy()


def required_specs(category: str) -> list[str]:
    cats = load_taxonomy()
    req = cats[category]["attributes"]["required"]
    if isinstance(req, list):
        return req
    return list(req.keys())


ENTRY_KEY_ORDER = [
    "schema_version",
    "id",
    "name",
    "aliases",
    "kind",
    "category",
    "tags",
    "maker",
    "identifiers",
    "description",
    "specs",
    "offers",
    "status",
    "confidence",
    "created_at",
    "updated_at",
    "last_verified_at",
    "history",
    "sources",
]


def order_entry(entry: dict[str, Any]) -> dict[str, Any]:
    ordered: dict[str, Any] = {k: entry[k] for k in ENTRY_KEY_ORDER if k in entry}
    for k, v in entry.items():
        if k not in ordered:
            ordered[k] = v
    if "sources" in entry:
        ordered.pop("sources", None)
        ordered["sources"] = entry["sources"]
    return ordered


def iter_entries() -> list[dict[str, Any]]:
    if not ENTRIES_DIR.is_dir():
        return []
    return [json.loads(p.read_text(encoding="utf-8")) for p in sorted(ENTRIES_DIR.rglob("*.json"))]

# References:
# [18] Content-addressed source snapshots (hash = identity).
