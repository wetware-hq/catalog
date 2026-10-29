⚠️ ACADEMIC RESEARCH PURPOSES ONLY; NOT FOR MEDICAL USE WITHOUT LICENSED OVERSIGHT

# catalog-validator

A dependency-light validator for [`wetware-hq/catalog`](https://github.com/wetware-hq/catalog)'s `graph.json`
(binder → protein-target evidence graph). It implements the validation predicates in `AGENTS.md` **§8**, using the
§2 schema, §3 key grammar, §5 canonical serialisation and §6 merge. Standard library only, Python ≥ 3.9.
It does not modify the catalog repo.

> A passing run proves **only the pure conditions** (and, with `--prev`, the one relational condition). The oracle
> predicate §8.16 is never discharged — it requires reading each paper (§4, §9.3).

## Install
None. Copy `validate.py` (and `tests/` if you want the suite). No third-party packages.

## Use
```bash
python3 validate.py graph.json                 # pure predicates §8.1–§8.15, §8.17, §8.18
python3 validate.py --prev OLD.json graph.json  # + relational §8.19 (add-only)
python3 validate.py --merge A.json B.json       # §6 merge -> canonical bytes on stdout
python3 validate.py graph.json --repo .         # + extension predicates E1 (banner), E2 (skill registry)
python3 validate.py graph.json --online         # + E3 pmid resolution via NCBI E-utilities (NON-BLOCKING)
python3 validate.py --json graph.json           # machine-readable report
```
Exit status: `0` all evaluated predicates passed · `1` a violation/refusal · `2` usage/IO error.
Each failing predicate prints its id (e.g. `8.13`) and the offending row.

## Predicate coverage (§8)
| # | tag | implemented | note |
|---|---|---|---|
| 1 UTF-8 | pure | yes | strict decode |
| 2 Final newline | pure | yes | exactly one `\n`, no extra trailing whitespace |
| 3 Root | pure | yes | non-array object, exactly `version`/`pair`/`preclinical` |
| 4 version | pure | yes | number `2`; string `"2"` or other → invalid |
| 5 Dictionary shape | pure | yes | each a non-null object, not array |
| 6 Canonical bytes | pure | yes | re-serialise per §5, compare byte-for-byte |
| 7 aa: grammar + order | pure | yes | §3 regex + non-decreasing segments |
| 8 helm: well-formedness | pure | yes | structure / `$…$…$…$` / control chars |
| 8-scope | pure | yes | `PEPTIDE`-only block type, per block |
| 8-monomer | pure | yes | monomer vs SMILES (e.g. `[CCO]`) — see ambiguity below |
| 9 uniprot: | pure | yes | §3 regex, isoform rules |
| 10 pmid: | pure | yes | §3 regex, no leading zeros |
| 11 Binder rows | pure | yes | ≥1 target |
| 12 Target rows | pure | yes | sorted, dedup, non-empty citation arrays |
| 13 One molecule, one key | pure | yes | aa multiset; helm index-normalised; aa↔plain-L-chain-helm |
| 14 Cross-prefix hygiene | pure | yes | prefixes do not cross roles |
| 15 No duplicate triple | pure | yes | `(binder,target,pmid)` not in both dictionaries |
| 16 Inclusion/study type | **oracle** | **NOT discharged** | reported, never checked (needs the paper) |
| 17 Forbidden writes | pure | yes | no stored rank/score/grade/status/ref keys |
| 18 Empty catalogue | pure | yes | exact 5-line canonical form |
| 19 Add-only | relational | yes (`--prev`) | needs a predecessor file |

## Extension predicates (beyond §8)

These are **not** part of AGENTS.md §8's nineteen normative predicates and do not renumber them. They enforce
repository/documentation invariants agreed for the `system.fleet` and are ids-prefixed `E`:

| id | tag | mode | what it checks |
|---|---|---|---|
| E1 Disclaimer banner | pure-ext | `--repo DIR` | the **first non-blank line** of every `.md` under `DIR` is byte-identical to `⚠️ ACADEMIC RESEARCH PURPOSES ONLY; NOT FOR MEDICAL USE WITHOUT LICENSED OVERSIGHT` — one fixed repeated string, no paraphrase or cross-reference (distinct from the README's *What it is not* scope paragraph). |
| E2 Skill registry | pure-ext | `--repo DIR` | `skills/*.md` on disk and the rows of AGENTS.md **§10** are in bijection (no orphan file, no dangling row); a skill whose header declares it a `special` / `agent.skill` must declare write scope **`none`**. |
| E3 pmid resolution | online-ext | `--online` | every `pmid:` in `graph.json` resolves via NCBI E-utilities (`esummary`). **NON-BLOCKING**: it needs network + a live third-party service, is reported separately, and **never** changes the exit code. A service outage reports *UNAVAILABLE*, not a failure. |

E1/E2 are pure and **do** gate (exit `1` on violation) when `--repo` is supplied. E3 never gates.
A skill is "special" iff its header block (text before the first `## `) contains the token `agent.skill`, or a
`class`/`type`/`spec` declaration whose value is `special`.

## Current result (graph.json @ commit 9e2f1d9, 55 `pair` rows, 0 `preclinical`)
All pure predicates **PASS**. Add-only **PASSES** against the first row-bearing commit (`b5fd668`). §8.16 is reported
as not discharged. No violations found.

## Spec ambiguities encountered
1. **§8.8 monomer vs SMILES is not fully specified as a byte-decidable rule.** The spec tags §8.8 *pure* and gives
   `[CCO]` (SMILES) as a monomer failure while `[dF]`, `[Nle]`, `[ac]`, `[am]`, `[Thi]`, `[Hyp]`, `[dTic]`, `[Phi]`
   are valid, but gives no general predicate. This validator uses a heuristic (`valid_monomer_symbol`): a bracketed
   token is a monomer iff it is alphanumeric and **not** an all-uppercase multi-letter run (which it reads as
   SMILES, matching the `[CCO]` example). This classifies every bracketed monomer in the current data correctly,
   but a real monomer code that is all-uppercase and >1 char would be a false negative. A registered-monomer-list
   check would be an oracle, which §8.8 forbids. Flagged for a spec clarification.
2. **§8.13(b) "normalising polymer index digits only".** Implemented by replacing digit runs that follow a letter
   or `]` (polymer block indices and connection indices) with a placeholder before comparison. The spec does not
   enumerate exactly which digits are "polymer index" vs. connection coordinates; the current data has no collision
   either way.
3. **§8.13(c) plain-L-chain HELM.** The spec says a HELM that denotes a plain L-chain is the same molecule as the
   `aa:` form and "only the `aa:` form is valid". This validator flags it under §8.13 when it collides with an
   `aa:` molecule. A standalone plain-L-chain HELM with no `aa:` counterpart is arguably invalid on its own; the
   spec frames it as an identity rule, so this validator reports only collisions. No such case exists in the data.
4. **§8.18 scope.** Reported only when both dictionaries are empty (otherwise N/A).

## Tests & CI
- `python3 tests/test_validate.py` — 25 tests: one minimal failing fixture per pure predicate plus §8.19 and merge,
  and failing + passing fixtures for the E1/E2 extension predicates (and an offline no-op test for E3),
  including the HELM scope-vs-monomer distinction. (pytest optional; a stdlib runner is built in.)
- `.github/workflows/validate.yml` — ready-to-use GitHub Actions workflow (runs tests, pure predicates, and the
  add-only check against the previous commit). Not pushed anywhere.
