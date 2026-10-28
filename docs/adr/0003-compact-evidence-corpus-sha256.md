# Compact peptide evidence corpus with SHA-256 integrity sidecar

## Status

Accepted

## Context

Multi-model claim verification produces large JSONL uploads that must not be committed wholesale. The catalog still needs a stable, shippable evidence file for registry `skillEvidence` references and rank rationales, with auditable integrity.

## Decision

- Commit **`data/evidence/peptide-claims.compact.json`**, a reduced corpus preserving each claim’s `verification_status` and citation identifiers.
- Regenerate from local uploads via `npm run build:evidence` (`scripts/build-evidence.ts`) when JSONL inputs are available.
- Write **`data/evidence/peptide-claims.compact.sha256`** (GNU-style `hash  filename` line) on each build using SHA-256 [1].
- Document provenance rules in **`data/evidence/PROVENANCE.md`** without embedding private upload paths in the committed corpus summary.
- Maintain **`data/evidence/REFERENCES.md`** [2] as the aggregated third-party source index for the corpus.

## Consequences

- Positive: Consumers can verify corpus bytes against the sidecar in CI (`npm run verify:evidence`).
- Positive: Registry validation detects missing or unknown `claim_id` references (`tests/validate.test.ts`).
- Negative: Regenerating evidence changes the SHA-256; releases must update the sidecar in the same commit.
- Verification: `tests/evidence-integrity.test.ts`, REQ-EVIDENCE-INTEGRITY-001 in `docs/requirements.yaml`.

## References

1. FIPS 180-4 — Secure Hash Standard (SHA-256). https://csrc.nist.gov/publications/detail/fips/180/4/final
2. `data/evidence/REFERENCES.md` — generated bibliography (`npm run generate:evidence-references`).
