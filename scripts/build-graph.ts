/**
 * KGX Biolink JSONL graph from registry + evidence corpus.
 * Run: npm run build:graph  |  npm run check (includes --check)
 */
import { readFileSync, writeFileSync, existsSync, mkdirSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath, pathToFileURL } from "node:url";
import { buildGraph, validateGraph } from "../src/lib/graph-build.js";
import { graphToJsonl } from "../src/lib/graph-serialize.js";
import type { Graph } from "../src/lib/graph-types.js";
import { loadEvidenceCorpus } from "../src/lib/corpus.js";
import { loadRegistryEntries } from "../src/lib/registry.js";

const ROOT = join(dirname(fileURLToPath(import.meta.url)), "..");

export function buildGraphArtifacts(root: string = ROOT): Graph {
  const registry = loadRegistryEntries();
  const evidence = loadEvidenceCorpus();
  const graph = buildGraph(registry, evidence);
  validateGraph(graph);
  return graph;
}

export function writeGraphArtifacts(root: string = ROOT): void {
  const graph = buildGraphArtifacts(root);
  const { nodes, edges } = graphToJsonl(graph);
  const dir = join(root, "graph");
  mkdirSync(dir, { recursive: true });
  writeFileSync(join(dir, "nodes.jsonl"), nodes);
  writeFileSync(join(dir, "edges.jsonl"), edges);
}

export function checkGraphArtifacts(root: string = ROOT): void {
  const nodesPath = join(root, "graph", "nodes.jsonl");
  const edgesPath = join(root, "graph", "edges.jsonl");
  if (!existsSync(nodesPath) || !existsSync(edgesPath)) {
    throw new Error("missing graph/nodes.jsonl or graph/edges.jsonl — run npm run build:graph");
  }
  const expected = graphToJsonl(buildGraphArtifacts(root));
  const nodesOnDisk = readFileSync(nodesPath, "utf8");
  const edgesOnDisk = readFileSync(edgesPath, "utf8");
  if (nodesOnDisk !== expected.nodes) {
    throw new Error("graph/nodes.jsonl out of sync — run npm run build:graph");
  }
  if (edgesOnDisk !== expected.edges) {
    throw new Error("graph/edges.jsonl out of sync — run npm run build:graph");
  }
}

const isMain =
  process.argv[1] !== undefined &&
  import.meta.url === pathToFileURL(process.argv[1]).href;

if (isMain) {
  if (process.argv.includes("--check")) {
    checkGraphArtifacts(ROOT);
    console.log("graph artifacts OK");
  } else {
    writeGraphArtifacts(ROOT);
    console.log("Wrote graph/nodes.jsonl and graph/edges.jsonl");
  }
}
