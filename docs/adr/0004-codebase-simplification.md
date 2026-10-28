# Codebase simplification (modules, scripts, tooling)

## Status

Accepted

## Context

The catalog had grown separate validate scripts, Redocly/CycloneDX tooling, and many small library files. Owner requirements are unchanged: CLI + HTTP (see ADR 0005 for node:http and deferred payments), evidence integrity, JSON Schemas, OpenAPI, requirements traceability, ADRs, and citation sections.

## Decision

- Merge `paths`, `evidence`, and `validate` into `corpus.ts` and `registry.ts`; merge CLI formatters into `catalog.ts`; inline HTTP cache helpers in `app.ts`.
- Remove unused `zod` dependency and heavy dev tools (Redocly CLI, CycloneDX npm plugin, YAML parser for requirements).
- Replace many npm scripts with **`npm run check`** (`scripts/build-evidence.ts --check` for SHA-256 + REFERENCES sync) plus **`npm test`** (includes OpenAPI route parity).
- Keep `docs/requirements.yaml` as a short requirement→test map without a custom parser.
- Do not commit SBOM artifacts; supply-chain listing is out of scope until a lightweight approach is chosen.
- Move architecture diagram to `docs/architecture.mermaid`; `architecture.md` links to it.

## Consequences

- Positive: Smaller lockfile, fewer files, every check traces to a test or `npm run check`.
- Positive: HTTP contract lives in JSON Schemas; `tests/http.test.ts` covers the three routes.
- Negative: OpenAPI lint is no longer Redocly-validated; structural checks are route-level only.
- Verification: `npm run check`, `npm test`, REQ-* rows in `docs/requirements.yaml`.

## References

1. Prior ADRs 0001–0003 in `docs/adr/`.
2. Owner simplification review (2026-10-28).
