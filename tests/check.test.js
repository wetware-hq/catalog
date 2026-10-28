import { readFileSync } from "node:fs";
import { join, dirname } from "node:path";
import { fileURLToPath } from "node:url";
import { spawnSync } from "node:child_process";
import test from "node:test";
import assert from "node:assert/strict";
import {
  validateGraph,
  canonicalLine,
  mergeGraphs,
  serializeGraph,
  validateCategoryVocabulary,
} from "../src/check.js";

const root = join(dirname(fileURLToPath(import.meta.url)), "..");
const graphDir = join(root, "graph");
const checkScript = join(root, "src/check.js");

function loadVocab() {
  return {
    relations: JSON.parse(readFileSync(join(graphDir, "relations.json"), "utf8")),
    categories: JSON.parse(readFileSync(join(graphDir, "categories.json"), "utf8")),
  };
}

const SRC1 = [{ source: "ref-1", date: "2026-01-01", licence: "CC0-1.0" }];
const SRC2 = [{ source: "ref-2", date: "2026-01-02", licence: "CC0-1.0" }];

function node(id, extra = {}) {
  return canonicalLine({ id, category: ["item"], sources: SRC1, ...extra }, "node");
}

function parseNode(line) {
  return JSON.parse(line);
}

function edge(subj, pred, obj, extra = {}) {
  return canonicalLine(
    { subject: subj, predicate: pred, object: obj, qualifiers: {}, sources: SRC1, ...extra },
    "edge",
  );
}

function lit(value) {
  return { value };
}

function asGraph(nodeLines, edgeLines) {
  const nodes = nodeLines.map(parseNode).sort((a, b) => (a.id < b.id ? -1 : a.id > b.id ? 1 : 0));
  return {
    nodesText: nodes.map((n) => canonicalLine(n, "node")).join("\n"),
    edgesText: edgeLines.join("\n"),
    ...loadVocab(),
  };
}

function graphBytes(g) {
  const { nodesText, edgesText } = serializeGraph(g);
  return `${nodesText}\n---\n${edgesText}`;
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

test("CLI validates graph directory", () => {
  const ok = spawnSync(process.execPath, [checkScript, graphDir], { encoding: "utf8" });
  assert.equal(ok.status, 0, ok.stderr);
});

test("missing edge endpoint fails", () => {
  const issues = validateGraph(asGraph([node("a")], [edge("a", "links_to", "missing")]));
  assert.ok(issues.some((m) => m.includes('object node "missing" missing')));
});

test("unknown predicate fails", () => {
  const issues = validateGraph(asGraph([node("a"), node("b")], [edge("a", "unknown_pred", "b")]));
  assert.ok(issues.some((m) => m.includes('unknown predicate "unknown_pred"')));
});

test("domain/range violation fails", () => {
  const n = parseNode(node("a", { category: ["entity"] }));
  const issues = validateGraph(
    asGraph([canonicalLine(n, "node"), node("b")], [edge("a", "links_to", "b")]),
  );
  assert.ok(issues.some((m) => m.includes("domain/range")));
});

test("unknown node category fails without edges", () => {
  const bad = parseNode(node("solo", { category: ["missing_cat"] }));
  const issues = validateGraph(asGraph([canonicalLine(bad, "node")], []));
  assert.ok(issues.some((m) => m.includes('unknown category "missing_cat"')));
});

test("node properties are rejected", () => {
  const raw =
    '{"category":["item"],"id":"a","properties":{"x":1},"sources":[{"date":"2026-01-01","licence":"CC0-1.0","source":"ref-1"}]}';
  const issues = validateGraph({ nodesText: raw, edgesText: "", ...loadVocab() });
  assert.ok(issues.some((m) => m.includes("properties are not supported")));
});

test("category cycle fails", () => {
  const issues = validateCategoryVocabulary({ a: ["b"], b: ["a"] });
  assert.ok(issues.some((m) => m.includes("cycle")));
});

test("missing node source fails", () => {
  const bad = parseNode(node("a", { sources: [] }));
  const issues = validateGraph(asGraph([canonicalLine(bad, "node")], []));
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
  const issues = validateGraph({
    nodesText: [node("b"), node("a")].join("\n"),
    edgesText: "",
    ...vocab,
  });
  assert.ok(issues.some((m) => m.includes("not sorted")));
});

test("non-canonical key order fails", () => {
  const vocab = loadVocab();
  const raw =
    '{"id":"a","category":["item"],"sources":[{"date":"2026-01-01","licence":"CC0-1.0","source":"ref-1"}]}';
  const issues = validateGraph({ nodesText: raw, edgesText: "", ...vocab });
  assert.ok(issues.some((m) => m.includes("not canonical")));
});

test("duplicate categories fail canonical check", () => {
  const vocab = loadVocab();
  const raw =
    '{"category":["item","item"],"id":"a","sources":[{"date":"2026-01-01","licence":"CC0-1.0","source":"ref-1"}]}';
  const issues = validateGraph({ nodesText: raw, edgesText: "", ...vocab });
  assert.ok(issues.some((m) => m.includes("sorted unique")));
});

test("merge unions shared node and is byte-identical both orders", () => {
  const left = {
    nodes: [parseNode(node("shared", { category: ["item"], sources: SRC1 }))],
    edges: [],
  };
  const right = {
    nodes: [parseNode(node("shared", { category: ["entity"], sources: SRC2 }))],
    edges: [],
  };
  const ab = graphBytes(mergeGraphs(left, right));
  const ba = graphBytes(mergeGraphs(right, left));
  assert.equal(ab, ba);
  assert.ok(ab.includes("ref-1") && ab.includes("ref-2"));
  assert.ok(ab.includes('"entity"') && ab.includes('"item"'));
});

test("literal non-integer number is rejected", () => {
  const issues = validateGraph(asGraph([node("a")], [edge("a", "price", lit(10.5))]));
  assert.ok(issues.some((m) => m.includes("safe integers")));
});

test("literal float form 10.0 in raw line is non-canonical", () => {
  const vocab = loadVocab();
  const raw =
    '{"object":{"value":10.0},"predicate":"price","qualifiers":{},"sources":[{"date":"2026-01-01","licence":"CC0-1.0","source":"ref-1"}],"subject":"a"}';
  const issues = validateGraph({ nodesText: node("a"), edgesText: raw, ...vocab });
  assert.ok(issues.some((m) => m.includes("not canonical")));
});

test("literal decimal as string is accepted", () => {
  const issues = validateGraph(asGraph([node("a")], [edge("a", "price", lit("10.5"))]));
  assert.deepEqual(issues, []);
});

test("conflicting attribute values merge as two literal edges with identical bytes", () => {
  const x = parseNode(node("x"));
  const left = {
    nodes: [x],
    edges: [JSON.parse(edge("x", "price", lit(10)))],
  };
  const right = {
    nodes: [x],
    edges: [JSON.parse(edge("x", "price", lit(12), { sources: SRC2 }))],
  };
  const ab = graphBytes(mergeGraphs(left, right));
  const ba = graphBytes(mergeGraphs(right, left));
  assert.equal(ab, ba);
  assert.ok(ab.includes('"value":10') && ab.includes('"value":12'));
});

test("merge is commutative, associative, and idempotent on non-identical graphs", () => {
  const g1 = {
    nodes: [parseNode(node("a")), parseNode(node("b", { sources: SRC1 }))],
    edges: [JSON.parse(edge("a", "links_to", "b"))],
  };
  const g2 = {
    nodes: [parseNode(node("b", { category: ["entity", "item"], sources: SRC2 })), parseNode(node("c"))],
    edges: [JSON.parse(edge("b", "links_to", "c")), JSON.parse(edge("c", "price", lit(3)))],
  };
  const g3 = { nodes: [parseNode(node("d", { sources: SRC2 }))], edges: [] };

  const ab = mergeGraphs(g1, g2);
  const ba = mergeGraphs(g2, g1);
  assert.equal(graphBytes(ab), graphBytes(ba));

  const ab_c = mergeGraphs(ab, g3);
  const a_bc = mergeGraphs(g1, mergeGraphs(g2, g3));
  assert.equal(graphBytes(ab_c), graphBytes(a_bc));

  const once = mergeGraphs(g1, g2);
  const idempotent = mergeGraphs(g1, once);
  assert.equal(graphBytes(once), graphBytes(idempotent));
});
