import { readFileSync } from "node:fs";
import { join, dirname } from "node:path";
import { fileURLToPath } from "node:url";
import test from "node:test";
import assert from "node:assert/strict";
import { validateGraph, sortKeys, mergeGraphs } from "../src/check.js";

const root = join(dirname(fileURLToPath(import.meta.url)), "..");
const graphDir = join(root, "graph");

function loadVocab() {
  return {
    relations: JSON.parse(readFileSync(join(graphDir, "relations.json"), "utf8")),
    categories: JSON.parse(readFileSync(join(graphDir, "categories.json"), "utf8")),
  };
}

const SRC = [{ source: "ref-1", date: "2026-01-01", licence: "CC0-1.0" }];

function node(id, extra = {}) {
  return sortKeys({
    id,
    category: ["item"],
    properties: {},
    sources: SRC,
    ...extra,
  });
}

function edge(subj, pred, obj, extra = {}) {
  return sortKeys({
    subject: subj,
    predicate: pred,
    object: obj,
    qualifiers: {},
    sources: SRC,
    ...extra,
  });
}

function asGraph(nodes, edges) {
  const sortedNodes = [...nodes].sort((a, b) => a.id.localeCompare(b.id));
  const sortedEdges = [...edges].sort((a, b) =>
    [a.subject, a.predicate, a.object, JSON.stringify(a.qualifiers ?? {})].join("\0")
      .localeCompare([b.subject, b.predicate, b.object, JSON.stringify(b.qualifiers ?? {})].join("\0")),
  );
  return {
    nodesText: sortedNodes.map((n) => JSON.stringify(n)).join("\n"),
    edgesText: sortedEdges.map((e) => JSON.stringify(e)).join("\n"),
    ...loadVocab(),
  };
}

test("empty graph passes validation", () => {
  const vocab = loadVocab();
  const issues = validateGraph({
    nodesText: readFileSync(join(graphDir, "nodes.jsonl"), "utf8"),
    edgesText: readFileSync(join(graphDir, "edges.jsonl"), "utf8"),
    ...vocab,
  });
  assert.deepEqual(issues, []);
});

test("missing edge endpoint fails", () => {
  const issues = validateGraph(
    asGraph([node("a")], [edge("a", "links_to", "missing")]),
  );
  assert.ok(issues.some((m) => m.includes('object node "missing" missing')));
});

test("unknown predicate fails", () => {
  const issues = validateGraph(
    asGraph([node("a"), node("b")], [edge("a", "unknown_pred", "b")]),
  );
  assert.ok(issues.some((m) => m.includes('unknown predicate "unknown_pred"')));
});

test("domain/range violation fails", () => {
  const n = node("a", { category: ["entity"] });
  const issues = validateGraph(asGraph([n, node("b")], [edge("a", "links_to", "b")]));
  assert.ok(issues.some((m) => m.includes("domain/range")));
});

test("missing node source fails", () => {
  const bad = node("a", { sources: [] });
  const issues = validateGraph(asGraph([bad], []));
  assert.ok(issues.some((m) => m.includes("at least one source required")));
});

test("missing edge source fails", () => {
  const issues = validateGraph(
    asGraph([node("a"), node("b")], [edge("a", "links_to", "b", { sources: [] })]),
  );
  assert.ok(issues.some((m) => m.includes("at least one source required")));
});

test("non-canonical node line order fails", () => {
  const vocab = loadVocab();
  const b = node("b");
  const a = node("a");
  const issues = validateGraph({
    nodesText: [JSON.stringify(b), JSON.stringify(a)].join("\n"),
    edgesText: "",
    ...vocab,
  });
  assert.ok(issues.some((m) => m.includes("not sorted")));
});

test("non-canonical key order fails", () => {
  const vocab = loadVocab();
  const raw = '{"id":"a","category":["item"],"properties":{},"sources":[{"date":"2026-01-01","licence":"CC0-1.0","source":"ref-1"}]}';
  const issues = validateGraph({ nodesText: raw, edgesText: "", ...vocab });
  assert.ok(issues.some((m) => m.includes("not canonical")));
});

test("merge is commutative, associative, and idempotent", () => {
  const g1 = {
    nodes: [node("a"), node("b")],
    edges: [edge("a", "links_to", "b")],
  };
  const g2 = {
    nodes: [node("b"), node("c")],
    edges: [edge("b", "links_to", "c")],
  };
  const g3 = { nodes: [node("d")], edges: [] };

  const ab = mergeGraphs(g1, g2);
  const ba = mergeGraphs(g2, g1);
  assert.deepEqual(ab, ba);

  const ab_c = mergeGraphs(ab, g3);
  const a_bc = mergeGraphs(g1, mergeGraphs(g2, g3));
  assert.deepEqual(ab_c, a_bc);

  const once = mergeGraphs(g1, g1);
  const idempotent = mergeGraphs(g1, once);
  assert.deepEqual(once, idempotent);
  assert.deepEqual(once.nodes.map((n) => n.id), ["a", "b"]);
  assert.equal(once.edges.length, 1);
});
