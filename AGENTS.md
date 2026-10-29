# Agent contract — `graph.json`

You may have no other context about this repository. Follow this document for every read, write, merge, or validation action.

## Normative documents

**`AGENTS.md` is normative.** A validator, merge implementation, or autonomous updater must follow this file only.

**`README.md` is non-normative.** It orients humans; if README and AGENTS disagree, AGENTS wins.

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

- Citation list elements: bare strings `pmid:` + decimal digits only (see §3).
- Lists: sorted lexicographically ascending, no duplicates.
- `status` values: exactly `approved`, `investigational`, or `unapproved`.
- Every binder key in `status` **must** appear as a key in `pair`.
- Every binder key in `pair` **must** map to a non-empty object with at least one target key.
- **One molecule, one key:** the same biological molecule must not appear under two different binder keys in one file (see §8).

There is no `ref` map and no evidence grades.

## 3. Key grammar

**Binder** (biological keys only):

- `aa:` + one or more canonical L-chain segments. Residues: `ACDEFGHIKLMNPQRSTVWY`. Multi-chain: the `/`-separated segments must be in **non-decreasing** order by **byte order** (UTF-8 code unit order)—a **sorted multiset of chains** (equal segments allowed, e.g. `aa:ACD/ACD`). If reordering segments would change the multiset or the on-disk segment order is not non-decreasing → **invalid**. Pattern: `^aa:[ACDEFGHIKLMNPQRSTVWY]+(/[ACDEFGHIKLMNPQRSTVWY]+)*$` with that order constraint.
- `helm:` + HELM notation copied verbatim from the source record (no leading/trailing whitespace in the payload). The payload **must** be well-formed HELM (see §8). A SMILES or other non-HELM linear notation (e.g. `CC(=O)Oc1ccccc1C(=O)O`) **must** be rejected.

**Target** (single protein):

- `uniprot:` + UniProt accession. Official accession body: either `[OPQ][0-9][A-Z0-9]{3}[0-9]` or `[A-NR-Z][0-9]([A-Z][A-Z0-9]{2}[0-9]){1,2}`. Optional isoform suffix: `-` plus a **positive integer with no leading zeros** (`-1`, `-2`, …). `-0`, `-01`, etc. → **invalid**. `uniprot:P12345` and `uniprot:P12345-1` are **distinct keys**; a producer must pick one form per target and must not treat them as interchangeable. Pattern: `^uniprot:((?:[OPQ][0-9][A-Z0-9]{3}[0-9])|(?:[A-NR-Z][0-9](?:[A-Z][A-Z0-9]{2}[0-9]){1,2}))(?:-[1-9]\d*)?$`

**Citation**:

- `pmid:` + decimal digits with **no leading zeros** (first digit must be `1`–`9`, or the sole digit `0` for PMID `0` if ever used). Pattern: `^pmid:(?:0|[1-9]\d*)$`
- No `doi:`, URLs, or other citation forms.

Do not use binder prefixes on targets or citations; do not use target/citation prefixes on binders.

## 4. Inclusion rule (citation admission)

- List `pmid:…` under `pair[binder][target]` only if that paper reports **clinical benefit** for that binder–target pair.
- Exclude null results, harm-only results, and reports that do not establish clinical benefit for the pair.
- Every `pair[binder][target]` array is **non-empty**.
- If no paper qualifies, **do not** write that pair (no empty arrays).

Admission is semantic: you must verify against the paper; mechanical checks cannot replace this.

## 5. Canonical serialisation

- Encoding: **valid UTF-8** only; invalid byte sequences are invalid and must not be lossily repaired (no replacement characters).
- Root key order in file: `pair`, `status`.
- Every object: keys sorted lexicographically ascending.
- Every citation array: deduplicated, sorted lexicographically ascending.
- No trailing whitespace anywhere in the file after the JSON value except the mandatory final newline (see §8).
- The file **must** end with **exactly one** newline character (`0x0A`). No `\r\n` unless the entire file convention is explicitly UTF-8 with CRLF—default is single `\n` only. A missing final newline is **invalid**.
- On-disk text equals `JSON.stringify` of the logically canonical object after applying the rules above (given already-valid binder keys, including pre-sorted `aa:` chains).

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

Implement a validator from this section alone. Each condition is tagged **pure** (decidable from one file’s bytes alone), **relational** (needs a predecessor file), or **oracle** (needs an external source). **Passing a validator run proves only that the pure conditions hold**; relational and oracle conditions require separate checks.

1. **[pure] UTF-8:** Raw bytes decode as valid UTF-8. Any invalid sequence → **invalid** (do not substitute U+FFFD or strip bytes).

2. **[pure] Final newline:** The file ends with exactly one `\n` and no other trailing whitespace (no spaces, tabs, or extra newlines after that byte). Missing final newline → **invalid**.

3. **[pure] JSON root:** Content parses as JSON; root is a non-array object with **exactly** keys `pair` and `status` (no extra top-level keys).

4. **[pure] `pair` / `status` shape:** Both values are non-null objects (not arrays).

5. **[pure] Canonical bytes:** After parsing, re-serialising per §5 yields the same byte sequence as on disk (for a file that already passes binder-key rules).

6. **[pure] `aa:` chain order:** For every `aa:` binder key, the `/`-separated chain segments form a **non-decreasing** sequence by byte order (a **sorted multiset of chains**; repeats allowed). If the segment order is not non-decreasing → **invalid** (not merely non-canonical).

7. **[pure] `helm:` well-formedness:** For every `helm:` key, the payload after `helm:` is either bare HELM1/HELM2 text or HELM2 with an optional version suffix such as `V2.0` appended after the `$…$` sections. Structure: one or more **polymer blocks** separated by `|` (not `$`), each block `<TYPE><index>{<monomers>}` where `TYPE` is `PEPTIDE`, `RNA`, `CHEM`, or `BLOB` and `index` is a positive integer with no leading zeros; `{<monomers>}` is a **non-empty** dot-separated list of monomer symbols, each either one uppercase letter from the 20 standard residues or a bracketed symbol `[...]`; empty `{}`, SMILES or other non-monomer strings inside a `PEPTIDE{…}` block, and ASCII control characters or NUL bytes anywhere in the payload → **invalid**. After the polymer section comes `$<connections>$<groupings>$<ext>$` (`$` begins the connections section; it is **not** a polymer separator). At least one `PEPTIDE` polymer block is **required**. Payloads that are wholly non-HELM (e.g. a bare SMILES string such as `CC(=O)Oc1ccccc1C(=O)O` with no HELM polymer grammar) → **invalid**. **Open scope (ADC / multi-polymer):** whether a `CHEM` or `RNA` polymer may appear alongside a `PEPTIDE` polymer is **pending the repository owner**; this rule **neither admits nor rejects** such combinations—it only enforces the structural tests above when those blocks are present.

8. **[pure] `uniprot:` accessions:** Every target key matches §3, including isoform suffix `-` + positive integer without leading zeros when present.

9. **[pure] `pmid:` digits:** Every citation matches `^pmid:(?:0|[1-9]\d*)$` (no leading zeros on multi-digit PMIDs).

10. **[pure] `status` keys:** Every key satisfies binder grammar (conditions 6–7 as applicable); every value is `approved`, `investigational`, or `unapproved`.

11. **[pure] `pair` binders in `status`:** Every key in `pair` is a key in `status`.

12. **[pure] `status` binders in `pair`:** Every key in `status` is a key in `pair`.

13. **[pure] `pair` targets present:** Every binder in `pair` maps to a non-empty object with at least one target key.

14. **[pure] Target rows:** Each inner key satisfies §3 target grammar; each value is a non-empty array; elements satisfy condition 9; arrays are strictly sorted and duplicate-free.

15. **[pure] One molecule, one key:** Each biological molecule has **exactly one canonical key form** in this catalogue. Identity rules (decidable): (a) two `aa:` keys denote the same molecule iff their **sorted multisets** of `/`-separated chain segments are equal; (b) two `helm:` keys denote the same molecule iff their payloads are equal after normalising polymer **index** digits only (same `TYPE`, `{monomers}`, and `$…$` sections; indices may differ); (c) an `aa:` key and a `helm:` key that denote the same plain L-chain sequence denote the **same molecule**, and only the **`aa:` form is valid**—the `helm:` duplicate is **invalid**. No two distinct binder keys among `pair` and `status` may share a molecule under these rules.

16. **[pure] Cross-prefix hygiene:** No target or citation prefix on binder keys; no binder/citation prefix on target keys; citations only under `pair` lists.

17. **[oracle] Inclusion (semantic):** Every stored `(binder, target, pmid)` triple satisfies §4 (requires literature review).

18. **[pure] Refuse forbidden writes:** No stored ranks, grades, or non-`pmid:` citations (structural absence).

19. **[pure] Empty catalogue:** `{"pair":{},"status":{}}` satisfies conditions 1–16 and 18 when serialised with one trailing newline.

20. **[relational] Add-only (two-file):** Given a predecessor file `P` and successor file `S`, every binder, target, and `pmid:` edge present in `P` is present unchanged in `S` (same binder keys, same target keys per binder, same citation sets unless only superseded by human-directed process outside this spec). **A single-file validator cannot implement condition 20**; it requires comparing two revisions.

## 9. Background update contract

When extending the catalogue autonomously:

1. **Append-only growth:** satisfy §8 condition **20** against the prior committed `graph.json`, and add only rows that satisfy §2–§4 and §8 conditions **1–19**.
2. **Re-serialise:** after any edit, rewrite `graph.json` to §5 before persisting.
3. **No implementation in repo:** this repository does not ship updaters, cron, or CI. Compliance is your behavior against this contract only.

If a proposed row fails any rule above, **refuse** the write and report which condition failed.
