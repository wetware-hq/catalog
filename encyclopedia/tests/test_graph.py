from __future__ import annotations

import copy
import json
import shutil
from pathlib import Path

import pytest
from hypothesis import given, strategies as st

from ecatalog.graph import (
    EDGES_PATH,
    NODES_PATH,
    build_graph,
    canonical_bytes,
    canonical_line,
    merge_edges,
    merge_graphs,
    merge_nodes,
    read_jsonl,
    validate_graph,
)

ROOT = Path(__file__).resolve().parent.parent


def test_check1_dangling_endpoint_smallest():
    nodes = [{"id": "catalog:a", "category": "biolink:Software", "name": "A", "provenance": []}]
    edges = [
        {
            "id": "edge:1",
            "subject": "catalog:a",
            "predicate": "biolink:has_attribute",
            "object": "catalog:missing",
            "knowledge_source": [{"source_id": "source:x", "license": "CC0-1.0", "date": "t"}],
            "date": "t",
            "quote_hash": "abc",
        }
    ]
    errs = validate_graph(nodes, edges)
    assert any("dangling object" in e for e in errs)


def test_check2_predicate_not_closed():
    nodes = [
        {"id": "catalog:a", "category": "biolink:Software", "name": "A", "provenance": []},
        {"id": "catalog:a#attr-x", "category": "biolink:Attribute", "name": "x", "provenance": []},
    ]
    edges = [
        {
            "id": "edge:1",
            "subject": "catalog:a",
            "predicate": "biolink:unknown_pred",
            "object": "catalog:a#attr-x",
            "knowledge_source": [{"source_id": "source:x", "license": "CC0-1.0", "date": "t"}],
            "date": "t",
            "quote_hash": "abc",
        }
    ]
    errs = validate_graph(nodes, edges)
    assert any("not in closed list" in e for e in errs)


def test_check3_empty_knowledge_source():
    nodes = [
        {"id": "catalog:a", "category": "biolink:Software", "name": "A", "provenance": []},
        {"id": "catalog:a#attr-x", "category": "biolink:Attribute", "name": "x", "provenance": []},
    ]
    edges = [
        {
            "id": "edge:1",
            "subject": "catalog:a",
            "predicate": "biolink:has_attribute",
            "object": "catalog:a#attr-x",
            "knowledge_source": [],
            "date": "t",
            "quote_hash": "abc",
        }
    ]
    errs = validate_graph(nodes, edges)
    assert any("knowledge_source empty" in e for e in errs)


def test_check4_sigma_mismatch():
    nodes = [
        {"id": "catalog:a", "category": "biolink:Device", "name": "A", "provenance": []},
        {"id": "catalog:a#attr-x", "category": "biolink:Attribute", "name": "x", "provenance": []},
    ]
    edges = [
        {
            "id": "edge:1",
            "subject": "catalog:a",
            "predicate": "biolink:has_attribute",
            "object": "catalog:a#attr-x",
            "knowledge_source": [{"source_id": "source:x", "license": "CC0-1.0", "date": "t"}],
            "date": "t",
            "quote_hash": "abc",
        }
    ]
    errs = validate_graph(nodes, edges)
    assert any("sigma mismatch" in e for e in errs)


def test_check5_non_canonical_bytes(tmp_path: Path):
    nodes = [{"id": "catalog:z", "category": "biolink:Software", "name": "Z", "provenance": []}]
    bad = tmp_path / "nodes.jsonl"
    bad.write_text('{"name":"Z","id":"catalog:z","category":"biolink:Software","provenance":[]}\n', encoding="utf-8")
    parsed = read_jsonl(bad)
    assert bad.read_bytes() != canonical_bytes(parsed)


def test_graph_repopulable_byte_identical():
    build_graph()
    ref_n = canonical_bytes(read_jsonl(NODES_PATH))
    ref_e = canonical_bytes(read_jsonl(EDGES_PATH))
    NODES_PATH.unlink(missing_ok=True)
    EDGES_PATH.unlink(missing_ok=True)
    build_graph()
    assert NODES_PATH.read_bytes() == ref_n
    assert EDGES_PATH.read_bytes() == ref_e
    assert validate_graph() == []


@given(st.data())
def test_merge_commutative(data):
    base = {
        "id": "catalog:n",
        "category": "biolink:Software",
        "name": "n",
        "provenance": [{"source_id": "source:a", "license": "CC0-1.0", "date": "1"}],
    }
    extra = {
        "id": "catalog:n",
        "category": "biolink:Software",
        "name": "n",
        "provenance": [{"source_id": "source:b", "license": "CC0-1.0", "date": "2"}],
    }
    a = {"catalog:n": copy.deepcopy(base)}
    b = {"catalog:n": copy.deepcopy(extra)}
    ab = merge_nodes(a, b)
    ba = merge_nodes(b, a)
    assert canonical_line(ab["catalog:n"]) == canonical_line(ba["catalog:n"])


def test_merge_associative_and_idempotent():
    n1 = {"catalog:x": {"id": "catalog:x", "category": "biolink:Software", "name": "x", "provenance": []}}
    n2 = {
        "catalog:x": {
            "id": "catalog:x",
            "category": "biolink:Software",
            "name": "x",
            "provenance": [{"source_id": "source:1", "license": "CC0-1.0", "date": "t"}],
        }
    }
    n3 = {
        "catalog:x": {
            "id": "catalog:x",
            "category": "biolink:Software",
            "name": "x",
            "provenance": [{"source_id": "source:2", "license": "CC0-1.0", "date": "t2"}],
        }
    }
    left = merge_nodes(merge_nodes(n1, n2), n3)
    right = merge_nodes(n1, merge_nodes(n2, n3))
    assert canonical_line(left["catalog:x"]) == canonical_line(right["catalog:x"])
    once = merge_nodes(left, left)
    assert canonical_line(once["catalog:x"]) == canonical_line(left["catalog:x"])

    e1 = {
        "edge:1": {
            "id": "edge:1",
            "subject": "catalog:x",
            "predicate": "biolink:has_attribute",
            "object": "catalog:x#a",
            "knowledge_source": [{"source_id": "source:1", "license": "CC0-1.0", "date": "t"}],
            "date": "t",
            "quote_hash": "h",
        }
    }
    e2 = {
        "edge:1": {
            "id": "edge:1",
            "subject": "catalog:x",
            "predicate": "biolink:has_attribute",
            "object": "catalog:x#a",
            "knowledge_source": [{"source_id": "source:2", "license": "CC0-1.0", "date": "t2"}],
            "date": "t2",
            "quote_hash": "h",
        }
    }
    merged = merge_edges(e1, e2)
    assert len(merged["edge:1"]["knowledge_source"]) == 2


def test_merge_graphs_property_smoke():
    na = [{"id": "catalog:a", "category": "biolink:Software", "name": "A", "provenance": []}]
    nb = [{"id": "catalog:b", "category": "biolink:Software", "name": "B", "provenance": []}]
    ea, eb = [], []
    n1, e1 = merge_graphs(na, ea, nb, eb)
    n2, e2 = merge_graphs(nb, eb, na, ea)
    assert {x["id"] for x in n1} == {x["id"] for x in n2}
