# KGX Biolink graph (derived superstructure)

## Status

Accepted

## Context

Agents and evidence citations benefit from a portable graph interchange format without adding HTTP surface area or runtime dependencies.

## Decision

- **Source of truth** remains `registry/domains/*/*.json` (agents, routing, skillEvidence) and `data/evidence/peptide-claims.compact.json` (claims). The graph is a **derived**, byte-deterministic KGX JSONL export — not authoritative for editing agents.
- Pure `buildGraph(registry, evidence)` emits `graph/nodes.jsonl` and `graph/edges.jsonl` with Biolink categories, CURIE ids (PMID, DOI, NCT, CHEBI when present; else `catalog:`), and fail-closed edge validation (sources, publications, endpoint nodes).
- `mergeGraphs` is a set-theoretic join-semilattice on node id / edge key; property-tested.
- `npm run check` verifies graph repopulability; catalog AgentCard skill `catalog-kgx` references graph artifacts (no new HTTP route).

## Consequences

- Positive: Graph consumers can load KGX without custom parsers; registry CLI and rank path unchanged.
- Negative: Large committed JSONL (~2.5k claim nodes); regen required when registry or corpus changes.
- Verification: `tests/graph-merge.test.ts`, `npm run check`.

## References

1. Biolink Model. https://biolink.github.io/biolink-model/
2. KGX specification. https://github.com/NCATSTranslator/KGX
