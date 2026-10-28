# x402 payment gating on catalog rank (HTTP)

## Status

Superseded by [0005-payments-deferred-node-http.md](./0005-payments-deferred-node-http.md) (payments deferred; x402 removed from the public catalog).

## Context

Ranking may be offered as a metered capability in deployed environments. The x402 v1 HTTP transport [1] defines payment-required responses and payment headers without embedding wallet secrets in the repository.

## Decision

- Gate **only** `POST /catalog/v1/rank` when `CATALOG_X402_ENABLED=true` (`src/lib/config.ts`).
- Return **402** with a JSON `PaymentRequiredResponse` (`x402Version`, `error`, `accepts[]`) from `src/lib/x402.ts`.
- Encode settlement metadata in **X-PAYMENT-RESPONSE** (base64 JSON); require **X-PAYMENT** on retry.
- Default to a **mock facilitator** for offline tests; optional HTTP facilitator URL for production wiring.
- Leave JSON-RPC `catalog/rank` on `/a2a/v1` **without** x402 in the current implementation (documented in OpenAPI [2]).

## Consequences

- Positive: Payment behavior is testable without chain access (`tests/http-x402.test.ts`).
- Positive: No private keys in repo; pay-to address comes from environment variables.
- Negative: Two rank entry points (REST vs JSON-RPC) differ in payment policy unless extended later.
- Verification: `tests/http-x402.test.ts`, REQ-X402-001 in `docs/requirements.yaml`.

## References

1. x402 v1 HTTP transport specification. https://github.com/coinbase/x402/blob/main/specs/transports-v1/http.md
2. OpenAPI description — `openapi/catalog.openapi.yaml` (402 responses on `/catalog/v1/rank`).
