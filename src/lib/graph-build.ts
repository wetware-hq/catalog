import type { CatalogRegistryEntry, CompactClaim, EvidenceCorpus } from "../types/catalog.js";
import type { Graph, GraphEdge, GraphNode } from "./graph-types.js";

const AGENT = "biolink:Software";
const CLAIM = "biolink:Statement";
const PUBLICATION = "biolink:Publication";
const PROVENANCE = "biolink:InformationContentEntity";

export function agentNodeId(registryId: string): string {
  return `catalog:agent:${registryId}`;
}

export function claimNodeId(claimId: string): string {
  return `catalog:claim:${claimId}`;
}

function authoritySource(authority: string | null): string {
  const slug = (authority ?? "unknown")
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, "-")
    .replace(/^-|-$/g, "");
  return `catalog:authority:${slug || "unknown"}`;
}

export function publicationCuries(claim: CompactClaim): string[] {
  const pubs: string[] = [];
  const ids = claim.identifiers ?? {};
  if (ids.pmid != null && String(ids.pmid).trim()) pubs.push(`PMID:${String(ids.pmid).trim()}`);
  if (ids.doi != null && String(ids.doi).trim()) {
    pubs.push(`DOI:${String(ids.doi).trim().toLowerCase()}`);
  }
  if (ids.nct != null && String(ids.nct).trim()) {
    const nct = String(ids.nct).trim();
    pubs.push(nct.startsWith("NCT:") ? nct : `NCT:${nct}`);
  }
  if (ids.chebi != null && String(ids.chebi).trim()) {
    const c = String(ids.chebi).trim().replace(/^CHEBI:/i, "");
    pubs.push(`CHEBI:${c}`);
  }
  if (!pubs.length) pubs.push(`catalog:provenance:${claim.claim_id}`);
  return [...new Set(pubs)].sort();
}

function publicationNode(id: string, claim: CompactClaim): GraphNode {
  if (id.startsWith("catalog:provenance:")) {
    const url = claim.identifiers?.url;
    return {
      id,
      category: PROVENANCE,
      name: claim.authority ?? "provenance",
      ...(url ? { url: [String(url)] } : {}),
    };
  }
  if (id.startsWith("PMID:")) {
    const pmid = id.slice(5);
    return { id, category: PUBLICATION, name: `PubMed ${pmid}`, url: [`https://pubmed.ncbi.nlm.nih.gov/${pmid}/`] };
  }
  if (id.startsWith("DOI:")) {
    const doi = id.slice(4);
    return { id, category: PUBLICATION, name: `DOI ${doi}`, url: [`https://doi.org/${doi}`] };
  }
  if (id.startsWith("NCT:")) {
    const nct = id.slice(4);
    return { id, category: PUBLICATION, name: nct, url: [`https://clinicaltrials.gov/study/${nct}`] };
  }
  if (id.startsWith("CHEBI:")) {
    return { id, category: "biolink:ChemicalEntity", name: id };
  }
  return { id, category: PUBLICATION, name: id };
}

function upsertNode(map: Map<string, GraphNode>, node: GraphNode): void {
  const prev = map.get(node.id);
  if (!prev) {
    map.set(node.id, node);
    return;
  }
  for (const [k, v] of Object.entries(node)) {
    if (k === "id" || k === "category") continue;
    prev[k] = mergeAttr(prev[k], v);
  }
}

function mergeAttr(a: unknown, b: unknown): unknown {
  const toSet = (x: unknown): string[] => {
    if (x == null) return [];
    if (Array.isArray(x)) return x.map(String);
    return [String(x)];
  };
  return [...new Set([...toSet(a), ...toSet(b)])].sort();
}

/** Pure KGX graph from registry + evidence (no clock / I/O). */
export function buildGraph(registry: CatalogRegistryEntry[], evidence: EvidenceCorpus): Graph {
  const nodeMap = new Map<string, GraphNode>();
  const claimById = new Map(evidence.claims.map((c) => [c.claim_id, c]));
  const edges: GraphEdge[] = [];

  for (const entry of registry) {
    upsertNode(nodeMap, {
      id: agentNodeId(entry.registryId),
      category: AGENT,
      name: entry.agentCard.name,
      domain: [entry.domainId],
    });

    for (const [skillId, refs] of Object.entries(entry.skillEvidence ?? {})) {
      for (const ref of refs) {
        const claim = claimById.get(ref.claim_id);
        if (!claim) continue;
        upsertNode(nodeMap, {
          id: claimNodeId(claim.claim_id),
          category: CLAIM,
          name: claim.slug,
          verification_status: [claim.verification_status],
          verified: [String(claim.verified)],
        });
        const pubs = publicationCuries(claim);
        for (const pub of pubs) {
          upsertNode(nodeMap, publicationNode(pub, claim));
        }
        const source = authoritySource(claim.authority);
        upsertNode(nodeMap, {
          id: source,
          category: "biolink:InformationResource",
          name: claim.authority ?? "unknown",
        });
        edges.push({
          subject: agentNodeId(entry.registryId),
          predicate: "biolink:mentions",
          object: claimNodeId(claim.claim_id),
          primary_knowledge_source: source,
          publications: pubs,
        });
        for (const pub of pubs) {
          edges.push({
            subject: claimNodeId(claim.claim_id),
            predicate: "biolink:supporting_document",
            object: pub,
            primary_knowledge_source: source,
            publications: pubs,
          });
        }
      }
      void skillId;
    }
  }

  for (const claim of evidence.claims) {
    upsertNode(nodeMap, {
      id: claimNodeId(claim.claim_id),
      category: CLAIM,
      name: claim.slug,
      verification_status: [claim.verification_status],
      verified: [String(claim.verified)],
    });
  }

  const nodes = [...nodeMap.values()].sort((a, b) => a.id.localeCompare(b.id));
  edges.sort(
    (a, b) =>
      a.subject.localeCompare(b.subject) ||
      a.predicate.localeCompare(b.predicate) ||
      a.object.localeCompare(b.object) ||
      a.primary_knowledge_source.localeCompare(b.primary_knowledge_source),
  );
  return { nodes, edges };
}

export class GraphValidationError extends Error {
  constructor(message: string) {
    super(message);
    this.name = "GraphValidationError";
  }
}

/** Fail closed before emit or after merge. */
export function validateGraph(graph: Graph): void {
  const nodeIds = new Set(graph.nodes.map((n) => n.id));
  for (const edge of graph.edges) {
    if (!edge.primary_knowledge_source?.trim()) {
      throw new GraphValidationError("edge missing primary_knowledge_source");
    }
    if (!edge.publications?.length) {
      throw new GraphValidationError("edge missing publications");
    }
    if (!nodeIds.has(edge.subject)) {
      throw new GraphValidationError(`edge subject not a node: ${edge.subject}`);
    }
    if (!nodeIds.has(edge.object)) {
      throw new GraphValidationError(`edge object not a node: ${edge.object}`);
    }
  }
}
