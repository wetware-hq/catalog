from __future__ import annotations

import copy
import json
from pathlib import Path

import pytest
from hypothesis import given, strategies as st

from ecatalog.graph import (
    EDGES_PATH,
    NODES_PATH,
    active_edges,
    build_graph,
    canonical_bytes,
    canonical_line,
    edge_identity_id,
    ensure_edge_id,
    is_subsumed_by,
    load_vocabulary,
    merge_edges,
    merge_graphs,
    merge_nodes,
    read_jsonl,
    transitive_closure_pairs,
    validate_graph,
)

ROOT = Path(__file__).resolve().parent.parent
TOY = Path(__file__).resolve().parent / "fixtures" / "toy"


def _ks():
    return [{"source_hash": "x", "date": "t", "licence": "CC0-1.0"}]


def test_check1_dangling_endpoint_smallest():
    vocab = load_vocabulary()
    nodes = [{"id": "catalog:a", "category": ["biolink:Software"], "name": "A", "provenance": _ks()}]
    edges = [
        ensure_edge_id(
            {
                "subject": "catalog:a",
                "predicate": "biolink:has_attribute",
                "object": "catalog:missing",
                "knowledge_source": _ks(),
                "date": "t",
                "quote_hash": "abc",
                "qualifiers": {},
            }
        )
    ]
    errs = validate_graph(nodes, edges, vocab=vocab)
    assert any("dangling object" in e for e in errs)


def test_literal_object_not_dangling():
    vocab = load_vocabulary()
    nodes = [{"id": "catalog:a", "category": ["biolink:Software"], "name": "A", "provenance": _ks()}]
    edges = [
        ensure_edge_id(
            {
                "subject": "catalog:a",
                "predicate": "biolink:has_attribute",
                "object": {"literal": True, "value": 1, "category": ["biolink:Attribute"]},
                "knowledge_source": _ks(),
                "date": "t",
                "quote_hash": "abc",
                "qualifiers": {},
            }
        )
    ]
    errs = validate_graph(nodes, edges, vocab=vocab)
    assert not any("dangling object" in e for e in errs)


def test_check2_predicate_not_closed():
    vocab = load_vocabulary()
    nodes = [{"id": "catalog:a", "category": ["biolink:Software"], "name": "A", "provenance": _ks()}]
    edges = [
        ensure_edge_id(
            {
                "subject": "catalog:a",
                "predicate": "biolink:unknown_pred",
                "object": {"literal": True, "value": 1, "category": ["biolink:Attribute"]},
                "knowledge_source": _ks(),
                "date": "t",
                "quote_hash": "abc",
                "qualifiers": {},
            }
        )
    ]
    assert any("not in closed list" in e for e in validate_graph(nodes, edges, vocab=vocab))


def test_check3_empty_knowledge_source():
    vocab = load_vocabulary()
    nodes = [{"id": "catalog:a", "category": ["biolink:Software"], "name": "A", "provenance": _ks()}]
    edges = [
        ensure_edge_id(
            {
                "subject": "catalog:a",
                "predicate": "biolink:has_attribute",
                "object": {"literal": True, "value": 1, "category": ["biolink:Attribute"]},
                "knowledge_source": [],
                "date": "t",
                "quote_hash": "abc",
                "qualifiers": {},
            }
        )
    ]
    assert any("knowledge_source empty" in e for e in validate_graph(nodes, edges, vocab=vocab))


def test_check4_sigma_subsumption_fail():
    vocab = load_vocabulary()
    nodes = [{"id": "catalog:a", "category": ["biolink:Software"], "name": "A", "provenance": _ks()}]
    edges = [
        ensure_edge_id(
            {
                "subject": "catalog:a",
                "predicate": "biolink:has_attribute",
                "object": {"literal": True, "value": "x", "category": ["biolink:NarrativeText"]},
                "knowledge_source": _ks(),
                "date": "t",
                "quote_hash": "abc",
                "qualifiers": {},
            }
        )
    ]
    assert any("sigma type check failed" in e for e in validate_graph(nodes, edges, vocab=vocab))


def test_small_molecule_subsumes_chemical_entity_domain():
    vocab = load_vocabulary()
    assert is_subsumed_by(vocab, ["biolink:SmallMolecule"], "biolink:ChemicalEntity")
    nodes = [{"id": "catalog:m", "category": ["biolink:SmallMolecule"], "name": "M", "provenance": _ks()}]
    edges = [
        ensure_edge_id(
            {
                "subject": "catalog:m",
                "predicate": "biolink:has_attribute",
                "object": {"literal": True, "value": 123, "category": ["biolink:ChemicalEntity"]},
                "knowledge_source": _ks(),
                "date": "t",
                "quote_hash": "abc",
                "qualifiers": {},
            }
        )
    ]
    assert validate_graph(nodes, edges, vocab=vocab) == []


def test_qualifiers_change_edge_identity():
    base = {
        "subject": "catalog:a",
        "predicate": "biolink:has_attribute",
        "object": {"literal": True, "value": 1, "category": ["biolink:Attribute"]},
        "knowledge_source": _ks(),
        "date": "t",
        "quote_hash": "abc",
    }
    e1 = ensure_edge_id({**base, "qualifiers": {}})
    e2 = ensure_edge_id({**base, "qualifiers": {"negated": True}})
    assert e1["id"] != e2["id"]


def test_supersedes_hides_edge_in_view():
    vocab = load_vocabulary()
    live = ensure_edge_id(
        {
            "subject": "catalog:a",
            "predicate": "biolink:has_attribute",
            "object": {"literal": True, "value": 1, "category": ["biolink:Attribute"]},
            "knowledge_source": _ks(),
            "date": "t",
            "quote_hash": "abc",
            "qualifiers": {},
        }
    )
    sup = ensure_edge_id(
        {
            "subject": "catalog:a",
            "predicate": "catalog:supersedes",
            "object": live["id"],
            "knowledge_source": _ks(),
            "date": "t2",
            "quote_hash": "def",
            "qualifiers": {},
        }
    )
    active = active_edges([live, sup], vocab)
    assert all(e["id"] != live["id"] for e in active)


def test_transitive_only_when_marked():
    vocab = load_vocabulary(TOY / "vocabulary.json")
    e1 = ensure_edge_id(
        {
            "subject": "ex:a",
            "predicate": "ex:relatedTo",
            "object": "ex:b",
            "knowledge_source": _ks(),
            "date": "t",
            "quote_hash": "1",
            "qualifiers": {},
        }
    )
    e2 = ensure_edge_id(
        {
            "subject": "ex:b",
            "predicate": "ex:relatedTo",
            "object": "ex:c",
            "knowledge_source": _ks(),
            "date": "t",
            "quote_hash": "2",
            "qualifiers": {},
        }
    )
    derived = transitive_closure_pairs([e1, e2], vocab)
    assert ("ex:a", "ex:relatedTo", "ex:c") in derived


def test_toy_vocabulary_fixture_passes_without_code_changes():
    vocab = load_vocabulary(TOY / "vocabulary.json")
    nodes = read_jsonl(TOY / "nodes.jsonl")
    edge = ensure_edge_id(
        {
            "subject": "ex:paper-1",
            "predicate": "ex:authoredBy",
            "object": "ex:author-1",
            "knowledge_source": _ks(),
            "date": "2026-01-01T00:00:00Z",
            "quote_hash": "q",
            "qualifiers": {},
        }
    )
    assert validate_graph(nodes, [edge], vocab=vocab) == []


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
        "category": ["biolink:Software"],
        "name": "n",
        "provenance": [{"source_hash": "a", "licence": "CC0-1.0", "date": "1"}],
    }
    extra = {
        "id": "catalog:n",
        "category": ["biolink:Software"],
        "name": "n",
        "provenance": [{"source_hash": "b", "licence": "CC0-1.0", "date": "2"}],
    }
    ab = merge_nodes({"catalog:n": copy.deepcopy(base)}, {"catalog:n": copy.deepcopy(extra)})
    ba = merge_nodes({"catalog:n": copy.deepcopy(extra)}, {"catalog:n": copy.deepcopy(base)})
    assert canonical_line(ab["catalog:n"]) == canonical_line(ba["catalog:n"])


def test_merge_associative_and_idempotent():
    n1 = {"catalog:x": {"id": "catalog:x", "category": ["biolink:Software"], "name": "x", "provenance": []}}
    n2 = {
        "catalog:x": {
            "id": "catalog:x",
            "category": ["biolink:Software"],
            "name": "x",
            "provenance": [{"source_hash": "1", "licence": "CC0-1.0", "date": "t"}],
        }
    }
    n3 = {
        "catalog:x": {
            "id": "catalog:x",
            "category": ["biolink:Software"],
            "name": "x",
            "provenance": [{"source_hash": "2", "licence": "CC0-1.0", "date": "t2"}],
        }
    }
    left = merge_nodes(merge_nodes(n1, n2), n3)
    right = merge_nodes(n1, merge_nodes(n2, n3))
    assert canonical_line(left["catalog:x"]) == canonical_line(right["catalog:x"])
    once = merge_nodes(left, left)
    assert canonical_line(once["catalog:x"]) == canonical_line(left["catalog:x"])
