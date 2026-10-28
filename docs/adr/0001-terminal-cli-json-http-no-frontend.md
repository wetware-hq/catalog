# Terminal CLI plus JSON HTTP discovery (no frontend)

## Status

Accepted

## Context

The catalog routes synthetic patient context to ranked A2A peptide specialist agents. Human operators and autonomous agents both need access, but a browser UI would add maintenance, accessibility, and security surface without improving machine-to-machine discovery. The owner constraint is terminal-native operation for humans and JSON primitives for agents.

## Decision

- Ship a **CLI** (`src/bin/catalog.ts`) with `rank`, `list`, `show`, `validate`, and `serve` as the primary human interface.
- Implement **HTTP** in `src/server/app.ts` using Hono: JSON responses only, `Accept: application/json` negotiation (406 otherwise), ETag/Cache-Control/Link headers, no HTML routes.
- Expose **A2A** discovery via `/.well-known/agent-card.json` and JSON-RPC `POST /a2a/v1` for `catalog/list` and `catalog/rank`.

## Consequences

- Positive: Single codebase serves CLI and HTTP; agents consume the same rank logic as the CLI.
- Positive: OpenAPI (`openapi/catalog.openapi.yaml`) can describe the HTTP surface without UI drift.
- Negative: No visual ranking dashboard; operators use terminal output or their own clients.
- Verification: `tests/http-x402.test.ts`, `tests/rank.test.ts`, REQ-CLI-001 and REQ-NO-UI-001 in `docs/requirements.yaml`.
