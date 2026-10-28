# Architecture (C4-style context)

The catalog is a **decision-support router**: it does not prescribe treatments. It matches synthetic patient features to registered A2A agent cards and attached evidence claims.

## System context

```mermaid
flowchart LR
  subgraph humans [Human operators]
    CLI[catalog CLI]
  end
  subgraph agents [Software agents]
    A2A[A2A JSON-RPC clients]
    REST[HTTP JSON clients]
  end
  subgraph catalog [Catalog server process]
    SERVE[Hono HTTP server]
    RANK[rankAgents]
    REG[(registry JSON)]
    EV[(peptide-claims.compact.json)]
  end
  subgraph optional [Optional payment]
    X402[x402 facilitator mock or HTTP]
  end
  CLI --> RANK
  REST --> SERVE
  A2A --> SERVE
  SERVE --> RANK
  RANK --> REG
  RANK --> EV
  SERVE -.->|POST /catalog/v1/rank when enabled| X402
```

## Containers (repository modules)

| Container | Path | Responsibility |
|-----------|------|----------------|
| CLI | `src/bin/catalog.ts`, `src/cli/` | Terminal commands; calls rank/validate/registry libs |
| HTTP API | `src/server/app.ts` | JSON routes, x402 on rank, JSON-RPC shim |
| Ranker | `src/lib/rank.ts` | Rule-based scoring and clinical rationales |
| Registry loader | `src/lib/registry.ts` | Domain entries + catalog AgentCard |
| Evidence loader | `src/lib/evidence.ts` | Compact JSON corpus |
| Evidence build | `scripts/build-evidence.ts` | Uploads → compact JSON + SHA-256 sidecar |
| Schemas | `schemas/*.schema.json` | Registry and rank I/O contracts |
| OpenAPI | `openapi/catalog.openapi.yaml` | HTTP contract (linted in CI) |

## Key flows

### Rank (CLI or HTTP)

1. Normalize patient input (`catalog.simple.v1` or FHIR Bundle) via `src/lib/patient.ts`.
2. Load registry entries for `domainId`.
3. Score agents using goal/peptide maps and `skillEvidence` claim references.
4. Return ordered agents with disclaimer and regulatory alerts.

### Evidence integrity

1. `build-evidence.ts` writes `peptide-claims.compact.json`.
2. SHA-256 digest written to `peptide-claims.compact.sha256`.
3. CI runs `npm run verify:evidence` to match sidecar to file bytes.

## Related artifacts

- Requirements: `docs/requirements.yaml`
- ADRs: `docs/adr/`
- API: `openapi/catalog.openapi.yaml`
- SBOM: `sbom.cdx.json`
