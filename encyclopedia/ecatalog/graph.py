from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from ecatalog.io import ROOT, SOURCES_DIR, sha256_text, iter_entries

GRAPH_DIR = ROOT / "graph"
RELATIONS_PATH = GRAPH_DIR / "relations.json"
NODES_PATH = GRAPH_DIR / "nodes.jsonl"
EDGES_PATH = GRAPH_DIR / "edges.jsonl"

KIND_CATEGORY = {
    "software": "biolink:Software",
    "equipment": "biolink:Device",
    "tool": "biolink:Device",
    "product": "biolink:Product",
    "consumable": "biolink:ChemicalEntity",
    "service": "biolink:Procedure",
}


def entry_curie(entry_id: str) -> str:
    return f"catalog:{entry_id}"


def canonical_line(obj: dict[str, Any]) -> str:
    return json.dumps(obj, sort_keys=True, separators=(",", ":"))


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    body = "\n".join(canonical_line(r) for r in sorted(rows, key=lambda r: r["id"]))
    path.write_text(body + ("\n" if body else ""), encoding="utf-8")


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.is_file():
        return []
    out: list[dict[str, Any]] = []
    for n, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        if line.strip():
            out.append(json.loads(line))
    return out


def load_sigma() -> dict[str, dict[str, str]]:
    data = json.loads(RELATIONS_PATH.read_text(encoding="utf-8"))
    return data["sigma"]


def source_license(sha: str) -> str:
    meta = json.loads((SOURCES_DIR / f"{sha}.json").read_text(encoding="utf-8"))
    if lic := meta.get("license"):
        return lic
    url = meta.get("url", "")
    if "COPYING" in url:
        return "GPL-2.0"
    if "progit" in url:
        return "CC-BY-NC-SA-3.0"
    return "UNKNOWN"


def provenance_item(sha: str) -> dict[str, str]:
    meta = json.loads((SOURCES_DIR / f"{sha}.json").read_text(encoding="utf-8"))
    return {
        "source_id": f"source:{sha}",
        "license": source_license(sha),
        "date": meta.get("retrieved_at", ""),
    }


def observation_from_spec(spec: dict[str, Any]) -> dict[str, Any]:
    sha = spec["source"]
    return {
        "value": spec.get("value"),
        "date": spec.get("observed_at", ""),
        "source_id": f"source:{sha}",
        "quote_hash": sha256_text(spec.get("evidence", "")),
    }


def current_observation(observations: list[dict[str, Any]]) -> dict[str, Any]:
    return max(observations, key=lambda o: (o.get("date", ""), o.get("source_id", "")))


def build_from_entries() -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    nodes: dict[str, dict[str, Any]] = {}
    edges: dict[str, dict[str, Any]] = {}
    for entry in iter_entries():
        cid = entry_curie(entry["id"])
        bl_cat = KIND_CATEGORY.get(entry["kind"], "biolink:NamedThing")
        prov = [provenance_item(s) for s in entry.get("sources", [])]
        nodes[cid] = {
            "id": cid,
            "category": bl_cat,
            "name": entry["name"],
            "provenance": sorted(prov, key=lambda p: p["source_id"]),
        }
        desc = entry.get("description")
        if desc:
            nid = f"{cid}#description"
            obs = []
            for sha in entry.get("sources", []):
                obs.append(
                    {
                        "value": desc,
                        "date": entry.get("updated_at", ""),
                        "source_id": f"source:{sha}",
                        "quote_hash": sha256_text(desc),
                    }
                )
            nodes[nid] = {
                "id": nid,
                "category": "biolink:NarrativeText",
                "name": "description",
                "provenance": sorted(prov, key=lambda p: p["source_id"]),
                "observations": sorted(obs, key=lambda o: (o["date"], o["source_id"])),
            }
            eid = f"edge:{sha256_text(cid + 'biolink:has_description' + nid)}"
            edges[eid] = _edge(
                eid,
                cid,
                "biolink:has_description",
                nid,
                prov,
                entry.get("updated_at", ""),
                sha256_text(desc),
            )
        for attr, spec in (entry.get("specs") or {}).items():
            aid = f"{cid}#attr-{attr}"
            obs = observation_from_spec(spec)
            ks = [provenance_item(spec["source"])]
            nodes[aid] = {
                "id": aid,
                "category": "biolink:Attribute",
                "name": attr,
                "provenance": ks,
                "observations": [obs],
            }
            eid = f"edge:{sha256_text(cid + 'biolink:has_attribute' + aid + obs['quote_hash'])}"
            edges[eid] = _edge(
                eid,
                cid,
                "biolink:has_attribute",
                aid,
                ks,
                spec.get("observed_at", ""),
                obs["quote_hash"],
            )
    return list(nodes.values()), list(edges.values())


def _edge(
    eid: str,
    subject: str,
    predicate: str,
    obj: str,
    knowledge_source: list[dict[str, str]],
    date: str,
    quote_hash: str,
) -> dict[str, Any]:
    return {
        "id": eid,
        "subject": subject,
        "predicate": predicate,
        "object": obj,
        "knowledge_source": sorted(knowledge_source, key=lambda k: k["source_id"]),
        "date": date,
        "quote_hash": quote_hash,
    }


def build_graph() -> dict[str, Any]:
    nodes, edges = build_from_entries()
    write_jsonl(NODES_PATH, nodes)
    write_jsonl(EDGES_PATH, edges)
    return {"nodes": len(nodes), "edges": len(edges)}


def validate_graph(nodes: list[dict[str, Any]] | None = None, edges: list[dict[str, Any]] | None = None) -> list[str]:
    from_disk = nodes is None and edges is None
    nodes = read_jsonl(NODES_PATH) if nodes is None else nodes
    edges = read_jsonl(EDGES_PATH) if edges is None else edges
    errors: list[str] = []
    sigma = load_sigma()
    node_ids = {n["id"] for n in nodes}
    node_cat = {n["id"]: n["category"] for n in nodes}
    allowed_predicates = set(sigma.keys())

    for i, edge in enumerate(edges, 1):
        eid = edge.get("id", f"line{i}")
        for end in ("subject", "object"):
            if edge.get(end) not in node_ids:
                errors.append(f"edges:{eid}: dangling {end} {edge.get(end)}")
        pred = edge.get("predicate")
        if pred not in allowed_predicates:
            errors.append(f"edges:{eid}: predicate {pred!r} not in closed list")
        ks = edge.get("knowledge_source") or []
        if not ks:
            errors.append(f"edges:{eid}: knowledge_source empty")
        if pred in sigma:
            dom, rng = sigma[pred]["domain"], sigma[pred]["range"]
            sub, obj = edge.get("subject"), edge.get("object")
            if sub in node_cat and obj in node_cat:
                if (node_cat[sub], node_cat[obj]) != (dom, rng):
                    errors.append(
                        f"edges:{eid}: sigma mismatch got ({node_cat[sub]}, {node_cat[obj]}) want ({dom}, {rng})"
                    )

    if from_disk:
        if NODES_PATH.is_file() and NODES_PATH.read_bytes() != canonical_bytes(nodes):
            errors.append("nodes.jsonl: not canonical (keys/lines order)")
        if EDGES_PATH.is_file() and EDGES_PATH.read_bytes() != canonical_bytes(edges):
            errors.append("edges.jsonl: not canonical (keys/lines order)")
    return errors


def canonical_bytes(rows: list[dict[str, Any]]) -> bytes:
    body = "\n".join(canonical_line(r) for r in sorted(rows, key=lambda r: r["id"]))
    return (body + ("\n" if body else "")).encode("utf-8")


def _prov_key(p: dict[str, str]) -> tuple[str, str, str]:
    return (p.get("source_id", ""), p.get("license", ""), p.get("date", ""))


def _obs_key(o: dict[str, Any]) -> tuple[Any, ...]:
    return (o.get("date", ""), o.get("source_id", ""), o.get("quote_hash", ""), json.dumps(o.get("value"), sort_keys=True))


def merge_nodes(a: dict[str, dict[str, Any]], b: dict[str, dict[str, Any]]) -> dict[str, dict[str, Any]]:
    out = {k: dict(v) for k, v in a.items()}
    for nid, node in b.items():
        if nid not in out:
            out[nid] = dict(node)
            continue
        merged = dict(out[nid])
        pset = {_prov_key(p) for p in merged.get("provenance", [])}
        for p in node.get("provenance", []):
            if _prov_key(p) not in pset:
                merged.setdefault("provenance", []).append(p)
                pset.add(_prov_key(p))
        oset = {_obs_key(o) for o in merged.get("observations", [])}
        for o in node.get("observations", []):
            if _obs_key(o) not in oset:
                merged.setdefault("observations", []).append(o)
                oset.add(_obs_key(o))
        merged["provenance"] = sorted(merged.get("provenance", []), key=_prov_key)
        if "observations" in merged:
            merged["observations"] = sorted(merged["observations"], key=_obs_key)
        out[nid] = merged
    return out


def merge_edges(a: dict[str, dict[str, Any]], b: dict[str, dict[str, Any]]) -> dict[str, dict[str, Any]]:
    out = {k: dict(v) for k, v in a.items()}
    for eid, edge in b.items():
        if eid not in out:
            out[eid] = dict(edge)
            continue
        merged = dict(out[eid])
        kset = {_prov_key(k) for k in merged.get("knowledge_source", [])}
        for k in edge.get("knowledge_source", []):
            if _prov_key(k) not in kset:
                merged.setdefault("knowledge_source", []).append(k)
                kset.add(_prov_key(k))
        merged["knowledge_source"] = sorted(merged["knowledge_source"], key=_prov_key)
        out[eid] = merged
    return out


def merge_graphs(
    nodes_a: list[dict[str, Any]], edges_a: list[dict[str, Any]], nodes_b: list[dict[str, Any]], edges_b: list[dict[str, Any]]
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    nd = merge_nodes({n["id"]: n for n in nodes_a}, {n["id"]: n for n in nodes_b})
    ed = merge_edges({e["id"]: e for e in edges_a}, {e["id"]: e for e in edges_b})
    return list(nd.values()), list(ed.values())

# References:
# [18] Content-addressed quote_hash ties edges to snapshot text.
