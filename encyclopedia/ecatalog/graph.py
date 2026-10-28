from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from ecatalog.io import ROOT, SOURCES_DIR, sha256_text, iter_entries

GRAPH_DIR = ROOT / "graph"
VOCABULARY_PATH = GRAPH_DIR / "vocabulary.json"
NODES_PATH = GRAPH_DIR / "nodes.jsonl"
EDGES_PATH = GRAPH_DIR / "edges.jsonl"


def load_vocabulary(path: Path | None = None) -> dict[str, Any]:
    return json.loads((path or VOCABULARY_PATH).read_text(encoding="utf-8"))


def canonical_line(obj: dict[str, Any]) -> str:
    return json.dumps(obj, sort_keys=True, separators=(",", ":"))


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.is_file():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    body = "\n".join(canonical_line(r) for r in sorted(rows, key=lambda r: r["id"]))
    path.write_text(body + ("\n" if body else ""), encoding="utf-8")


def append_jsonl(path: Path, row: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as fh:
        fh.write(canonical_line(row) + "\n")


def categories_of(node_or_literal: dict[str, Any] | list[str]) -> list[str]:
    if isinstance(node_or_literal, list):
        cats = node_or_literal
    else:
        cats = node_or_literal.get("category", [])
    if isinstance(cats, str):
        cats = [cats]
    if not cats:
        raise ValueError("category must be a non-empty list")
    return cats


def ancestor_set(vocab: dict[str, Any], category: str) -> set[str]:
    closure = vocab.get("category_closure", {})
    seen = {category}
    stack = list(closure.get(category, []))
    while stack:
        cur = stack.pop()
        if cur in seen:
            continue
        seen.add(cur)
        stack.extend(closure.get(cur, []))
    return seen


def is_subsumed_by(vocab: dict[str, Any], subject_categories: list[str], required: str) -> bool:
    for cat in subject_categories:
        if required in ancestor_set(vocab, cat):
            return True
    return False


def is_literal(obj: Any) -> bool:
    return isinstance(obj, dict) and obj.get("literal") is True


def is_node_ref(obj: Any, vocab: dict[str, Any]) -> bool:
    if not isinstance(obj, str):
        return False
    prefixes = list(vocab.get("prefixes", {}).keys()) + ["catalog", "source", "edge", "ex"]
    return any(obj.startswith(f"{p}:") for p in prefixes)


def object_categories(vocab: dict[str, Any], obj: Any, node_index: dict[str, dict[str, Any]]) -> list[str]:
    if is_literal(obj):
        cats = obj.get("category", [])
        if isinstance(cats, str):
            cats = [cats]
        return cats or vocab.get("catalog_mapping", {}).get("literal_value_categories", ["biolink:NamedThing"])
    if isinstance(obj, str) and obj in node_index:
        return categories_of(node_index[obj])
    return []


def canonical_qualifiers(qualifiers: dict[str, Any]) -> str:
    return json.dumps(qualifiers or {}, sort_keys=True, separators=(",", ":"))


def edge_sort_key(edge: dict[str, Any]) -> tuple[Any, ...]:
    obj = edge.get("object")
    obj_key = canonical_line(obj) if isinstance(obj, dict) else obj
    return (
        edge.get("subject"),
        edge.get("predicate"),
        obj_key,
        canonical_qualifiers(edge.get("qualifiers") or {}),
    )


def edge_identity_id(edge: dict[str, Any]) -> str:
    payload = json.dumps(edge_sort_key(edge), sort_keys=True, separators=(",", ":"))
    return f"edge:{sha256_text(payload)}"


def ensure_edge_id(edge: dict[str, Any]) -> dict[str, Any]:
    out = dict(edge)
    out.setdefault("qualifiers", {})
    out["id"] = edge_identity_id(out)
    return out


def provenance_from_source(vocab: dict[str, Any], sha: str) -> dict[str, str]:
    meta = json.loads((SOURCES_DIR / f"{sha}.json").read_text(encoding="utf-8"))
    licence = meta.get("licence") or meta.get("license")
    if not licence:
        for rule in vocab.get("licence_rules", []):
            if rule.get("url_contains", "") in meta.get("url", ""):
                licence = rule["licence"]
                break
    return {
        "source_hash": sha,
        "date": meta.get("retrieved_at", ""),
        "licence": licence or vocab.get("default_licence", "UNKNOWN"),
    }


def knowledge_source_from_provenance(prov: list[dict[str, str]]) -> list[dict[str, str]]:
    return sorted(
        [
            {
                "source_hash": p["source_hash"],
                "date": p["date"],
                "licence": p["licence"],
            }
            for p in prov
        ],
        key=lambda k: (k["source_hash"], k["date"], k["licence"]),
    )


def sigma_match(
    vocab: dict[str, Any],
    predicate: str,
    subj_cats: list[str],
    obj_cats: list[str],
) -> bool:
    spec = vocab["predicates"].get(predicate)
    if not spec:
        return False
    for pair in spec.get("pairs", []):
        dom, rng = pair["domain"], pair["range"]
        if not is_subsumed_by(vocab, subj_cats, dom):
            continue
        if obj_cats and is_subsumed_by(vocab, obj_cats, rng):
            return True
    return False


def active_edge_ids(edges: list[dict[str, Any]], vocab: dict[str, Any]) -> set[str]:
    supers = vocab.get("supersedes_predicate", "catalog:supersedes")
    inactive: set[str] = set()
    for e in edges:
        if e.get("predicate") == supers and isinstance(e.get("object"), str):
            inactive.add(e["object"])
    return {e["id"] for e in edges if e["id"] not in inactive}


def active_edges(edges: list[dict[str, Any]], vocab: dict[str, Any]) -> list[dict[str, Any]]:
    active = active_edge_ids(edges, vocab)
    return [e for e in edges if e["id"] in active]


def transitive_closure_pairs(
    edges: list[dict[str, Any]], vocab: dict[str, Any]
) -> set[tuple[str, str, str]]:
    """Derive (subject, predicate, object) pairs for predicates marked transitive only."""
    derived: set[tuple[str, str, str]] = set()
    preds = {
        p
        for p, meta in vocab.get("predicates", {}).items()
        if meta.get("transitive")
    }
    if not preds:
        return derived
    live = active_edges(edges, vocab)
    by_pred: dict[str, list[tuple[str, str]]] = {p: [] for p in preds}
    for e in live:
        if e["predicate"] in preds and isinstance(e["object"], str):
            by_pred[e["predicate"]].append((e["subject"], e["object"]))
    for pred, pairs in by_pred.items():
        graph = pairs
        for s, o in graph:
            derived.add((s, pred, o))
        changed = True
        while changed:
            changed = False
            for a, b in list(graph):
                for _s, c in graph:
                    if _s == b and (a, c) not in graph:
                        graph.append((a, c))
                        derived.add((a, pred, c))
                        changed = True
    return derived


def validate_graph(
    nodes: list[dict[str, Any]] | None = None,
    edges: list[dict[str, Any]] | None = None,
    *,
    vocab: dict[str, Any] | None = None,
    nodes_path: Path = NODES_PATH,
    edges_path: Path = EDGES_PATH,
) -> list[str]:
    vocab = vocab or load_vocabulary()
    from_disk = nodes is None and edges is None
    nodes = read_jsonl(nodes_path) if nodes is None else nodes
    edges = read_jsonl(edges_path) if edges is None else edges
    errors: list[str] = []
    node_index = {n["id"]: n for n in nodes}
    allowed_predicates = set(vocab.get("predicates", {}))

    for n in nodes:
        try:
            categories_of(n)
        except ValueError:
            errors.append(f"nodes:{n.get('id')}: empty category list")
        for p in n.get("provenance", []):
            if not p.get("source_hash") or not p.get("date") or not p.get("licence"):
                errors.append(f"nodes:{n.get('id')}: provenance entry needs source_hash, date, licence")

    seen_ids: set[str] = set()
    for edge in edges:
        eid = edge.get("id") or edge_identity_id(edge)
        if eid in seen_ids:
            errors.append(f"edges:{eid}: duplicate identity")
        seen_ids.add(eid)
        if edge_identity_id(edge) != eid:
            errors.append(f"edges:{eid}: id does not match (subject,predicate,object,qualifiers)")

        pred = edge.get("predicate")
        if pred not in allowed_predicates:
            errors.append(f"edges:{eid}: predicate {pred!r} not in closed list")
        ks = edge.get("knowledge_source") or []
        if not ks:
            errors.append(f"edges:{eid}: knowledge_source empty (fail closed)")
        for k in ks:
            if not k.get("source_hash") or not k.get("date") or not k.get("licence"):
                errors.append(f"edges:{eid}: knowledge_source entry incomplete")

        sub = edge.get("subject")
        if is_node_ref(sub, vocab) and sub not in node_index:
            errors.append(f"edges:{eid}: dangling subject {sub}")
        obj = edge.get("object")
        if is_node_ref(obj, vocab) and obj not in node_index:
            errors.append(f"edges:{eid}: dangling object {obj}")

        if pred in allowed_predicates and is_node_ref(sub, vocab):
            sub_cats = categories_of(node_index[sub])
            obj_cats = object_categories(vocab, obj, node_index)
            if obj_cats and not sigma_match(vocab, pred, sub_cats, obj_cats):
                errors.append(f"edges:{eid}: sigma type check failed")

    if from_disk:
        if nodes_path.is_file() and nodes_path.read_bytes() != canonical_bytes(nodes):
            errors.append(f"{nodes_path.name}: not canonical")
        if edges_path.is_file() and edges_path.read_bytes() != canonical_bytes(edges):
            errors.append(f"{edges_path.name}: not canonical")
    return errors


def canonical_bytes(rows: list[dict[str, Any]]) -> bytes:
    body = "\n".join(canonical_line(r) for r in sorted(rows, key=lambda r: r["id"]))
    return (body + ("\n" if body else "")).encode("utf-8")


def entry_curie(vocab: dict[str, Any], entry_id: str) -> str:
    prefix = vocab.get("catalog_mapping", {}).get("entry_id_prefix", "catalog")
    return f"{prefix}:{entry_id}"


def _literal_object(vocab: dict[str, Any], spec: dict[str, Any], attr: str) -> dict[str, Any]:
    val = spec.get("value")
    unit = spec.get("unit")
    obj: dict[str, Any] = {
        "literal": True,
        "value": val,
        "category": vocab["catalog_mapping"].get("literal_value_categories", ["biolink:Attribute"]),
    }
    if unit:
        obj["unit"] = unit
    obj["attribute"] = attr
    return obj


def build_from_entries(vocab: dict[str, Any] | None = None) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    vocab = vocab or load_vocabulary()
    mapping = vocab.get("catalog_mapping")
    if not mapping:
        return [], []
    nodes: dict[str, dict[str, Any]] = {}
    edges: list[dict[str, Any]] = []
    for entry in iter_entries():
        cid = entry_curie(vocab, entry["id"])
        cats = mapping.get("kind_categories", {}).get(entry["kind"], mapping.get("default_categories", []))
        prov = [provenance_from_source(vocab, s) for s in entry.get("sources", [])]
        nodes[cid] = {
            "id": cid,
            "category": cats,
            "name": entry["name"],
            "provenance": sorted(prov, key=lambda p: p["source_hash"]),
        }
        desc = entry.get("description")
        if desc:
            ks = knowledge_source_from_provenance([provenance_from_source(vocab, entry["sources"][0])])
            e = ensure_edge_id(
                {
                    "subject": cid,
                    "predicate": mapping["description_predicate"],
                    "object": {
                        "literal": True,
                        "value": desc,
                        "category": ["biolink:NarrativeText"],
                    },
                    "knowledge_source": ks,
                    "date": entry.get("updated_at", ""),
                    "quote_hash": sha256_text(desc),
                    "qualifiers": {},
                }
            )
            edges.append(e)
        for attr, spec in (entry.get("specs") or {}).items():
            ks = knowledge_source_from_provenance([provenance_from_source(vocab, spec["source"])])
            e = ensure_edge_id(
                {
                    "subject": cid,
                    "predicate": mapping["spec_predicate"],
                    "object": _literal_object(vocab, spec, attr),
                    "knowledge_source": ks,
                    "date": spec.get("observed_at", ""),
                    "quote_hash": sha256_text(spec.get("evidence", "")),
                    "qualifiers": {"attribute": attr},
                }
            )
            edges.append(e)
    return list(nodes.values()), edges


def build_graph(vocab_path: Path | None = None) -> dict[str, Any]:
    vocab = load_vocabulary(vocab_path)
    nodes, edges = build_from_entries(vocab)
    write_jsonl(NODES_PATH, nodes)
    write_jsonl(EDGES_PATH, edges)
    return {"nodes": len(nodes), "edges": len(edges)}


def merge_nodes(a: dict[str, dict[str, Any]], b: dict[str, dict[str, Any]]) -> dict[str, dict[str, Any]]:
    out = {k: dict(v) for k, v in a.items()}

    def pk(p: dict[str, str]) -> tuple[str, str, str]:
        return (p["source_hash"], p["date"], p["licence"])

    for nid, node in b.items():
        if nid not in out:
            out[nid] = dict(node)
            continue
        merged = dict(out[nid])
        seen = {pk(p) for p in merged.get("provenance", [])}
        for p in node.get("provenance", []):
            if pk(p) not in seen:
                merged.setdefault("provenance", []).append(p)
                seen.add(pk(p))
        merged["provenance"] = sorted(merged.get("provenance", []), key=pk)
        out[nid] = merged
    return out


def merge_edges(a: dict[str, dict[str, Any]], b: dict[str, dict[str, Any]]) -> dict[str, dict[str, Any]]:
    out = {edge_identity_id(v): dict(v) for v in a.values()}

    def kk(k: dict[str, str]) -> tuple[str, str, str]:
        return (k["source_hash"], k["date"], k["licence"])

    for edge in b.values():
        key = edge_identity_id(edge)
        if key not in out:
            out[key] = dict(edge)
            continue
        merged = dict(out[key])
        seen = {kk(x) for x in merged.get("knowledge_source", [])}
        for x in edge.get("knowledge_source", []):
            if kk(x) not in seen:
                merged.setdefault("knowledge_source", []).append(x)
                seen.add(kk(x))
        merged["knowledge_source"] = sorted(merged["knowledge_source"], key=kk)
        out[key] = merged
    return out


def merge_graphs(
    nodes_a: list[dict[str, Any]],
    edges_a: list[dict[str, Any]],
    nodes_b: list[dict[str, Any]],
    edges_b: list[dict[str, Any]],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    nd = merge_nodes({n["id"]: n for n in nodes_a}, {n["id"]: n for n in nodes_b})
    ed = merge_edges({edge_identity_id(e): e for e in edges_a}, {edge_identity_id(e): e for e in edges_b})
    return list(nd.values()), list(ed.values())

# References:
# [18] Content-addressed quote_hash; vocabulary-driven generic graph core.
