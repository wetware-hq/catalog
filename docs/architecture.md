# Architecture

Decision-support catalog: terminal CLI and a **three-route** JSON HTTP surface (`src/server.ts`, Node `node:http` only). Browsing uses CLI `list` / `show`.

System diagram: [architecture.mermaid](./architecture.mermaid)

## Module map

| Module | Requirement trace |
|--------|-------------------|
| `src/bin/catalog.ts` | REQ-CLI-001 |
| `src/server.ts` | REQ-HTTP-001, REQ-NO-UI-001, REQ-A2A-001, REQ-SCHEMA-001 |
| `src/lib/rank.ts` | REQ-CLI-001 |
| `src/lib/registry.ts` | REQ-SCHEMA-001, REQ-EVIDENCE-STATUS-001 |
| `src/lib/corpus.ts` | REQ-EVIDENCE-INTEGRITY-001 |
| `scripts/build-evidence.ts` | REQ-EVIDENCE-INTEGRITY-001 |
| `schemas/*.json` | REQ-SCHEMA-001, REQ-SE-001 |
| `docs/requirements.yaml` | REQ-SE-001 |
| `docs/adr/*` | REQ-SE-001 |

## References

1. Agent2Agent (A2A) Protocol. https://github.com/a2aproject/A2A/blob/main/docs/specification.md
2. Node.js HTTP module. https://nodejs.org/api/http.html
3. JSON Schema draft 2020-12. https://json-schema.org/draft/2020-12/json-schema-core
4. Mermaid diagram syntax. https://mermaid.js.org/
