# Biomedical Agent Catalog

A2A ([Agent2Agent][1]) catalog that ranks peptide specialist agents from **synthetic** patient context. Terminal-native CLI for humans; a **three-route** JSON HTTP API for agents. **Decision support only — not a prescriber.**

Open-source A2A catalog for routing synthetic patient context to specialist agents. Domain `peptides` is seeded; schema supports future domains (e.g. infectious disease, psychiatry) without restructuring.

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│  catalog CLI (primary)     catalog serve (HTTP, no UI)      │
│  rank | list | show | validate                              │
└───────────────┬─────────────────────────────┬───────────────┘
                │                             │
                ▼                             ▼
         rankAgents()                  node:http (3 routes)
                │                     rank + agent-card + health
                ▼
    registry/domains/{domainId}/*.json  +  data/evidence/peptide-claims.compact.json
                │
                ▼
    Rule-based matcher → relevanceScore + matchedSkills + clinical rationale
```

| Layer | Role |
|-------|------|
| **A2A AgentCard** | Each registered agent exposes standard v1 fields (`name`, `description`, `version`, `supportedInterfaces`, `capabilities`, I/O modes, `skills`). Placeholder `NOT_DEPLOYED` URLs mark agents not yet live. |
| **Catalog AgentCard** | Served at `GET /.well-known/agent-card.json` when `catalog serve` is running. |
| **Registry entry** | `registryId`, `domainId`, `agentCard`, plus catalog-only `routing` and `skillEvidence` (claim_id refs). JSON Schema [4]: `schemas/catalog-registry-entry.schema.json`. |
| **Evidence** | Multi-model–verified peptide claims, reduced to ~1.4 MB `data/evidence/peptide-claims.compact.json` with `verification_status` preserved. See `data/evidence/PROVENANCE.md` and generated `data/evidence/REFERENCES.md`. |
| **Patient input** | `catalog.simple.v1` JSON or FHIR R4 [3] `Bundle` (Patient + Condition / Goal / Observation / MedicationStatement / AllergyIntolerance). |
| **HTTP contract** | Rank I/O: `schemas/rank-request.schema.json`, `schemas/rank-response.schema.json` (validated in `src/server.ts`). |

## Quick start

```bash
npm ci
npm run build          # regenerates evidence if uploads present; uses committed corpus otherwise
npm run catalog -- validate
npm run catalog -- list --domain peptides
```

## CLI (primary interface)

```bash
# List peptide agents
npm run catalog -- list --domain peptides

# Show one registry entry (A2A card + routing metadata)
npm run catalog -- show peptide-regulatory-au

# Rank agents for a synthetic patient (human-readable)
npm run catalog -- rank --patient fixtures/patients/synthetic-athlete-tendon-simple.json

# Machine-readable
npm run catalog -- rank --patient fixtures/patients/synthetic-t2dm-weight-simple.json --json

# Validate registry + evidence references
npm run catalog -- validate

# Start HTTP server (127.0.0.1 by default; no HTML UI)
npm run catalog -- serve --port 8787
```

After `npm run build`, the `catalog` binary is also available as `./dist/bin/catalog.js`.

### Demo: rank output (athlete + tendon fixture)

```bash
npm run catalog -- rank --patient fixtures/patients/synthetic-athlete-tendon-simple.json
```

Example (truncated):

```
Clinical decision support only — not prescribing advice. ...

Patient: Synthetic Athlete (tendon injury) (syn-athlete-001)
Inferred peptide themes: bpc-157, tb-500

Ranked agents:
1. peptide-clinical-advisor  score=0.87
   ... Top skill "holistic-peptide-recommendation" ...
   regulatory:
     ! Patient flagged as seeking compounded peptides — verify TGA [5] ...
     ! [bpc-157] Verified claim 4d0b84024d846a41: no TGA ARTG [5] entry located (confirmed_2of2).

2. peptide-regulatory-au  score=0.78
   ... Top skill "wada-prohibited-list" (WADA Prohibited List [6]) ...
```

Fixtures (all synthetic):

- `fixtures/patients/synthetic-athlete-tendon-simple.json`
- `fixtures/patients/synthetic-t2dm-weight-simple.json`
- `fixtures/patients/synthetic-fertility-fhir.json` (FHIR Bundle)

## HTTP API (3 routes)

All responses are `Content-Type: application/json`. Default listen: `127.0.0.1:8787` (`CATALOG_HOST`, `CATALOG_PORT`, optional `CATALOG_PUBLIC_BASE_URL` for AgentCard URLs).

| Method | Path | Body / response |
|--------|------|-----------------|
| `POST` | `/catalog/v1/rank` | Request → `schemas/rank-request.schema.json`; response → `schemas/rank-response.schema.json` |
| `GET` | `/.well-known/agent-card.json` | Catalog A2A AgentCard |
| `GET` | `/health` | `{"ok":true}` |

Errors: **400** invalid JSON or schema, **404** unknown path, **405** wrong method, **413** body &gt; 64 KiB, **500** generic JSON `{ "error": "…" }` (no stack traces). Use CLI `list` / `show` for registry browsing.

## Adding a domain or agent

1. Create `registry/domains/<domainId>/<registryId>.json` matching `schemas/catalog-registry-entry.schema.json`.
2. Use a valid A2A AgentCard (required fields only from the spec; do not invent core fields).
3. Attach `skillEvidence` with `claim_id` values from `data/evidence/peptide-claims.compact.json` (or future domain corpora).
4. Extend `GOAL_PEPTIDE_MAP` / routing tags in `src/lib/rank.ts` as clinical matching rules evolve.
5. Run `npm run catalog -- validate`.

## Evidence regeneration

Raw verification uploads are not committed. To rebuild from uploads:

```bash
CLAIM_UPLOADS_DIR=/path/to/uploads npm run build:evidence
```

## CI checks

```bash
npm run check    # evidence SHA-256 sidecar + REFERENCES.md in sync
npm test         # registry, rank, HTTP, evidence integrity
```

## Tests

```bash
npm test
```

## License

MIT — see [LICENSE](LICENSE).

## References

1. Agent2Agent (A2A) Protocol. https://github.com/a2aproject/A2A/blob/main/docs/specification.md
2. HL7 FHIR R4. https://hl7.org/fhir/R4/
3. JSON Schema (draft 2020-12). https://json-schema.org/draft/2020-12/json-schema-core
4. Therapeutic Goods Administration (TGA) — Australian Register of Therapeutic Goods (ARTG). https://www.tga.gov.au/resources/artg
5. World Anti-Doping Agency (WADA) Prohibited List. https://www.wada-ama.org/en/resources/world-anti-doping-code-and-international-standards/prohibited-list
6. Node.js HTTP module. https://nodejs.org/api/http.html
7. Markdown Any Decision Records (MADR). https://adr.github.io/madr/
