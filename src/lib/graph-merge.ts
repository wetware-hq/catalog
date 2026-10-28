import type { Graph, GraphEdge, GraphNode } from "./graph-types.js";
import { validateGraph } from "./graph-build.js";

function edgeKey(e: GraphEdge): string {
  return [e.subject, e.predicate, e.object, e.primary_knowledge_source].join("\t");
}

function mergeNode(a: GraphNode, b: GraphNode): GraphNode {
  if (a.id !== b.id) throw new Error("mergeNode id mismatch");
  const out: GraphNode = { id: a.id, category: a.category };
  for (const key of new Set([...Object.keys(a), ...Object.keys(b)])) {
    if (key === "id") continue;
    if (key === "category") {
      out.category = a.category;
      continue;
    }
    out[key] = mergeAttr(a[key], b[key]);
  }
  return out;
}

function mergeAttr(a: unknown, b: unknown): unknown {
  const toSet = (x: unknown): string[] => {
    if (x == null) return [];
    if (Array.isArray(x)) return x.map(String);
    return [String(x)];
  };
  return [...new Set([...toSet(a), ...toSet(b)])].sort();
}

function mergePublications(a: string[], b: string[]): string[] {
  return [...new Set([...a, ...b])].sort();
}

function mergeEdge(a: GraphEdge, b: GraphEdge): GraphEdge {
  return {
    subject: a.subject,
    predicate: a.predicate,
    object: a.object,
    primary_knowledge_source: a.primary_knowledge_source,
    publications: mergePublications(a.publications, b.publications),
  };
}

/** Commutative, associative, idempotent union keyed by node id / edge key. */
export function mergeGraphs(a: Graph, b: Graph): Graph {
  const nodeMap = new Map<string, GraphNode>();
  for (const n of [...a.nodes, ...b.nodes]) {
    const prev = nodeMap.get(n.id);
    nodeMap.set(n.id, prev ? mergeNode(prev, n) : { ...n });
  }
  const edgeMap = new Map<string, GraphEdge>();
  for (const e of [...a.edges, ...b.edges]) {
    const k = edgeKey(e);
    const prev = edgeMap.get(k);
    edgeMap.set(k, prev ? mergeEdge(prev, e) : { ...e, publications: [...e.publications].sort() });
  }
  const graph: Graph = {
    nodes: [...nodeMap.values()].sort((x, y) => x.id.localeCompare(y.id)),
    edges: [...edgeMap.values()].sort(
      (x, y) =>
        x.subject.localeCompare(y.subject) ||
        x.predicate.localeCompare(y.predicate) ||
        x.object.localeCompare(y.object) ||
        x.primary_knowledge_source.localeCompare(y.primary_knowledge_source),
    ),
  };
  validateGraph(graph);
  return graph;
}
