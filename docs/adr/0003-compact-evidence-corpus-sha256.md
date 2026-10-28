# Compact peptide evidence corpus with SHA-256 integrity sidecar

## Status

Accepted

## Context

Multi-model claim verification produces large JSONL uploads that must not be committed wholesale. The catalog still needs a stable, shippable evidence file for registry `skillEvidence` references and rank rationales, with auditable integrity.

## Decision

- Commit **`data/evidence/peptide-claims.compact.json`**, a reduced corpus preserving each claim’s `verification_status` and citation identifiers.
- Regenerate from local uploads via `npm run build:evidence` (`scripts/build-evidence.ts`) when JSONL inputs are available.
- Write **`data/evidence/peptide-claims.compact.sha256`** (GNU-style `hash  filename` line) on each build.
- Document provenance rules in **`data/evidence/PROVENANCE.md`** without embedding private upload paths in the committed corpus summary.

## Consequences

- Positive: Consumers can verify corpus bytes against the sidecar in CI (`npm run verify:evidence`).
- Positive: Registry validation detects missing or unknown `claim_id` references (`tests/validate.test.ts`).
- Negative: Regenerating evidence changes the SHA-256; releases must update the sidecar in the same commit.
- Verification: `tests/evidence-integrity.test.ts`, REQ-EVIDENCE-INTEGRITY-001 in `docs/requirements.yaml`.
