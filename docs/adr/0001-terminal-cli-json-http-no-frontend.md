# Terminal CLI + minimal JSON HTTP (no frontend)

## Status

Accepted (HTTP scope narrowed by ADR 0005)

## Context

The catalog must stay terminal-native for operators while exposing a small machine interface for agents. No HTML UI.

## Decision

- Primary interface: **`catalog` CLI** (`src/bin/catalog.ts`) — rank, list, show, validate, serve.
- HTTP: **`src/server.ts`** with Node `node:http` — three JSON routes only (see ADR 0005); rank request/response validated against JSON Schemas in `schemas/`.
- Registry and rank I/O validated in CLI via `validateCatalog()` and shared rank logic in `src/lib/rank.ts`.

## Consequences

- Positive: Clear split — CLI for browsing, HTTP for rank + AgentCard discovery.
- Negative: No HTTP catalog index or JSON-RPC shim.
- Verification: `tests/http.test.ts`, `tests/rank.test.ts`, REQ-* in `docs/requirements.yaml`.

## References

1. Agent2Agent (A2A) Protocol. https://github.com/a2aproject/A2A/blob/main/docs/specification.md
2. Node.js HTTP module. https://nodejs.org/api/http.html
3. JSON Schema draft 2020-12. https://json-schema.org/draft/2020-12/json-schema-core
4. RFC 9110 — HTTP Semantics. https://www.rfc-editor.org/rfc/rfc9110
