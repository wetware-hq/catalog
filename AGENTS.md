# Agent contract — `graph.json`

You may have no other context about this repository. Follow this document for every read, write, merge, or validation action.

## Scope

**Read:** `graph.json`, this file, `LICENSE`.

**Write:** only `graph.json` (when authorised by the background-update contract below).

**Refuse:** adding scripts, workflows, CI, package manifests, or secondary data files to this repo; storing computed ranks or scores in `graph.json`; citations other than bare `pmid:<digits>`; empty citation lists; pairs without clinical-benefit evidence; removing or rewriting existing rows without explicit human supersession instruction outside this file.

## 1. Purpose

Single-file bipartite database: binders linked to protein targets. Each stored `(binder, target)` edge lists PubMed identifiers for papers that report **clinical benefit** for that pair. Regulatory status is recorded per binder. Representation: two JSON object dictionaries in one root object.

## 2. Schema

Root object keys (fixed order on disk): `pair`, then `status`.

| Key | Type | Meaning |
|-----|------|---------|
| `pair` | `Record<binder, Record<target, string[]>>` | Binder → target → citation list. |
| `status` | `Record<binder, string>` | Regulatory status for each binder that appears in `pair`. |

- Citation list elements: bare strings `pmid:` + decimal digits only.
- Lists: sorted lexicographically ascending, no duplicates.
- `status` values: exactly `approved`, `investigational`, or `unapproved`.

There is no `ref` map and no evidence grades.

## 3. Key grammar

**Binder** (biological keys only):

- `aa:` + one or more canonical L-chain segments. Residues: `ACDEFGHIKLMNPQRSTVWY`. Multi-chain: sort chain strings ascending, join with `/`. Pattern: `^aa:[ACDEFGHIKLMNPQRSTVWY]+(/[ACDEFGHIKLMNPQRSTVWY]+)*$`
- `helm:` + HELM string copied verbatim from the source record (non-whitespace after prefix). Pattern: `^helm:\S+$`

**Target** (single protein):

- `uniprot:` + accession. Pattern: `^uniprot:[A-Z][A-Z0-9]{5,9}$`

**Citation**:

- `pmid:` + one or more ASCII digits. Pattern: `^pmid:\d+$`
- No `doi:`, URLs, or other citation forms.

Do not use binder prefixes on targets or citations; do not use target/citation prefixes on binders.

## 4. Inclusion rule (citation admission)

- List `pmid:…` under `pair[binder][target]` only if that paper reports **clinical benefit** for that binder–target pair.
- Exclude null results, harm-only results, and reports that do not establish clinical benefit for the pair.
- Every `pair[binder][target]` array is **non-empty**.
- If no paper qualifies, **do not** write that pair (no empty arrays).

Admission is semantic: you must verify against the paper; mechanical checks cannot replace this.

## 5. Canonical serialisation

- Encoding: UTF-8.
- Root key order in file: `pair`, `status`.
- Every object: keys sorted lexicographically ascending.
- Every citation array: deduplicated, sorted lexicographically ascending.
- No trailing whitespace on any line.
- File ends with exactly one `\n` after the JSON text.
- On-disk text equals `JSON.stringify` of the logically canonical object after applying the rules above.

## 6. Merge semantics

Merge valid graphs `A` and `B` into `M`:

- **`pair`**: For each binder and target, citation lists are the sorted deduplicated union of lists from `A` and `B`.
- **`status`**: For each binder in either map, if both define a status, keep the **weaker** value. Strength order (strongest first): `approved` > `investigational` > `unapproved`. Weaker = later in that list when merging conflicts.

Re-serialise per §5. Merge is commutative, associative, and idempotent.

## 7. Read-time matching (never stored)

Do not write ranks, scores, or aggregates into `graph.json`.

For each target `t`:

1. Consider binders `b` with non-empty `pair[b][t]`.
2. Rank by citation count `|pair[b][t]|` descending.
3. Tie-break: binder key ascending lexicographic.

## 8. Validation predicates

Implement a validator; a file is **valid** iff:

1. Parses as JSON; root is a non-array object with exactly keys `pair`, `status` (no extras).
2. `pair` and `status` are non-null objects (not arrays).
3. Every `status` key satisfies binder grammar (§3); every value is `approved`, `investigational`, or `unapproved`.
4. Every `pair` key satisfies binder grammar (§3) and is a key in `status`.
5. Each `pair[binder]` is a non-array object; each inner key satisfies target grammar (§3).
6. Each `pair[binder][target]` is a non-empty array; each element matches `^pmid:\d+$`; array is strictly sorted, duplicate-free.
7. Inclusion rule (§4) holds for every stored pair and PMID (semantic review).
8. On-disk bytes match canonical serialisation (§5).

Checks 1–6 and 8 are mechanical; check 7 requires evidence review.

## 9. Background update contract

When extending the catalogue autonomously:

1. **Append-only growth:** add binders, targets, PMIDs, or status rows that satisfy §2–§4 and validation §8. Do not delete or overwrite existing entries unless a human explicitly instructs supersession outside this repo.
2. **Re-serialise:** after any edit, rewrite `graph.json` to §5 before persisting.
3. **No implementation in repo:** this repository does not ship updaters, cron, or CI. Compliance is your behavior against this contract only.

If a proposed row fails any rule above, **refuse** the write and report which condition failed.
