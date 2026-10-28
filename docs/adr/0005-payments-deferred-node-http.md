# Payments deferred; primitive three-route HTTP

## Status

Accepted

## Context

ADR 0002 added optional x402 on rank; the owner **deferred payments** and asked for a **bare-metal** HTTP layer with no framework, no OpenAPI file, and no discovery routes beyond AgentCard + rank + health.

## Decision

- Remove x402 code, configuration, and ADR 0002 (marked superseded).
- Serve **exactly three** routes via `src/server.ts` and `node:http` only:
  - `POST /catalog/v1/rank` — validate `schemas/rank-request.schema.json`, respond per `schemas/rank-response.schema.json` (Ajv).
  - `GET /.well-known/agent-card.json` — catalog AgentCard JSON.
  - `GET /health` — `{"ok":true}`.
- No Accept negotiation, ETags, CORS, or extra discovery/JSON-RPC HTTP paths (CLI `list` / `show` cover browsing).
- Errors: **400** bad JSON/schema, **404** unknown path, **405** wrong method, **413** over **64 KiB** body, **500** generic (no stack traces). Default bind **127.0.0.1**; port from `CATALOG_PORT`.
- Drop `openapi/catalog.openapi.yaml`; **JSON Schemas** under `schemas/` are the HTTP contract.

## Consequences

- Positive: Zero HTTP npm dependencies; smallest server surface.
- Negative: Agents must use CLI or embed rank logic for registry browsing over HTTP.
- Verification: `tests/http.test.ts`, `npm run build`, `npm run check`, `npm test`.

## References

1. Supersedes `docs/adr/0002-x402-rank-payment-gating.md`.
2. Node.js HTTP API. https://nodejs.org/api/http.html
3. JSON Schema draft 2020-12. https://json-schema.org/draft/2020-12/json-schema-core
