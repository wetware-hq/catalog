import type { Graph, GraphEdge, GraphNode } from "./graph-types.js";
import { sortValue } from "./stable-json.js";

export function graphToJsonl(graph: Graph): { nodes: string; edges: string } {
  const nodeLines = graph.nodes.map((n) => JSON.stringify(sortValue(n)));
  const edgeLines = graph.edges.map((e) => JSON.stringify(sortValue(e)));
  return {
    nodes: `${nodeLines.join("\n")}\n`,
    edges: `${edgeLines.join("\n")}\n`,
  };
}

export function parseGraphJsonl(nodesBody: string, edgesBody: string): Graph {
  const parseLines = <T>(body: string): T[] =>
    body
      .split("\n")
      .map((l) => l.trim())
      .filter(Boolean)
      .map((l) => JSON.parse(l) as T);
  return {
    nodes: parseLines<GraphNode>(nodesBody),
    edges: parseLines<GraphEdge>(edgesBody),
  };
}
