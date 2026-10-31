⚠️ ACADEMIC RESEARCH PURPOSES ONLY; NOT FOR MEDICAL USE WITHOUT LICENSED OVERSIGHT

# verifier

The `verifier/` namespace of [`wetware-hq/catalog`](https://github.com/wetware-hq/catalog): a dependency-light
checker for this repository's `graph.json` (binder → protein-target evidence graph). It implements the validation
predicates in `follow-agent-contract.md` **§8**, using the §2 schema, §3 key grammar, §5 canonical serialisation and §6 merge.
Standard library only, Python ≥ 3.9.
It reads; it writes nothing in this repository, and it is outside every agent's write scope (`follow-agent-contract.md` §0).

> A passing run proves **only the pure conditions** (and, with `--prev`, the one relational condition). The oracle
> predicate §8.16 is never discharged — it requires reading each paper (§4, §9.3).

## Install
Nothing to install: one file, `verify.py`, standard library only. The suite is `tests/`.

## Use
From the repository root:
```bash
python3 verifier/verify.py graph.json                 # pure predicates §8.1–§8.15, §8.17, §8.18
python3 verifier/verify.py --prev OLD.json graph.json # + relational §8.19 (add-only)
python3 verifier/verify.py --merge A.json B.json      # §6 merge -> canonical bytes on stdout
python3 verifier/verify.py graph.json --repo .        # + extension predicates E1 (banner), E2 (skill registry), E4 (system registry), E5 (identity line)
python3 verifier/verify.py graph.json --online        # + E3 pmid resolution via NCBI E-utilities (NON-BLOCKING)
python3 verifier/verify.py --trace core.trace a1.trace # TRACES judgements (tracer/record-fleet-traces.md); carrier sets are literals
python3 verifier/verify.py --json graph.json          # machine-readable report
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
| 17 Forbidden writes | pure | partly | checks only forbidden **root** keys, which cannot fail unless 3 already has; the non-`pmid:` citation half of the predicate is what 10 enforces |
| 18 Empty catalogue | pure | yes | exact 5-line canonical form |
| 19 Add-only | relational | yes (`--prev`) | needs a predecessor file |

## Extension predicates (beyond §8)

These are **not** part of follow-agent-contract.md §8's nineteen normative predicates and do not renumber them. They enforce
repository/documentation invariants agreed for `fleet.campaign` / `agent.skill` and are ids-prefixed `E`:

| id | tag | mode | what it checks |
|---|---|---|---|
| E1 Disclaimer banner | pure-ext | `--repo DIR` | the **first non-blank line** of every `.md` under `DIR` is byte-identical to `⚠️ ACADEMIC RESEARCH PURPOSES ONLY; NOT FOR MEDICAL USE WITHOUT LICENSED OVERSIGHT` — one fixed repeated string, no paraphrase or cross-reference (distinct from the README's *What it is not* scope paragraph). Exclusions: the exact paths in `E1_ALLOWLIST`, see below. |
| E2 Skill registry | pure-ext | `--repo DIR` | `skills/*.md` on disk and the rows of follow-agent-contract.md **§10** are in bijection (no orphan file, no dangling row); a skill whose header declares it `class: special` must declare write scope **`none`**. |
| E3 pmid resolution | online-ext | `--online` | every `pmid:` in `graph.json` resolves via NCBI E-utilities (`esummary`). **NON-BLOCKING**: it needs network + a live third-party service, is reported separately, and **never** changes the exit code. A service outage reports *UNAVAILABLE*, not a failure. |
| E4 System registry | pure-ext | `--repo DIR` | `systems/*.md` and `tracer/*.md` on disk and the paths named in follow-agent-contract.md **§11** are in bijection. The two directories are hard-coded; a markdown file anywhere else is not a system row. |
| E5 Identity line | pure-ext | `--repo DIR` | the header of every `skills/*.md`, `systems/*.md` and `tracer/*.md` matches follow-agent-contract.md **§0c**: skills are `type: resource.procedure` with `spec: agent.skill`, systems and tracer are `type: agent.system` with `spec: fleet.campaign`. `fleet/*.md` carries `spec: fleet.campaign` and declares no `type`. `agent.swarm` is refused as a `spec` or a `type`. The markdown may name that string when it says it is neither. |

E1, E2, E4, and E5 are pure and **do** gate (exit `1` on violation) when `--repo` is supplied. E3 never gates.

### Trace judgements

`--trace CORE.trace WORKER.trace …` decides `tracer/record-fleet-traces.md`. The carrier sets (`Skill`, `Act`, `Gate`, `Step`, `Fields`, `Context`) are literals in `verify.py`. They are not loaded from the markdown. Exit `0` is the judgement `result`. Any other exit is `partial` and names the first code in the spec's order: `R1`, `R3`, `admit`, then `R2`, `R4`–`R10`. `admit` reports the line code (`syntax`, `hash`, `run`, `skill`, `act`, `fields`, `value`, `parent`). A `result` does not discharge `follow-agent-contract.md` §8.16, and it does not decide that a logged act occurred.

### E1's exclusion allowlist

E1 has to skip exactly one file: `verifier/tests/fixtures/ext_disclaimer_fail/skip-disclaimer-banner.md` is a deliberately
unbannered fixture and is how E1 itself is tested, so scanning it would make the verifier fail by doing its job.

**The rule: an exclusion in a checker is only safe if the excluded thing is pinned by a test that fails when the
exclusion is abused.** Skipping the whole `tests/fixtures/` *directory* broke that rule — nothing failed if a
fixture quietly gained the banner, nothing failed if a real document was parked under `tests/fixtures/`, and the
blind spot grew with every file added. The exclusion is therefore `E1_ALLOWLIST`, a tuple of **exact
repo-relative paths**, one entry long; the other eight `.md` files under `fixtures/` carry the banner and are
scanned like any other file. Four tests hold it shut:

- `test_E1_every_allowlisted_path_fails_the_banner_check` — every listed path exists and **fails** the banner
  check. Add the banner to it, or delete it, and this test breaks.
- `test_E1_fixture_named_file_outside_the_fixtures_tree_still_fails` — a file named like the fixture, in a
  directory named like the fixture, anywhere but the allowlisted path, still fails E1. The exclusion is by exact
  path, never by name.
- `test_E1_real_file_at_an_allowlisted_path_is_skipped` — the one blind spot that remains, as a passing test
  rather than a paragraph someone can delete.
- `test_E1_repo_root_passes_with_the_fixtures_scanned` — E1 passes over the real repository with the eight
  bannered fixtures scanned, so widening the allowlist to hide a fixture would not go unnoticed here.

Version-control internals and generated tool caches (`.git`, `.pytest_cache`, `__pycache__`, …) are not walked at
all: they are not repository content, are absent from a fresh clone, and are not exclusions of anything.
A skill is "special" iff its header block (text before the first `## `) has a `class`/`type`/`spec` declaration
whose value is `special`. Every skill carries `spec: agent.skill`; that is not the special marker.

## Current result (`graph.json`: 55 `pair` rows, 41 targets, 0 `preclinical`)
All pure predicates **PASS**, and E1/E2/E4/E5 pass with `--repo .`. Add-only **PASSES** against `graph.json` at
`a5a768c` — the blob is unchanged (`05e317b`) since that commit, because no commit since then has touched the
catalogue. §8.16 is reported as not discharged. No violations found.

## Spec ambiguities encountered
1. **§8.8 monomer vs SMILES is not fully specified as a byte-decidable rule.** The spec tags §8.8 *pure* and gives
   `[CCO]` (SMILES) as a monomer failure while `[dF]`, `[Nle]`, `[ac]`, `[am]`, `[Thi]`, `[Hyp]`, `[dTic]`, `[Phi]`
   are valid, but gives no general predicate. This verifier uses a heuristic (`valid_monomer_symbol`): a bracketed
   token is a monomer iff it is alphanumeric and **not** an all-uppercase multi-letter run (which it reads as
   SMILES, matching the `[CCO]` example). This classifies every bracketed monomer in the current data correctly,
   but a real monomer code that is all-uppercase and >1 char would be a false negative. A registered-monomer-list
   check would be an oracle, which §8.8 forbids. Flagged for a spec clarification.
2. **§8.13(b) "normalising polymer index digits only".** Implemented by replacing digit runs that follow a letter
   or `]` (polymer block indices and connection indices) with a placeholder before comparison. The spec does not
   enumerate exactly which digits are "polymer index" vs. connection coordinates; the current data has no collision
   either way.
3. **§8.13(c) plain-L-chain HELM.** The spec says a HELM that denotes a plain L-chain is the same molecule as the
   `aa:` form and "only the `aa:` form is valid". This verifier flags it under §8.13 when it collides with an
   `aa:` molecule. A standalone plain-L-chain HELM with no `aa:` counterpart is arguably invalid on its own; the
   spec frames it as an identity rule, so this verifier reports only collisions. No such case exists in the data.
4. **§8.18 scope.** Reported only when both dictionaries are empty (otherwise N/A).

## Tests & CI
- `python3 verifier/tests/test_verify.py` — 39 verifier tests: one minimal failing fixture per pure predicate plus §8.19,
  failing + passing fixtures for the E1/E2/E4/E5 extension predicates (and an offline no-op test for E3), the four tests
  that pin E1's exclusion allowlist, the trace witness plus the admit / R9 / R10 refusals, and the HELM scope-vs-monomer distinction. (pytest optional; a stdlib runner is built in.)
  **`--merge` (§6) is not covered by the suite**: no test exercises it, so the merge path is implemented and unverified.
- `python3 fleet/tests/test_fleet.py` — 13 hermetic tests for the fleet emitter and its fail-closed live-service gates.
- `.github/workflows/validate.yml` — the GitHub Actions workflow that runs both suites on `wetware-hq/catalog`:
  the verifier and fleet tests, the pure predicates, the add-only check against the previous commit, and the E1/E2/E4/E5 extension
  predicates, with E3 in a separate non-blocking job. The workflow file keeps its `validate.yml` name so the
  check name GitHub reports does not move. A green run proves the pure conditions and the **gating** extension
  predicates E1, E2, E4, and E5, and nothing else: E3 is non-blocking (`continue-on-error: true`), so a green run says
  nothing about it, and §8.16 is never discharged by a machine (`follow-agent-contract.md` §9.6). The trace witness is in the unit tests, not in that workflow command.
