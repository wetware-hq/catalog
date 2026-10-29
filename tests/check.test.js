import { readFileSync, writeFileSync, unlinkSync } from "node:fs";
import { join, dirname } from "node:path";
import { fileURLToPath } from "node:url";
import { spawnSync } from "node:child_process";
import test from "node:test";
import assert from "node:assert/strict";
import {
  validateGraph,
  validateGraphFile,
  mergeGraphs,
  canonicalText,
} from "../src/check.js";

const root = join(dirname(fileURLToPath(import.meta.url)), "..");
const graphFile = join(root, "graph/graph.json");
const checkScript = join(root, "src/check.js");

const B1 = "CHEMBL123";
const B2 = "seq:ACDEF";
const T1 = "P04637";
const T2 = "Q9Y6K9";

function cite(ref, level) {
  return { ref, level };
}

function graph(partial) {
  return {
    binders: {},
    targets: {},
    edges: {},
    ...partial,
  };
}

function graphBytes(g) {
  return canonicalText(g);
}

test("empty graph file passes", () => {
  assert.deepEqual(validateGraphFile(graphFile), []);
});

test("CLI validates graph file", () => {
  const ok = spawnSync(process.execPath, [checkScript, graphFile], { encoding: "utf8" });
  assert.equal(ok.status, 0, ok.stderr);
});

test("empty citation array is rejected", () => {
  const g = graph({
    binders: { [B1]: { status: "approved" } },
    targets: { [T1]: {} },
    edges: { [B1]: { [T1]: [] } },
  });
  const issues = validateGraph(g);
  assert.ok(issues.some((m) => m.includes("at least one citation required")));
});

test("edge endpoints must exist in binders and targets", () => {
  const g = graph({ edges: { [B1]: { [T1]: [cite("12345", "human")] } } });
  const issues = validateGraph(g);
  assert.ok(issues.some((m) => m.includes("missing from binders")));
  assert.ok(issues.some((m) => m.includes("missing from targets")));
});

test("non-canonical key order in file is rejected", () => {
  const path = join(root, "graph/.tmp-order.json");
  writeFileSync(path, '{"targets":{},"binders":{},"edges":{}}');
  const issues = validateGraphFile(path);
  unlinkSync(path);
  assert.ok(issues.some((m) => m.includes("not canonical")));
});

test("merge unions citations and is byte-identical both orders", () => {
  const left = graph({
    binders: { [B1]: { status: "approved" } },
    targets: { [T1]: {}, [T2]: {} },
    edges: {
      [B1]: {
        [T1]: [cite("12345", "human")],
        [T2]: [cite("10.1000/example", "in_vitro")],
      },
    },
  });
  const right = graph({
    binders: { [B1]: { status: "investigational" }, [B2]: { status: "unapproved" } },
    targets: { [T1]: {}, [T2]: {} },
    edges: {
      [B1]: { [T1]: [cite("67890", "animal")] },
      [B2]: { [T2]: [cite("11111", "claim")] },
    },
  });
  const ab = graphBytes(mergeGraphs(left, right));
  const ba = graphBytes(mergeGraphs(right, left));
  assert.equal(ab, ba);
  assert.ok(ab.includes("12345") && ab.includes("67890"));
});

test("merge is commutative, associative, and idempotent on non-identical graphs", () => {
  const g1 = graph({
    binders: { [B1]: { status: "approved" } },
    targets: { [T1]: {} },
    edges: { [B1]: { [T1]: [cite("12345", "human")] } },
  });
  const g2 = graph({
    binders: { [B2]: { status: "investigational" } },
    targets: { [T2]: {} },
    edges: { [B2]: { [T2]: [cite("22222", "claim")] } },
  });
  const g3 = graph({
    binders: { [B1]: { status: "approved" } },
    targets: { [T1]: {}, [T2]: {} },
    edges: { [B1]: { [T2]: [cite("33333", "in_vitro")] } },
  });

  const ab = mergeGraphs(g1, g2);
  const ba = mergeGraphs(g2, g1);
  assert.equal(graphBytes(ab), graphBytes(ba));

  assert.equal(graphBytes(mergeGraphs(ab, g3)), graphBytes(mergeGraphs(g1, mergeGraphs(g2, g3))));

  const once = mergeGraphs(g1, g2);
  assert.equal(graphBytes(once), graphBytes(mergeGraphs(g1, once)));
});
