# Compact peptide evidence corpus with SHA-256 integrity sidecar

## Status

Accepted

## Context

Multi-model claim verification produces large JSONL uploads that must not be committed wholesale. The catalog still needs a stable, shippable evidence file for registry `skillEvidence` references and rank rationales, with auditable integrity.

## Decision

- Commit **`data/evidence/peptide-claims.compact.json`**, a reduced corpus preserving each claim’s `verification_status` and citation identifiers.
- Regenerate from local uploads via `npm run build:evidence` (`scripts/build-evidence.ts`) when JSONL inputs are available.
- Pin integrity with **`data/evidence/peptide-claims.compact.gitoid`** (single-line `git hash-object` blob id) — replaces the earlier SHA-256 sidecar to drop duplicate hashing code while staying verifiable in git CI checkouts [1].
- Document provenance rules in **`data/evidence/PROVENANCE.md`** without embedding private upload paths in the committed corpus summary.
- Maintain **`data/evidence/REFERENCES.md`** [2] as the aggregated third-party source index for the corpus.

## Consequences

- Positive: Consumers can verify corpus bytes via `npm run check` (git oid + REFERENCES sync).
- Positive: Registry validation detects missing or unknown `claim_id` references (`tests/validate.test.ts`).
- Negative: Regenerating evidence changes the git oid; releases must update `.gitoid` in the same commit. Requires `git` on PATH (true in CI; not for bare tarball downloads without git).
- Verification: `npm run check`, REQ-EVIDENCE-INTEGRITY-001 in `docs/requirements.yaml`.

## References

1. Git `hash-object` — blob object id for committed corpus bytes. https://git-scm.com/docs/git-hash-object
2. `data/evidence/REFERENCES.md` — generated bibliography (`npm run build:evidence`).
