# Architecture

Decision-support catalog: terminal CLI and JSON HTTP (no UI) rank synthetic patient context against registered A2A peptide agents and attached evidence claims.

System diagram (Mermaid): [architecture.mermaid](./architecture.mermaid)

## Module map

| Module | Requirement trace |
|--------|-------------------|
| `src/bin/catalog.ts` | REQ-CLI-001 |
| `src/server/app.ts` | REQ-HTTP-001, REQ-A2A-001, REQ-X402-001 |
| `src/lib/rank.ts` | REQ-CLI-001 |
| `src/lib/registry.ts` | REQ-SCHEMA-001, REQ-EVIDENCE-STATUS-001 |
| `src/lib/corpus.ts` | REQ-EVIDENCE-INTEGRITY-001 |
| `scripts/build-evidence.ts` | REQ-EVIDENCE-INTEGRITY-001 |
| `openapi/catalog.openapi.yaml` | REQ-SE-001, REQ-NO-UI-001 |
| `docs/requirements.yaml` | REQ-SE-001 |
| `docs/adr/*` | REQ-SE-001 |

## References

1. Agent2Agent (A2A) Protocol. https://github.com/a2aproject/A2A/blob/main/docs/specification.md
2. x402 v1 HTTP transport. https://github.com/coinbase/x402/blob/main/specs/transports-v1/http.md
3. OpenAPI Specification v3.1.0. https://spec.openapis.org/oas/v3.1.0/draft
4. Mermaid diagram syntax. https://mermaid.js.org/
