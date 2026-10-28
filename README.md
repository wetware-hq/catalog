# Wetware Biomedical Agent Catalog

A2A ([Agent2Agent](https://github.com/a2aproject/A2A)) catalog that ranks peptide specialist agents from **synthetic** patient context. Terminal-native CLI for humans; HTTP + JSON-RPC for agents. **Decision support only — not a prescriber.**

Owner context: Wetware (Mathew Chu, PGY1 / physician-scientist). Domain `peptides` is seeded; schema supports future domains (e.g. infectious disease, psychiatry) without restructuring.

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│  catalog CLI (primary)     catalog serve (HTTP, no UI)      │
│  rank | list | show | validate                              │
└───────────────┬─────────────────────────────┬───────────────┘
                │                             │
                ▼                             ▼
         rankAgents()                  Hono HTTP + JSON-RPC
                │                     /.well-known/agent-card.json
                │                     /catalog/v1/*  /a2a/v1
                ▼
    registry/domains/{domainId}/*.json  +  data/evidence/peptide-claims.compact.json
                │
                ▼
    Rule-based matcher → relevanceScore + matchedSkills + clinical rationale
```

| Layer | Role |
|-------|------|
| **A2A AgentCard** | Each registered agent exposes standard v1 fields (`name`, `description`, `version`, `supportedInterfaces`, `capabilities`, I/O modes, `skills`). Placeholder `NOT_DEPLOYED` URLs mark agents not yet live. |
| **Catalog AgentCard** | This repo’s catalog is itself an A2A server (`/.well-known/agent-card.json`) with skills `catalog-rank` and `catalog-list`. |
| **Registry entry** | `registryId`, `domainId`, `agentCard`, plus catalog-only `routing` and `skillEvidence` (claim_id refs). JSON Schema: `schemas/catalog-registry-entry.schema.json`. |
| **Evidence** | Fleet v3 peptide claims, reduced to ~1.4 MB `data/evidence/peptide-claims.compact.json` with `verification_status` preserved. See `data/evidence/PROVENANCE.md`. |
| **Patient input** | `wetware.simple.v1` JSON or FHIR R4 `Bundle` (Patient + Condition / Goal / Observation / MedicationStatement / AllergyIntolerance). |
| **x402 (optional)** | Config-gated payment on `POST /catalog/v1/rank` only ([x402 v1 HTTP transport](https://github.com/coinbase/x402/blob/main/specs/transports-v1/http.md): `402` + `accepts[]`, `X-PAYMENT`, `X-PAYMENT-RESPONSE`). Mock facilitator by default for offline tests. |

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
npm run catalog -- show wetware-peptide-regulatory-au

# Rank agents for a synthetic patient (human-readable)
npm run catalog -- rank --patient fixtures/patients/synthetic-athlete-tendon-simple.json

# Machine-readable
npm run catalog -- rank --patient fixtures/patients/synthetic-t2dm-weight-simple.json --json

# Validate registry + evidence references
npm run catalog -- validate

# Start HTTP server (A2A + catalog index; no HTML UI)
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
1. wetware-peptide-clinical-advisor  score=0.87
   ... Top skill "holistic-peptide-recommendation" ...
   regulatory:
     ! Patient flagged as seeking compounded peptides — verify TGA ...
     ! [bpc-157] Verified fleet claim 4d0b84024d846a41: no TGA ARTG entry located (confirmed_2of2).

2. wetware-peptide-regulatory-au  score=0.78
   ... Top skill "wada-prohibited-list" ...
```

Fixtures (all synthetic):

- `fixtures/patients/synthetic-athlete-tendon-simple.json`
- `fixtures/patients/synthetic-t2dm-weight-simple.json`
- `fixtures/patients/synthetic-fertility-fhir.json` (FHIR Bundle)

## HTTP discovery (agents, not a frontend)

| Resource | Description |
|----------|-------------|
| `GET /.well-known/agent-card.json` | Catalog’s A2A AgentCard |
| `GET /catalog/v1/index` | Catalog index + link map |
| `GET /catalog/v1/domains` | Domain list |
| `GET /catalog/v1/domains/peptides/agents` | Agent cards in domain |
| `GET /catalog/v1/agents/{registryId}` | Full registry entry |
| `POST /catalog/v1/rank` | Rank operation (optional x402) |
| `POST /a2a/v1` | JSON-RPC 2.0 (`catalog/list`, `catalog/rank`) |

Responses use `Content-Type: application/json`, `ETag`, `Cache-Control`, and `Link` headers. `Accept: application/json` is expected; unsupported types receive `406`.

### x402 payment for `POST /catalog/v1/rank`

Disabled by default. Enable for testing:

```bash
export CATALOG_X402_ENABLED=true
export CATALOG_X402_PAY_TO=0x0000000000000000000000000000000000000001
export CATALOG_X402_AMOUNT=1000
export CATALOG_PUBLIC_BASE_URL=http://127.0.0.1:8787
npm run catalog -- serve
```

**1. Unpaid request → 402** with `PaymentRequirements` in the JSON body (`x402Version: 1`, `accepts[]`):

```bash
curl -sS -D - -o /tmp/rank402.json \
  -X POST http://127.0.0.1:8787/catalog/v1/rank \
  -H 'Content-Type: application/json' \
  -d @- <<'EOF'
{"domainId":"peptides","patient":{"format":"wetware.simple.v1","id":"x","displayName":"Test","clinicalGoals":["weight management","obesity"],"countryCode":"AU"},"limit":3}
EOF
```

**2. Paid retry** — build an `X-PAYMENT` header (base64 JSON `PaymentPayload` per x402 v1). Tests use the mock facilitator (`src/lib/x402.ts`); it accepts authorizations where `to` / `value` match the `accepts[0]` entry. Example using Node for a mock header:

```bash
PAYMENT=$(node --input-type=module -e "
  import { loadConfig } from './dist/lib/config.js';
  import { mockPaymentHeader } from './dist/lib/x402.js';
  const cfg = loadConfig({ x402: { enabled: true } });
  console.log(mockPaymentHeader(cfg.x402));
")

curl -sS -D - \
  -X POST http://127.0.0.1:8787/catalog/v1/rank \
  -H 'Content-Type: application/json' \
  -H "X-PAYMENT: $PAYMENT" \
  -d '{"domainId":"peptides","patient":{"format":"wetware.simple.v1","id":"x","displayName":"Test","clinicalGoals":["obesity"],"countryCode":"AU"}}'
```

On success, the response includes `X-PAYMENT-RESPONSE` (base64 `SettlementResponse`) and ranked agents in the body.

Environment variables (all optional):

| Variable | Default | Purpose |
|----------|---------|---------|
| `CATALOG_X402_ENABLED` | `false` | Gate rank endpoint |
| `CATALOG_X402_FACILITATOR_MODE` | `mock` | `mock` or `http` |
| `CATALOG_X402_FACILITATOR_URL` | — | Remote verify/settle when `http` |
| `CATALOG_X402_PAY_TO` | placeholder | Must be set in production via env |
| `CATALOG_X402_AMOUNT` | `1000` | Atomic units |
| `CATALOG_X402_NETWORK` | `base-sepolia` | x402 network id |
| `CATALOG_X402_ASSET` | USDC test address | Asset contract |

No private keys or wallets are stored in the repo.

## Adding a domain or agent

1. Create `registry/domains/<domainId>/<registryId>.json` matching `schemas/catalog-registry-entry.schema.json`.
2. Use a valid A2A AgentCard (required fields only from the spec; do not invent core fields).
3. Attach `skillEvidence` with `claim_id` values from `data/evidence/peptide-claims.compact.json` (or future domain corpora).
4. Extend `GOAL_PEPTIDE_MAP` / routing tags in `src/lib/rank.ts` as clinical matching rules evolve.
5. Run `npm run catalog -- validate`.

## Evidence regeneration

Raw fleet uploads are not committed. To rebuild from uploads:

```bash
CLAIM_UPLOADS_DIR=/path/to/uploads npm run build:evidence
```

## Tests

```bash
npm test
```

## License

MIT — see [LICENSE](LICENSE).
