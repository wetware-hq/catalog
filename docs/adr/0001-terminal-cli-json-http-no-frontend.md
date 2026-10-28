# Terminal CLI plus JSON HTTP discovery (no frontend)

## Status

Accepted

## Context

The catalog routes synthetic patient context to ranked A2A [1] peptide specialist agents. Human operators and autonomous agents both need access, but a browser UI would add maintenance, accessibility, and security surface without improving machine-to-machine discovery. The owner constraint is terminal-native operation for humans and JSON primitives for agents.

## Decision

- Ship a **CLI** (`src/bin/catalog.ts`) with `rank`, `list`, `show`, `validate`, and `serve` as the primary human interface.
- Implement **HTTP** in `src/server/app.ts` using Hono [2]: JSON responses only, `Accept: application/json` negotiation (406 otherwise), ETag/Cache-Control/Link headers [5], no HTML routes.
- Expose **A2A** discovery via `/.well-known/agent-card.json` and JSON-RPC [4] `POST /a2a/v1` for `catalog/list` and `catalog/rank`.

## Consequences

- Positive: Single codebase serves CLI and HTTP; agents consume the same rank logic as the CLI.
- Positive: OpenAPI [3] (`openapi/catalog.openapi.yaml`) can describe the HTTP surface without UI drift.
- Negative: No visual ranking dashboard; operators use terminal output or their own clients.
- Verification: `tests/http-x402.test.ts`, `tests/rank.test.ts`, REQ-CLI-001 and REQ-NO-UI-001 in `docs/requirements.yaml`.

## References

1. Agent2Agent (A2A) Protocol. https://github.com/a2aproject/A2A/blob/main/docs/specification.md
2. Hono web framework. https://hono.dev/
3. OpenAPI Specification v3.1.0. https://spec.openapis.org/oas/v3.1.0/draft
4. JSON-RPC 2.0 Specification. https://www.jsonrpc.org/specification
5. RFC 9110 — HTTP Semantics; RFC 8288 — Web Linking. https://www.rfc-editor.org/rfc/rfc9110
