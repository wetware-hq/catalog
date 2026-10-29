⚠️ ACADEMIC RESEARCH PURPOSES ONLY; NOT FOR MEDICAL USE WITHOUT LICENSED OVERSIGHT

# `graph.json` — agent contract

`type: resource.reference` · **normative**. `README.md` is non-normative; on conflict this file governs. Implement validators, mergers and updaters from this file alone.

## 0. Scope

- **Read:** `graph.json`, `AGENTS.md`, `skills/*.md`, `LICENSE`.
- **Write:** `graph.json` and `proposals.json` only, under §9.
- **Refuse:** scripts, workflows, CI, package manifests or secondary data files in this repo, `proposals.json` (§9) being the single named exception; stored ranks, scores or grades; citations other than bare `pmid:<digits>`; empty citation arrays; pairs without qualifying evidence (§4); removal or rewriting of existing rows absent explicit human supersession.

## 0b. Documentation banner

Every Markdown file in this repository opens, as its **first non-blank line**, with the exact byte string

`⚠️ ACADEMIC RESEARCH PURPOSES ONLY; NOT FOR MEDICAL USE WITHOUT LICENSED OVERSIGHT`

— one fixed, repeated string, byte-identical in every file, never paraphrased, abbreviated or replaced by a cross-reference. It states **who may act on this repository**, and is deliberately distinct from the README's *What it is not* paragraph, which states what the catalogue records; the two are not merged. This is a normative documentation invariant. It is **not** one of the nineteen §8 predicates and does not renumber them; it is checked as a validator extension (see `catalog-validator`).

## 1. Purpose

Single-file bipartite database: biological binders → protein targets. An edge lists PubMed identifiers for that pair, in one of two dictionaries separated by **study type**: `pair` for clinical benefit in humans, `preclinical` for non-human or in-vitro utility. Protein-only (§3, §8.8). The two are never merged and never ranked against each other (§7).

## 2. Schema

Root: a non-array object with **exactly** `version`, `pair`, `preclinical`, in that order.

| key | type | meaning |
|---|---|---|
| `version` | `number` | schema version; currently `2` |
| `pair` | `Record<binder, Record<target, string[]>>` | binder → target → citations reporting **clinical benefit in humans** |
| `preclinical` | same shape as `pair` | citations reporting **non-human or in-vitro utility** |

- Both dictionaries obey every rule in this file identically; where a rule names `pair`, it binds `preclinical` too unless stated otherwise.
- Either dictionary may be empty (`{}`). A binder may appear in both; the same `(binder, target, pmid)` triple must not.
- Every binder key maps to a non-empty object; every target key to a non-empty array.
- Citations: bare `pmid:<digits>`, sorted ascending, deduplicated.
- One molecule, one key (§8.13), across both dictionaries.
- Absent by design: `status`, `ref`, evidence grades, ranks, scores. The `pair`/`preclinical` split is **study type, not strength**: it orders nothing and asserts nothing about weight of evidence.

## 3. Key grammar

**Binder** — biological only.

- `aa:` + one or more canonical L-chain segments over `ACDEFGHIKLMNPQRSTVWY`, `/`-separated. Segments **non-decreasing** by UTF-8 byte order — a sorted multiset, repeats allowed (`aa:ACD/ACD`). Non-decreasing violated → **invalid**, not merely non-canonical.
  `^aa:[ACDEFGHIKLMNPQRSTVWY]+(/[ACDEFGHIKLMNPQRSTVWY]+)*$` plus that order constraint.
- `helm:` + HELM copied verbatim from the source record, no surrounding whitespace, well-formed per §8.8. SMILES or other non-HELM linear notation → **invalid**.

**Target** — one protein.

- `uniprot:` + accession, optional isoform suffix `-` + positive integer, no leading zeros. `uniprot:P12345` and `uniprot:P12345-1` are **distinct keys**; pick one form per target and do not treat them as interchangeable.
  `^uniprot:((?:[OPQ][0-9][A-Z0-9]{3}[0-9])|(?:[A-NR-Z][0-9](?:[A-Z][A-Z0-9]{2}[0-9]){1,2}))(?:-[1-9]\d*)?$`

**Citation**

- `^pmid:(?:0|[1-9]\d*)$`. No `doi:`, URLs or other forms.

Prefixes do not cross roles: no target or citation prefix on a binder key, and none of the reverse.

The four namespace prefixes — `aa:`, `helm:`, `uniprot:`, `pmid:` — are **grammar, not style**: fixed, case-sensitive tokens with no synonyms and no abbreviations. Re-casing or renaming one invalidates every row that uses it. Files in this repository may be renamed; a key prefix may not.

## 4. Citation admission

- `pair[binder][target]` **iff** the paper reports **clinical benefit in humans** for that binder against that target.
- `preclinical[binder][target]` **iff** the paper reports utility in a non-human or in-vitro system for that pair, and makes no human-benefit claim.
- A paper reporting both belongs in `pair` only. If the study type cannot be determined from the paper, **refuse the row**; do not default to either dictionary.
- Exclude null results, harm-only results and anything short of utility for the pair.
- No qualifying paper → do not write the pair. Empty arrays are never valid.

Admission is **semantic** and is an **oracle** step (§8.16): verify against the paper. No grammar check, record lookup, or crawl substitutes for it, and no automated run discharges it — see §9.

## 5. Canonical serialisation

- Encoding: valid UTF-8. Invalid byte sequences are invalid and must not be repaired lossily (no U+FFFD, no stripping).
- Root key order: `version`, `pair`, `preclinical`. Every object: keys sorted ascending. Every citation array: sorted ascending, deduplicated.
- Indentation two spaces per level, one key or element per line, `": "` between key and value, `,` with no trailing space.
- Exactly one terminating `\n` (`0x0A`); no other trailing whitespace; missing final newline → **invalid**. `\r\n` only if the whole file convention is explicitly CRLF; default is `\n`.
- On-disk text = `JSON.stringify(obj, null, 2)` of the canonical object + that newline.

## 6. Merge

Merge valid `A`, `B` → `M`:

- `version`: must be equal in both. Different versions → **refuse**, never coerce.
- `pair` and `preclinical`: per dictionary, per binder and target, citations are the sorted deduplicated union. Never union across dictionaries.

Re-serialise per §5. Commutative, associative, idempotent.

## 7. Read contract

For a consumer reading the catalogue at runtime:

- **Pin the read.** Fetch `graph.json` at a commit SHA or a tag, never at a branch name. A branch tip moves; an agent that reads `main` twice may get two catalogues and cannot tell which it had. Read through the repository contents API at that SHA, not a CDN mirror — mirrors serve stale bytes.
- **Refuse an unknown `version`** outright (§8.4). Never read the recognised part of a newer file.
- **The reverse index belongs to the reader.** `pair` is keyed binder → target; the runtime question, target → binders, is derivable from those bytes and is the consumer's to build at read time. It is never stored: a second copy of the same facts has no merge law.
- **Absence is not a negative.** A missing pair means no qualifying paper has been entered. At present coverage that is not evidence that no such binder exists.
- **Absence is not a resolve failure.** Key resolution ([`skills/resolve-key.md`](skills/resolve-key.md)) has exactly two failure verdicts: `unresolved`, the record answered and matched zero or more than one entry — final, cacheable — and `unavailable`, the service did not answer — retry, cache nothing. Catalogue absence is neither. It is a read-layer fact about these bytes, reported by the reader's reverse index and never by the resolver: a binder can resolve perfectly and still not be entered. Mapping absence onto `unresolved` reads not-yet-entered as resolve-failed.

### Ranking

Never stored. Rank **within one dictionary only**; a `preclinical` row and a `pair` row are not comparable and must not appear in one ordering. For target `t` in dictionary `D`:

1. Binders `b` where `D[b][t]` is non-empty.
2. Rank by `|D[b][t]|` descending.
3. Tie-break: binder key ascending.

## 8. Validation predicates

Implement from this section alone. Tags: **pure** = decidable from one file's bytes; **relational** = needs a predecessor file; **oracle** = needs an external source. A passing validator run proves **only the pure conditions**.

1. **[pure] UTF-8.** Bytes decode as valid UTF-8.
2. **[pure] Final newline.** Exactly one `\n`, nothing after it.
3. **[pure] Root.** Parses as JSON; root is a non-array object with exactly `version`, `pair` and `preclinical`.
4. **[pure] `version`.** The number `2`. Any other value, or a string → **invalid**. An unknown version is **refused**, never partially read.
5. **[pure] Dictionary shape.** `pair` and `preclinical` are each a non-null object, not an array; either may be empty.
6. **[pure] Canonical bytes.** Re-serialising the parsed object per §5 reproduces the file byte for byte.
7. **[pure] `aa:` order.** Chain segments non-decreasing by byte order.
8. **[pure] `helm:` well-formedness.** Payload is bare HELM1/HELM2, optionally with a version suffix such as `V2.0` after the `$…$` sections.
   - Polymer blocks separated by `|`, each `<TYPE><index>{<monomers>}`; `index` a positive integer without leading zeros.
   - `TYPE` is `PEPTIDE`, the only admissible block type. **Per block, not per molecule:** `PEPTIDE1|PEPTIDE2|PEPTIDE3|PEPTIDE4` is valid; one non-`PEPTIDE` block invalidates the key.
   - `{<monomers>}` non-empty, dot-separated; each monomer one uppercase standard residue or a bracketed symbol `[...]`.
   - After the polymer section: `$<connections>$<groupings>$<ext>$`. `$` opens connections; it is not a polymer separator.
   - **Invalid:** `{}`; SMILES or other non-monomer text inside `PEPTIDE{…}`; ASCII control characters or NUL anywhere; a wholly non-HELM payload.
   - Two refusals, two predicates: a non-`PEPTIDE` block fails **scope**; `[CCO]` inside `PEPTIDE1{…}` fails **monomer**. Do not collapse them.
   - Protein-only is settled. `RNA`, `CHEM`, `BLOB` are out of scope by block type, which closes the ADC and multi-polymer question independently of block count.
9. **[pure] `uniprot:`.** Every target key matches §3.
10. **[pure] `pmid:`.** Every citation matches §3.
11. **[pure] Binder rows.** In each dictionary, every binder maps to a non-empty object with ≥1 target key.
12. **[pure] Target rows.** Inner keys satisfy §3; values are non-empty arrays, sorted, duplicate-free, elements satisfying condition 10.
13. **[pure] One molecule, one key.** Across both dictionaries. Decidable identity: (a) two `aa:` keys are the same molecule iff their sorted chain multisets are equal; (b) two `helm:` keys iff their payloads are equal after normalising polymer index digits only; (c) an `aa:` and a `helm:` key denoting the same plain L-chain sequence are the same molecule and only the `aa:` form is valid. No two distinct binder keys in `pair` or `preclinical` may share a molecule.
14. **[pure] Cross-prefix hygiene.** No role's prefix on another role's key; citations only inside citation arrays.
15. **[pure] No duplicate triple.** No `(binder, target, pmid)` triple appears in both `pair` and `preclinical`.
16. **[oracle] Inclusion and study type.** Every `(binder, target, pmid)` triple satisfies §4, in the dictionary it occupies. Requires reading the paper. **No validator run and no automated intake discharges this condition.**
17. **[pure] Forbidden writes.** No stored ranks, grades or non-`pmid:` citations.
18. **[pure] Empty catalogue.** The empty catalogue is `{`, `  "version": 2,`, `  "pair": {},`, `  "preclinical": {}`, `}` on five lines with one trailing newline, and satisfies conditions 1–15 and 17. Any compact one-line form **fails** condition 6 and is invalid.
19. **[relational] Add-only.** Given predecessor `P` and successor `S`, every binder, target and citation in `P` is present unchanged in `S`, in the same dictionary, except under human-directed supersession outside this spec. **A single-file validator cannot implement this.**

## 9. Background update contract

1. Satisfy §8.19 against the prior committed `graph.json`; add only rows satisfying §2–§4 and §8.1–§8.18.
2. Re-serialise to §5 before persisting.
3. **File boundary.** Autonomous intake writes `proposals.json` only, and never writes `graph.json` on any branch. Admission is the act of reading the paper, and that act is what moves bytes from `proposals.json` into `graph.json`, choosing the dictionary per §4. **Trust is carried by the file, not by a branch:** a branch name is mutable and has no merge law, so a fence of the form "unverified rows live on branch X" dissolves at the first merge and relaunders those rows as verified, while `proposals.json` merges into `proposals.json` on every branch. Condition 16 is therefore discharged at the file move, by a reader, and never by the run that proposed the row.
4. **`proposals.json`.** Root: a non-array object with exactly `version` (the number `2`) and `proposal` (an array). Each element has exactly `binder`, `target`, `pmid`, each satisfying §3. A proposal carries **no dictionary assignment**: `pair` versus `preclinical` is part of the oracle and is chosen when the paper is read. Serialise per §5; add-only per §8.19. It is not catalogue-shaped and must not be read as one.
5. Intake procedure: [`skills/propose-pairs.md`](skills/propose-pairs.md). It enumerates structured authorities; it does not crawl prose, and its own acceptance test is rediscovery of the rows already committed.
6. This repository ships no updater, cron or CI. Compliance is your behaviour against this contract.

A proposed row failing any rule above is **refused**, naming the condition that failed.

## 10. Skills

`skills/*.md` are procedures subordinate to this file; on any conflict this file governs (§0). Each skill declares its own description at its head and this file does not restate it: read the skill for what it does, read this section for where it may act.

| skill | namespaces (§3) | signature | write scope |
|---|---|---|---|
| [`skills/resolve-key.md`](skills/resolve-key.md) | `aa:` `helm:` `uniprot:`; never `pmid:` | `Key -> Identity \| unresolved \| unavailable`; verdicts per §7 | none; read-only |
| [`skills/propose-pairs.md`](skills/propose-pairs.md) | binder `aa:` `helm:`, target `uniprot:`, citation `pmid:` | candidate pairs -> `proposals.json` per §9.4 | `proposals.json` only, never `graph.json` |

- A skill may refuse more than this file requires, never less: it never admits a key §3 rejects.
- No skill discharges §8.16. `propose-pairs` proposes; a reader admits (§9.3).
- A skill does not widen §0. One needing to write anything else requires a change to this file first.
- Two skills, named here exactly. A procedure not listed in this section is not part of this contract.
