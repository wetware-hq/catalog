import { writeFileSync, unlinkSync } from "node:fs";
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
  STATUS_ORDER,
  GRADE_ORDER,
} from "../src/check.js";

const root = join(dirname(fileURLToPath(import.meta.url)), "..");
const graphFile = join(root, "graph/graph.json");
const checkScript = join(root, "src/check.js");

const B1 = "chembl:CHEMBL123";
const B2 = "seq:ACDEF";
const T1 = "uniprot:P04637";
const T2 = "uniprot:Q9Y6K9";
const C1 = "pmid:12345";
const C2 = "pmid:67890";
const C3 = "doi:10.1000/example";

function graph(partial) {
  return { pair: {}, status: {}, ref: {}, ...partial };
}

function graphBytes(g) {
  return canonicalText(g);
}

function validPair(binder, target, citations) {
  const ref = {};
  for (const c of citations) ref[c] = "claim";
  return graph({
    status: { [binder]: "approved" },
    ref,
    pair: { [binder]: { [target]: citations } },
  });
}

test("empty graph file passes", () => {
  assert.deepEqual(validateGraphFile(graphFile), []);
});

test("CLI validates graph file", () => {
  const ok = spawnSync(process.execPath, [checkScript, graphFile], { encoding: "utf8" });
  assert.equal(ok.status, 0, ok.stderr);
});

test("empty citation list is rejected", () => {
  const g = graph({
    status: { [B1]: "approved" },
    ref: { [C1]: "claim" },
    pair: { [B1]: { [T1]: [] } },
  });
  assert.ok(validateGraph(g).some((m) => m.includes("at least one citation required")));
});

test("target-prefixed key as binder is rejected", () => {
  const g = graph({
    status: { [B1]: "approved" },
    ref: { [C1]: "claim" },
    pair: { [T1]: { [T2]: [C1] } },
  });
  const issues = validateGraph(g);
  assert.ok(issues.some((m) => m.includes("target key cannot be a binder")));
});

test("non-canonical key order in file is rejected", () => {
  const path = join(root, "graph/.tmp-order.json");
  writeFileSync(path, '{"ref":{},"status":{},"pair":{}}');
  const issues = validateGraphFile(path);
  unlinkSync(path);
  assert.ok(issues.some((m) => m.includes("not canonical")));
});

test("merge picks weaker status and grade on conflict", () => {
  const left = validPair(B1, T1, [C1]);
  left.status[B1] = STATUS_ORDER[0];
  left.ref[C1] = GRADE_ORDER[0];
  const right = validPair(B1, T1, [C2]);
  right.status[B1] = STATUS_ORDER[2];
  right.ref[C1] = GRADE_ORDER[4];
  right.ref[C2] = GRADE_ORDER[3];
  const merged = mergeGraphs(left, right);
  assert.equal(merged.status[B1], STATUS_ORDER[2]);
  assert.equal(merged.ref[C1], GRADE_ORDER[4]);
  assert.equal(graphBytes(mergeGraphs(left, right)), graphBytes(mergeGraphs(right, left)));
});

test("merge is commutative, associative, and idempotent on non-identical graphs", () => {
  const g1 = validPair(B1, T1, [C1]);
  const g2 = validPair(B2, T2, [C2]);
  g2.ref[C2] = "rct";
  const g3 = validPair(B1, T2, [C3]);
  g3.ref[C3] = "cohort";

  const ab = mergeGraphs(g1, g2);
  const ba = mergeGraphs(g2, g1);
  assert.equal(graphBytes(ab), graphBytes(ba));

  assert.equal(graphBytes(mergeGraphs(ab, g3)), graphBytes(mergeGraphs(g1, mergeGraphs(g2, g3))));

  const once = mergeGraphs(g1, g2);
  assert.equal(graphBytes(once), graphBytes(mergeGraphs(g1, once)));
});
