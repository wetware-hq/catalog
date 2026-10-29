# graph.json — agent-native specification

## 1. Purpose

Single-file bipartite database: binders linked to protein targets, each edge annotated with citations that report clinical benefit. Representation is three JSON object dictionaries in one root object (`graph.json`).

## 2. Schema

Root object keys (fixed order on disk): `pair`, then `status`, then `ref`.

| Key | Type | Meaning |
|-----|------|---------|
| `pair` | `Record<binder, Record<target, string[]>>` | For each binder, map each target to a citation list. |
| `status` | `Record<binder, string>` | Regulatory status for each binder that appears in `pair`. |
| `ref` | `Record<citation, string>` | Evidence grade for each citation that appears in any `pair` list. |

- Citation lists: sorted lexicographically, no duplicates.
- `status` values: exactly one of `approved`, `investigational`, `unapproved`.
- `ref` values: evidence grades (see §4).

## 3. Key grammar

**Binder** (biological keys only):

- `aa:` + one or more canonical L-chain segments. Alphabet: `ACDEFGHIKLMNPQRSTVWY`. Multi-chain: sort chain strings ascending, join with `/`. Pattern: `^aa:[ACDEFGHIKLMNPQRSTVWY]+(/[ACDEFGHIKLMNPQRSTVWY]+)*$`
- `helm:` + HELM string copied verbatim from the source record (non-whitespace payload). Pattern: `^helm:\S+$`

**Target** (single protein):

- `uniprot:` + accession. Pattern: `^uniprot:[A-Z][A-Z0-9]{5,9}$`

**Citation**:

- `pmid:` + decimal digits only.
- `doi:` + arbitrary non-empty string (DOI as stored).

Binder keys must not use target/citation prefixes; targets must not use binder/citation prefixes.

## 4. Grade order (strongest → weakest)

`meta` > `rct` > `trial` > `observational` > `case` > `animal` > `in_vitro` > `claim`

`ref` values must be members of this set.

## 5. Inclusion rule

- A citation is listed under `pair[binder][target]` only if it reports **clinical benefit** for that binder–target pair.
- Exclude null results, harm-only results, and non–clinical-benefit reports.
- Every `(binder, target)` entry in `pair` has **at least one** citation.
- Pairs with no qualifying citations are **omitted** from `pair` (not stored as empty lists).

## 6. Canonical serialisation

- Encoding: UTF-8.
- Root key order in file: `pair`, `status`, `ref`.
- At every object level: keys sorted lexicographically ascending.
- Every citation array: deduplicated, sorted lexicographically ascending.
- No trailing whitespace on any line.
- File ends with exactly one `\n` after the JSON text.
- On-disk text must equal `JSON.stringify` of the logically canonical object (after applying the sorting/dedup rules above).

## 7. Merge semantics

Merge two valid graphs `A` and `B` into `M`:

- **`pair`**: For each binder and target, citation lists are the sorted deduplicated union of lists from `A` and `B`.
- **`status`**: For each binder key present in either map, if both define a status, keep the **weaker** under order `approved` < `investigational` < `unapproved` (weaker = later in that list).
- **`ref`**: For each citation key present in either map, if both define a grade, keep the **weaker** under the grade order in §4 (weaker = later in that list).

Then re-serialise per §6. This merge is commutative, associative, and idempotent.

## 8. Read-time matching (never stored)

Derived views only; do not persist ranks or scores in `graph.json`.

For each target `t`:

1. For each binder `b` with row `pair[b][t]`, let `G(b,t) = max{ ref[c] | c ∈ pair[b][t] }` where max uses §4 order.
2. Rank binders by `G(b,t)` descending (stronger grade first).
3. Tie-break: larger citation count `|pair[b][t]|`; if still tied, binder key ascending lexicographic.

## 9. Validation predicates

A file is **valid** iff all hold:

1. Parses as JSON and root is a non-array object with exactly keys `pair`, `status`, `ref` (no extra top-level keys).
2. `pair`, `status`, `ref` are each non-null objects (not arrays).
3. Every key in `status` satisfies binder grammar (§3) and maps to `approved`, `investigational`, or `unapproved`.
4. Every key in `ref` satisfies citation grammar (§3) and maps to a grade in §4.
5. Every key in `pair` satisfies binder grammar (§3) and exists as a key in `status`.
6. For each `pair[binder]`, values are non-array objects; every inner key satisfies target grammar (§3).
7. For each `pair[binder][target]`, value is a non-empty array of citation keys; each element satisfies citation grammar (§3); array is strictly sorted and duplicate-free.
8. For every citation `c` in any `pair` list, `c` is a key in `ref`.
9. Inclusion rule (§5) is satisfied for every stored pair and citation (semantic; agent verifies against sources).
10. On-disk bytes match canonical serialisation (§6).

An agent **regenerates a validator** by implementing checks 1–8 and 10 mechanically; check 9 requires evidence review.

## 10. Background update contract

An autonomous agent may **extend** `graph.json` by:

1. Adding only new binders, targets, citations, or rows that satisfy §2–§5 and §9.
2. Never removing or rewriting existing keys except by explicit supersession policy defined outside this file (not stored here).
3. After any edit, re-serialising to §6 before commit.

No batch job, workflow, or executable updater is part of this repository; compliance is by agent behavior against this spec.
