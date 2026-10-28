import type { CatalogRegistryEntry, CompactClaim, EvidenceCorpus } from "../types/catalog.js";

export type GraphNode = {
  id: string;
  category: string;
  name?: string;
  /** Scalar or multiset attribute values after merge. */
  [key: string]: unknown;
};

export type GraphEdge = {
  subject: string;
  predicate: string;
  object: string;
  primary_knowledge_source: string;
  publications: string[];
};

export type Graph = {
  nodes: GraphNode[];
  edges: GraphEdge[];
};

export type GraphBuildInput = {
  registry: CatalogRegistryEntry[];
  evidence: EvidenceCorpus;
};

export type { CatalogRegistryEntry, CompactClaim, EvidenceCorpus };
