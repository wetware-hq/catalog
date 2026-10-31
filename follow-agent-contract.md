⚠️ ACADEMIC RESEARCH PURPOSES ONLY; NOT FOR MEDICAL USE WITHOUT LICENSED OVERSIGHT

# `graph.json` — agent contract

`type: resource.reference` · **normative**. `read-repository.md` is non-normative; on conflict this file governs. Implement verifiers, mergers and updaters from this file alone.

## 0. Scope

- **Read:** `graph.json`, `follow-agent-contract.md`, `skills/*.md`, `systems/*.md` (§11), `pin-references.md`, `read-repository.md` (non-normative), `fleet/`, `verifier/`, `.github/workflows/`, `LICENSE`.
- **Write:** `graph.json` and `proposals.json` only, under §9.
- **Refuse:** writing scripts, workflows, CI, package manifests or secondary data files in this repo, `proposals.json` (§9) being the single named exception — the fleet harness under `fleet/`, verifier under `verifier/` and workflow under `.github/workflows/` are human-directed additions that exercise or check this contract and are outside every agent's write scope, so an agent reads them and does not edit them; stored ranks, scores or grades; citations other than bare `pmid:<digits>`; empty citation arrays; pairs without qualifying evidence (§4); removal or rewriting of existing rows absent explicit human supersession.

## 0b. Documentation banner

Every Markdown file in this repository opens, as its **first non-blank line**, with the exact byte string

`⚠️ ACADEMIC RESEARCH PURPOSES ONLY; NOT FOR MEDICAL USE WITHOUT LICENSED OVERSIGHT`

— one fixed, repeated string, byte-identical in every file, never paraphrased, abbreviated or replaced by a cross-reference. It states **who may act on this repository**, and is deliberately distinct from the README's *What it is not* paragraph, which states what the catalogue records; the two are not merged. This is a normative documentation invariant. It is **not** one of the nineteen §8 predicates and does not renumber them; it is checked as a verifier extension, predicate E1 (see `verifier/`).

## 0c. Identity line

Every file in `skills/` and `systems/` names itself once, in the header, before the first section heading. Extension predicate E5 checks that line. E5 is not a §8 predicate and does not renumber them.

| directory | what the line says |
|---|---|
| `skills/` | a `resource.procedure`, spec `agent.skill`. The one skill §10 marks `special` also says so. The others do not. |
| `systems/` | an `agent.system`, spec `fleet.campaign`. No class. |

`agent.skill` is the spec of a procedure. `fleet.campaign` is the spec of one run. `agent.swarm` and `agent.fleet` are not specs and not types. A header outside these two directories that carries either spec fails E5: that file is an orphan. The checker skips exactly two registry fixtures, `verifier/tests/fixtures/ext_registry_fail/skills/exercise-special-scope.md` and `verifier/tests/fixtures/ext_registry_ok/skills/exercise-special-scope.md`. They declare the skill spec so E2 can be tested, and they are not skills of this contract. The harness code under `fleet/` is not a row of this table. Its specification is [`systems/read-fleet.md`](systems/read-fleet.md). The four strings, and the ordinary words next to them, are set out in §11.

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

Implement from this section alone. Tags: **pure** = decidable from one file's bytes; **relational** = needs a predecessor file; **oracle** = needs an external source. A passing verifier run proves **only the pure conditions**.

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
16. **[oracle] Inclusion and study type.** Every `(binder, target, pmid)` triple satisfies §4, in the dictionary it occupies. Requires reading the paper. **No verifier run and no automated intake discharges this condition.**
17. **[pure] Forbidden writes.** No stored ranks, grades or non-`pmid:` citations.
18. **[pure] Empty catalogue.** The empty catalogue is `{`, `  "version": 2,`, `  "pair": {},`, `  "preclinical": {}`, `}` on five lines with one trailing newline, and satisfies conditions 1–15 and 17. Any compact one-line form **fails** condition 6 and is invalid.
19. **[relational] Add-only.** Given predecessor `P` and successor `S`, every binder, target and citation in `P` is present unchanged in `S`, in the same dictionary, except under human-directed supersession outside this spec. **A single-file verifier cannot implement this.**

## 9. Background update contract

1. Satisfy §8.19 against the prior committed `graph.json`; add only rows satisfying §2–§4 and §8.1–§8.18.
2. Re-serialise to §5 before persisting.
3. **File boundary.** Autonomous intake writes `proposals.json` only, and never writes `graph.json` on any branch. Admission is the act of reading the paper, and that act is what moves bytes from `proposals.json` into `graph.json`, choosing the dictionary per §4. **Trust is carried by the file, not by a branch:** a branch name is mutable and has no merge law, so a fence of the form "unverified rows live on branch X" dissolves at the first merge and relaunders those rows as verified, while `proposals.json` merges into `proposals.json` on every branch. Condition 16 is therefore discharged at the file move, by a reader, and never by the run that proposed the row.
4. **`proposals.json`.** Root: a non-array object with exactly `version` (the number `2`) and `proposal` (an array). Each element has exactly `binder`, `target`, `pmid`, each satisfying §3. A proposal carries **no dictionary assignment**: `pair` versus `preclinical` is part of the oracle and is chosen when the paper is read. Serialise per §5; add-only per §8.19. It is not catalogue-shaped and must not be read as one.
5. Intake procedure: [`skills/propose-pairs.md`](skills/propose-pairs.md). It enumerates structured authorities; it does not crawl prose, and its own acceptance test is rediscovery of the rows already committed.
6. This repository ships no updater and no cron. It does ship a verifier (`verifier/`) and a workflow (`.github/workflows/validate.yml`) that runs it, and neither writes `graph.json` or `proposals.json`: a passing run proves only the pure conditions (§8) and the repository extension predicates E1, E2, E4, and E5, which are not §8 predicates and do not renumber them (E3, pmid resolution, is non-blocking and gates nothing). It never proves §8.16. Compliance is your behaviour against this contract, not a green check.

A proposed row failing any rule above is **refused**, naming the condition that failed.

## 10. Skills

`skills/*.md` are procedures subordinate to this file; on any conflict this file governs (§0). Each skill declares its own description at its head and this file does not restate it: read the skill for what it does, read this section for where it may act.

| skill | namespaces (§3) | signature | write scope |
|---|---|---|---|
| [`skills/resolve-key.md`](skills/resolve-key.md) | `aa:` `helm:` `uniprot:`; never `pmid:` | `Key -> Identity \| unresolved \| unavailable`; verdicts per §7 | none; read-only |
| [`skills/propose-pairs.md`](skills/propose-pairs.md) | binder `aa:` `helm:`, target `uniprot:`, citation `pmid:` | candidate pairs -> `proposals.json` per §9.4 | `proposals.json` only, never `graph.json` |

**Special class.** The classes are defined by what a skill does to claims. A **catalogue** skill is conservative: it relocates facts that already exist, and is bound by §4. A **`class: special`** skill originates a claim no source has reported; it writes nothing, its output is categorically ineligible for `graph.json` and for `proposals.json`, and its oracle is not a read paper. Classify the next skill by that test, not by precedent.

No separate directory is needed, and none is used: a `special` skill has **no output file**, so there is no boundary to erode. That write-nothing contract is what the class rests on, and it is checkable — **a `class: special` row declares write scope `none`**, and a skill whose output could reach either dictionary is not `special`, it is a catalogue skill and §4 binds it.

The reader-facing warning is therefore not carried by a path either. It is carried by the **emitted report**, verbatim on the same block as every sequence (see the skill's §7), because the report is the only thing that leaves.

| skill | class | namespaces (§3) | signature | write scope |
|---|---|---|---|---|
| [`skills/design-binder.md`](skills/design-binder.md) | `special` | target `uniprot:` (human only); emits binder `aa:` `helm:`; never `pmid:` | `(Target, Indication) -> Binder \| unranked candidates`; refusals per the skill's §3 and §7 | **none**; writes no file in this repository |


- A skill may refuse more than this file requires, never less: it never admits a key §3 rejects.
- No skill discharges §8.16. `propose-pairs` proposes; a reader admits (§9.3).
- `design-binder` is `special` and writes nothing (§4, §9.4): a de novo design has no qualifying paper, so no element of `graph.json` or `proposals.json` can hold it. There is no designs file either — its oracle is a measured Kd, which makes its output an experimental worklist rather than a database. A designed molecule enters only once a paper exists, by `propose-pairs` and a reader.
- A skill does not widen §0. One needing to write anything else requires a change to this file first.
- Three skills, named here exactly — two catalogue procedures and one `special`. A procedure not listed in this section is not part of this contract.

## 11. Systems

`systems/*.md` are specifications of machinery a skill may run, not procedures a skill follows: §10 governs what a skill may do to claims, this section governs what a system is. A system is subordinate to this file on the same terms as a skill (§0), and holds no element of `graph.json` or `proposals.json`. Every `fleet.campaign` specification lives in this directory. A header outside `systems/` that carries that spec is an orphan and fails E5. The bench store and the trace store do not share a header, an extension, or a query. The harness code under `fleet/` writes both stores and is specified by `systems/read-fleet.md`.

### Terms

`agent.skill`, `fleet.campaign`, `agent.swarm`, and `agent.fleet` are four strings. This contract uses the first as the spec of a procedure and the second as the spec of one run. Retrieved 31 Oct 2026 (Australia/Sydney). The Wikidata items are live entities, pinned by last revision, with no byte hash. Each arXiv row is pinned by versioned id plus the SHA-256 of the PDF bytes downloaded that day from `https://arxiv.org/pdf/<id>`. A quoted sentence was read off that PDF's text layer (`pdftotext -layout`, poppler 24.02.0). The remainder of each paper was not read for this repository. These records describe the ordinary words. They do not replace the sentences below.

**`agent.skill` is a procedure.** It is the spec on every skill in §10. It is not a run. Wikidata `wbsearchentities` for `agent.skill`, language `en`, limit 5, returned an empty `search` array on this retrieval. The ordinary word is [Q205961](https://www.wikidata.org/wiki/Q205961), English label "skill", English description "learned ability and competence to carry out an action", last revision 2541591399, modified 2026-09-07T08:25:55Z.

**`fleet.campaign` is one run.** It is the spec on every system in the table below. The run has one core. `run` is the SHA-256 of that core's bytes. The core carries `bound-n` and `bound-tok`. The run ends on one `halt`. Workers that append bench lines or trace lines are members of that run. Set-union merge with no coordinator is a property of the bench store inside the run. Wikidata `wbsearchentities` for `fleet.campaign`, language `en`, limit 5, returned an empty `search` array on this retrieval.

**`agent.swarm` is not a spec and not a type.** No header in this tree names it as either. A run of this contract is a `fleet.campaign`.

**`agent.fleet` is not a spec and not a type.** The folder sort retired it. A header that carries it fails E5. The name of the run is `fleet.campaign`. The members of that run are its workers. Wikidata `wbsearchentities` for `agent.fleet`, language `en`, limit 10, returned an empty `search` array on this retrieval, the same result as the query for `agent.swarm`.

**One reading in a skill.** "The campaign" names the one `fleet.campaign` run. "Workers" names the members of that run. The phrase "fleet and design architectures" in `skills/design-binder.md` §5 names methods in the literature. It does not name this run.

**The ordinary words sit next to those strings, and they are not the same object.**

- Wikidata [Q529909](https://www.wikidata.org/wiki/Q529909), English label "multi-agent system", English description "built of multiple interacting agents", last revision 2516060604, modified 2026-07-10T21:47:04Z. Instance of [Q96116695](https://www.wikidata.org/wiki/Q96116695) "type of system". Subclass of [Q2429814](https://www.wikidata.org/wiki/Q2429814) "software system". arXiv:2502.14743v2 (Sun, Yang, Duan, Shi, Lyu, Chang, Lin, Shen), byte sha256 `de8fbdff90b586fdd478ef5009e7584a5a1e7d37fd3c15eeab5d66fd495aab8e`. Definition 1, read off that PDF: "The multi-agent system is a system consisting of multiple independent interactive decision makers called agents, where an agent may be a person, a robot, a robotic subsystem, a manipulator's finger, a distributed computing unit, a language model, a satellite, etc."
- Wikidata has no item labelled `agent.swarm`. The nearest item names a behaviour. [Q863960](https://www.wikidata.org/wiki/Q863960), English label "swarm intelligence", English description "collective behavior of decentralized, self-organized systems", last revision 2515886205, modified 2026-07-10T14:01:57Z. Instance of [Q125161275](https://www.wikidata.org/wiki/Q125161275) "type of intelligence", [Q609408](https://www.wikidata.org/wiki/Q609408) "auto-organisation", [Q188961](https://www.wikidata.org/wiki/Q188961) "decentralization", and [Q2548752](https://www.wikidata.org/wiki/Q2548752) "collective behavior". Subclass of [Q83500](https://www.wikidata.org/wiki/Q83500) "intelligence". Facet of [Q17156857](https://www.wikidata.org/wiki/Q17156857) "decentralised system" and of [Q4406838](https://www.wikidata.org/wiki/Q4406838) "self-organizing system". arXiv:2411.11616v2 (Cazenille, Toquebiau, Lobato-Dauzier, Loi, Macabre, Aubert-Kato, Genot, Bredeche), byte sha256 `e5072b74c4a622c95f7996607b3e17b2566dbc248f35dbd854a7836a65fe38bb`. The definition that paper adopts, read off that PDF: "swarm robotics involves deploying robotic agents that coordinate in a decentralized manner to achieve a common goal, with each robot limited to sensing and acting within its immediate environment."
- [Q47311934](https://www.wikidata.org/wiki/Q47311934), English label "fleet", English description "group of vehicles operated by an organization", last revision 2520618032, modified 2026-07-21T11:05:03Z. Subclass of [Q16887380](https://www.wikidata.org/wiki/Q16887380) "group". arXiv:2510.10379v1 (Gupta, Asbery, Merchant, Anwar, Thomason), byte sha256 `e6494d40cf75e7cdc60cd7713960f58e30b515b144b243d580feb690148e79d8`. System Design, read off that PDF: "At its core, the system employs a centralized fleet manager that orchestrates robot operations through a planning and allocation framework."
- [Q831663](https://www.wikidata.org/wiki/Q831663), English label "military campaign", English alias "campaign", English description "large scale, long duration, significant military strategy plan", last revision 2552201427, modified 2026-10-02T15:17:09Z.

A procedure of this contract is an `agent.skill`. A run of this contract is one `fleet.campaign`: one core, one hash, bounds, one halt. Q205961 is a learned ability. Q863960 is collective behaviour of decentralized, self-organized systems, in the item's own spelling. Q47311934 is a group of vehicles operated by an organization. Q831663 is a military campaign. arXiv:2510.10379v1 describes a centralized fleet manager. Those items remain different objects from the procedure and from the run.

| system | what it holds | write scope |
|---|---|---|
| [`systems/use-bench.md`](systems/use-bench.md) | a run-scoped append-only commons where a campaign's workers read and write partial work concurrently | its own `.bench` store only; never `graph.json`, never `proposals.json` |
| [`systems/record-fleet-traces.md`](systems/record-fleet-traces.md) | the act log of one `fleet.campaign` run: pin, call, refusal, proposal, emission, halt | its own `.trace` store only, outside this repository; never `graph.json`, never `proposals.json`, never `.bench` |
| [`systems/read-fleet.md`](systems/read-fleet.md) | the reference harness for one run: preflight, execution of `design-binder`, and the handoff to `--trace` | no file in this repository; `fleet/fleet.py` appends the `.bench` and `.trace` stores the other rows specify, outside this repository |

- A system is not a skill and is not listed in §10. It originates nothing and admits nothing: §4 is untouched by anything written to a scratchpad or an act log, and a record in a `.bench` or `.trace` store is not a claim this file recognises.
- `bench` is scoped to a single run and is discarded with it. It is not a second catalogue, and it is not a cache of `graph.json`.
- Every `.bench` record declares an evidence tier, and no query pools across tiers — the same refusal §2 makes between clinical and preclinical, one layer down. A tier that is declared is not thereby honest; the line can only require the declaration.
- The trace records acts, not evidence. The record has no tier, no study type, and no score. A `.trace` file is not a proposal and is not a bench. It is discarded with the run. The specification is `systems/record-fleet-traces.md`. `verifier/verify.py --trace` decides it. That decision is pure and does not discharge §8.16.
- The rows of this table and the files `systems/*.md` are in bijection. That bijection is extension predicate E4. It is not a §8 predicate and it does not renumber them.
- Three systems, named here exactly. A specification not listed in this section is not part of this contract.
