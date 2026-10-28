import { describe, expect, it } from "vitest";
import type { Graph } from "../src/lib/graph-types.js";
import { validateGraph, GraphValidationError } from "../src/lib/graph-build.js";
import { mergeGraphs } from "../src/lib/graph-merge.js";
import { graphToJsonl } from "../src/lib/graph-serialize.js";

function ser(graph: Graph): string {
  const { nodes, edges } = graphToJsonl(graph);
  return nodes + edges;
}

function g(nodes: Graph["nodes"], edges: Graph["edges"]): Graph {
  return { nodes, edges };
}

const baseA = g(
  [
    { id: "catalog:agent:a", category: "biolink:Software", name: "A" },
    { id: "catalog:claim:1", category: "biolink:Statement", name: "c1" },
  ],
  [
    {
      subject: "catalog:agent:a",
      predicate: "biolink:mentions",
      object: "catalog:claim:1",
      primary_knowledge_source: "catalog:authority:pubmed",
      publications: ["PMID:1"],
    },
  ],
);

const baseB = g(
  [
    { id: "catalog:agent:a", category: "biolink:Software", name: "A-alt" },
    { id: "catalog:claim:1", category: "biolink:Statement", name: "c1" },
  ],
  [
    {
      subject: "catalog:agent:a",
      predicate: "biolink:mentions",
      object: "catalog:claim:1",
      primary_knowledge_source: "catalog:authority:pubmed",
      publications: ["PMID:2"],
    },
  ],
);

describe("mergeGraphs", () => {
  it("is commutative (up to stable serialization)", () => {
    const ab = mergeGraphs(baseA, baseB);
    const ba = mergeGraphs(baseB, baseA);
    expect(ser(ab)).toBe(ser(ba));
  });

  it("is associative", () => {
    const c = g([{ id: "catalog:claim:2", category: "biolink:Statement" }], []);
    const left = mergeGraphs(mergeGraphs(baseA, baseB), c);
    const right = mergeGraphs(baseA, mergeGraphs(baseB, c));
    expect(ser(left)).toBe(ser(right));
  });

  it("is idempotent", () => {
    const once = mergeGraphs(baseA, baseB);
    const twice = mergeGraphs(once, baseB);
    expect(ser(twice)).toBe(ser(once));
  });

  it("fail-closed: validateGraph rejects dangling edge endpoints", () => {
    const bad = g(
      [{ id: "catalog:agent:a", category: "biolink:Software" }],
      [
        {
          subject: "catalog:agent:a",
          predicate: "biolink:mentions",
          object: "catalog:claim:missing",
          primary_knowledge_source: "catalog:authority:x",
          publications: ["PMID:9"],
        },
      ],
    );
    expect(() => validateGraph(bad)).toThrow(GraphValidationError);
  });
});
