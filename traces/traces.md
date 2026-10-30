⚠️ ACADEMIC RESEARCH PURPOSES ONLY; NOT FOR MEDICAL USE WITHOUT LICENSED OVERSIGHT

**Licensed oversight is required for any use of this system; none has been performed to date.**

# `TRACES` — the execution record of one fleet run

`type: resource.system` · `spec: agent.fleet` · subordinate to `AGENTS.md`, which governs on any conflict (`AGENTS.md` §0).

TRACES is the act log of one `agent.fleet` run. It records what the run did — a pin, a call, a refusal, a proposal, an emission, a halt — so a later reader can reconstruct the gate curve of that run. **Nothing written here is a claim about a molecule, and nothing here is admissible to `graph.json` or to `proposals.json`.**

## 0. Scope

- **Read:** this file, `AGENTS.md`, the run's own `.trace` files.
- **Write:** `.trace` files inside a run directory, which lives outside this repository.
- **Refuse:** `graph.json`, `proposals.json`, every `.bench` file, and every file in this repository. TRACES ships no program, no package manifest, no workflow and no data file here. Its presence in the repository is this specification only.

The tracer is §5. Any `agent.fleet` run emits it by appending lines. A run that produces no trace is not a run this system recognises.

`systems/` and `traces/` are both systems (`AGENTS.md` §11). They do not share a header, a file extension, or a query. A skill may use either; neither discharges §4, and neither widens `AGENTS.md` §0.

## 1. Objective

Two quantities, both decided by the grammar rather than by an implementer's taste.

**Format freedom** is the number of format decisions a conforming emitter still makes on a legal line. The minimum this record can reach without going silent is **1**: the worker filename (§3). Act names, field sets, field order, parent pointers, quoting, identifiers, the study-type slot, and every score slot are fixed or absent. That count is the engineering idiot index of the format. An implementation that adds a decision the grammar does not have produces a line §5 does not admit.

**Gate coverage** is how much of the result curve in §7 a head satisfies. The curve is the ordered list R1–R10. The maximum is the whole curve: a head on which every condition holds is a **result**, and any other head is **partial**. The receiver names the first failing condition. It does not emit a fraction, an area, a rank, or a utility. A single area under that curve would be a grade of the run, and a grade is the failure this file exists to keep out of the record.

The curve is a record of gates. It is not clinical benefit. `skills/design-binder.md` states that no computable score for clinical utility exists. [`references.md`](../references.md) row 9 measures binding assays, rejects the area under an ROC curve for that data, and still says nothing about patients. A trace that stored such an area would manufacture the oracle `AGENTS.md` §8.16 reserves for a reader. The clinical utility this system can actually maximise is reconstructability of the gates a licensed reader needs: which bytes were pinned, which procedure ran, which refusal fired, which triple was proposed with no study type attached, which hypothesis left with its disclaimer, and the explicit statement that the run did not discharge the oracle.

## 2. Why this is not BENCH

BENCH (`systems/bench.md`) holds tiered claims about the world. A trace holds acts of a run. An act is not a measurement, a prediction, or an experimental result, and giving it a tier would make a log line look like evidence. The two stores therefore have different headers (`%trace/` does not parse as `%bench/`), different extensions, and no operation that copies a node from one into the other.

A number that belongs to the world — an affinity, a pose, a Kd, a model score — has no field here. If a run needs to keep one, that is a BENCH record with its tier, in the bench store. The trace records the gate that fired.

## 3. Structure and merge

A run directory holds `core.trace` and one `<worker>.trace` per worker. `<worker>` matches `^[a-z][a-z0-9-]{0,31}$`. Files are append-only, UTF-8, LF. Each line ends in one `\n`, the file ends on that newline, and no line has a trailing space. Invalid UTF-8 is rejected. A byte sequence is never repaired with U+FFFD (`AGENTS.md` §5).

Each worker file is a header plus immutable lines. A line's identifier is SHA-256 over its preimage (§5), 64 lowercase hex digits, with no shorter prefix accepted. Identical bytes are one node. Parent identifiers point at a line whose own identifier was fixed first, or at `^0` for the core alone, so the graph is acyclic. There is no total order and no "latest". A date on an `unresolved` or `unavailable` line is the UTC calendar day of the attempt, not a sequence number.

Merge is set union of **admitted** nodes (§5). It is associative, commutative, and idempotent, for the same reason BENCH's merge is: the identifier is a function of the bytes. A line the receiver does not admit is not in the union. Out-of-order arrival waits; it does not create a placeholder.

What converges is the head. What does not converge is a prose summary of the head. A result is the head that satisfies §7, reported with the core hash. An answer without that hash is not a result.

## 4. The core

`core.trace` is written once, before any worker starts, and has no writer afterward.

```
%trace-core/1
bound-n:"<positive integer>"
bound-tok:"<positive integer>"
skill:"<skill>"
spec:"<40 lowercase hex>"
```

The four fields are required, in that order, which is key order. A positive integer matches `[1-9][0-9]*` — no sign, no leading zero, not zero. `skill` is `resolve-key`, `propose-pairs`, or `design-binder`, the names in `AGENTS.md` §10 and no synonym. `spec` is the git commit of this repository that the run pinned. A branch name has no production: a branch tip moves, and a trace that names one cannot be reread (`AGENTS.md` §7).

`run` is SHA-256 of those exact bytes, header included, one trailing newline included. One changed byte is a different run. Bounds live in the core so a halt cannot invent a tighter cap at the end, and so a run cannot start without a pre-registered stop (`skills/design-binder.md`: quiescence is not a stopping condition; `systems/bench.md` §10.2).

Every line carries `run` and `skill` inside the bytes its identifier covers. A line cannot be moved to another run or another procedure without changing its identifier. The receiver checks both against the core. That check is load-bearing: a sender-side promise is not a check.

## 5. Tracer

The tracer is these two functions. They are the whole implementation surface. No library is part of the contract.

```
emit(act, fields) -> line | refused
admit(line, core) -> node | refused
```

`emit` appends. `admit` is the receiver and is the only way a line enters a head. A line the receiver refuses stays in the sender's file and is not in the receiver's head.

### 5.1 Wire

```
header  = "%trace/1 core=" run " spec=" gitsha NL
line    = act SP id SP parents SP "run=" run SP "skill=" skill [ SP field { SP field } ] NL
field   = key ":" quoted
quoted  = '"' chars '"'
parents = "^0" | "^" id
```

`act`, `skill`, and `key` are tokens from the tables below. `chars` is a non-empty UTF-8 string of at most 1024 bytes containing no `"` and no ASCII control. `id` is 64 lowercase hex. `gitsha` on the header equals the core's `spec`. Keys on a line are in ascending byte order, one space between tokens, no trailing space.

The **preimage** is the line with the `id` token removed and without the newline. `id` is SHA-256 of the preimage's UTF-8 bytes. `admit` recomputes it and refuses a mismatch. Extra keys, missing keys, a wrong parent, an unknown act, a value outside its production: the same refusal.

`call` has no fields. Its preimage is `call ^0 run=<run> skill=<skill>` and is a function of the core alone, so every worker that emits it writes one node.

### 5.2 Values

| production | accepts |
|---|---|
| `int` | positive integer as in §4 |
| `git` | 40 lowercase hex digits |
| `path` | the characters `graph.json` only |
| `oracle` | the characters `not-discharged` only |
| `kind` | the characters `hypothesis` only |
| `disclaimer` | the banner on the first line of this file, byte-identical |
| `binder` | an `aa:` or `helm:` key that `AGENTS.md` §3, §8.7 and §8.8 accept |
| `target` | a `uniprot:` key that `AGENTS.md` §3 accepts |
| `pmid` | a `pmid:` citation that `AGENTS.md` §3 accepts |
| `key` | a `binder` or a `target`, as the act's step requires |
| `token64` | `[A-Za-z0-9._:/-]{1,64}` |
| `day` | a real Gregorian calendar date `YYYY-MM-DD`, the UTC day, no zone suffix |
| `subject` | `chars`, or exactly `unencodable`, or exactly `unquotable` |

`unencodable` is the subject when the offending input is not valid UTF-8. `unquotable` is the subject when it contains `"`, a newline, or an ASCII control. No other substitute is legal, and U+FFFD is never written. `binder`, `target`, `pmid`, and `key` are checked by the predicates in `AGENTS.md`. This file does not restate them. `subject` is not a key: it exists to carry the bytes that failed, and §3 is not applied to it.

There is no production for a dictionary name, a tier, a rank, a grade, a score, an AUC, a utility, a Kd, or a pose. Those words are not banned by a denylist that an implementer must remember. They fail because they are not in the field set of any act.

### 5.3 Acts

Parents are exact. The first matching row wins. A parent id that is not yet in the head waits; any other parent string is refused.

| line | parent |
|---|---|
| `call` | `^0` |
| `pin` | `^` plus the call id |
| `resolve-key`, every non-call line | `^` plus the call id |
| `design-binder` pre-pin `refuse` | `^` plus the call id |
| `design-binder` `halt` on a head that has no pin | `^` plus the call id |
| every remaining line | `^` plus the pin id |

| act | skills | fields, exact set |
|---|---|---|
| `call` | all three | (none) |
| `pin` | `propose-pairs`, `design-binder` | `path`, `rev` |
| `refuse` | all three | `gate`, `subject` |
| `unresolved` | all three | `key`, `source`, `release`, `retrieved`, `step` |
| `unavailable` | all three | `key`, `source`, `release`, `retrieved`, `step` |
| `propose` | `propose-pairs` | `binder`, `target`, `pmid` |
| `context` | `design-binder` | see §5.4 |
| `emit` | `design-binder` | `binder`, `target`, `kind`, `disclaimer` |
| `halt` | all three | `bound-n`, `bound-tok`, `oracle` |

`path` is `path`. `rev` is `git`: the commit the catalogue was read at, not a SHA-256 of the file. `bound-n` and `bound-tok` are `int` and equal the core. `oracle` is `oracle`. `kind` is `kind`. `disclaimer` is `disclaimer`. `source` and `release` are `token64`, and `release` may be the token `unspecified` when the service publishes none. `retrieved` is `day`. `step` is a token from §5.5.

`unresolved` and `unavailable` are different acts. One act for both is how an outage becomes a finding (`skills/resolve-key.md`).

A `propose` line carries no study type. `pair` versus `preclinical` is chosen when a reader reads the paper (`AGENTS.md` §9.4), and a trace that could say it would be doing that job. The halt's oracle token is the only grammatical statement of §8.16 available on a line, and the only value is `not-discharged`. A run cannot seal itself as having read the papers.

An `emit` line is a hypothesis. The disclaimer sits inside the hashed bytes, so deleting it or rewording it yields a different identifier and `admit` refuses the stripped line. The unit of copy is the whole line. A binder value lifted out of it is not a trace record and has dropped the warning `skills/design-binder.md` §7 requires on the same block as the sequence.

### 5.4 `context`

The field set is `verdict`, `gloss`, and the other fields named in that row, and nothing else. `gloss` is the token in the row and no other.

| `verdict` | `gloss` | other fields |
|---|---|---|
| `hit-same-indication` | `stop` | `target`, `binder`, `pmid` |
| `hit-other-indication` | `transfers-not` | `target`, `binder`, `pmid` |
| `absent` | `not-a-negative` | `target` only, besides `verdict` and `gloss` |

`absent` means no qualifying paper is entered. The gloss is the only legal wording of that fact, because catalogue absence is not a negative (`AGENTS.md` §7). The indication text is not a field. `AGENTS.md` §2 gives it nowhere to live, and a trace is not a side channel for it. The `pmid` on a hit row is the paper the indication was read from.

### 5.5 Gates and steps

`gate` is one token from the skill's row. `step` is one token from the skill's row.

| skill | `refuse` gates | `step` |
|---|---|---|
| `resolve-key` | `grammar`, `scope`, `ascii` | `resolve` |
| `propose-pairs` | `out-of-scope`, `illegal-payload`, `duplicate-triple`, `duplicate-molecule` | `3`, `4` |
| `design-binder` | `grammar`, `species`, `not-protein`, `indication-absent`, `selectivity`, `immunogenicity`, `developability`, `no-assay` | `catalogue`, `model` |

Pre-pin gates for `design-binder` are `grammar`, `species`, `not-protein`, `indication-absent`. Those refusals parent the call. The other four parent the pin. `propose-pairs` refusals all parent the pin: the catalogue pin is part of that procedure even when every candidate dies at the first gate.

On `design-binder`, step `catalogue` requires a `target` key, and step `model` requires a `binder` key. On `resolve-key`, `key` is whatever §3 key was looked up. On `propose-pairs`, step `3` is the binder lookup and step `4` is the target lookup (`skills/propose-pairs.md` §4).

Screen names record which gate fired. They do not record the affinity, the count, or the bar. Those numbers are not acts.

## 6. Admissibility

A trace is not a proposal file and is not opened as one. `propose-pairs` writes `proposals.json` by its own protocol. Drift between a `propose` line and that file is visible to a reader and is not repaired here. The §6 merge of the catalogue does not read `.trace` bytes.

An `emit` line is a de novo sequence with no paper. It is ineligible for `graph.json` and for `proposals.json` on the same grounds as the skill that emits it (`AGENTS.md` §10, `class: special`). A tier-shaped reading of a trace is a reading of the wrong system (§2).

A fact enters the catalogue only by the ordinary route: a paper exists, `propose-pairs` proposes it, a reader admits it.

## 7. Result

The receiver evaluates the merged head in order and stops at the first failure. Partial output is the condition id. Result output is the word `result` and the core hash. No coverage fraction is printed.

1. **R1.** The core matches §4, and `run` equals SHA-256 of its bytes.
2. **R2.** Every admitted line carries that `run` and the core's `skill`.
3. **R3.** Every worker header matches §5.1 for that core.
4. **R4.** The head contains exactly one `call`, and it is the call line of this core.
5. **R5.** The head contains exactly one `halt`; bounds equal the core; `oracle` is `not-discharged`; its parent is the pin id if the head contains a pin, otherwise the call id.
6. **R6.** Every parent id other than `^0` is itself in the head.
7. **R7.** Every line's act is legal for the skill, and its parent follows §5.3.
8. **R8.** Every value matches §5.2. Binder, target, pmid, and key are refused exactly where `AGENTS.md` refuses them.
9. **R9.** Across `propose` lines, no two binders are one molecule under `AGENTS.md` §8.13.
10. **R10.** The skill's shape holds.

**`propose-pairs`.** Exactly one `pin`, parent the call, `path` = `graph.json`, `rev` 40 lowercase hex. Every other non-call line parents that pin. Gates and steps are from the `propose-pairs` row of §5.5. No `context` line and no `emit` line.

**`resolve-key`.** No `pin`, no `propose`, no `context`, no `emit`. Every non-call line parents the call. Gates and steps are from the `resolve-key` row.

**`design-binder`.** Either the head has no pin, or it has exactly one.

- No pin: at least one pre-pin `refuse`, no `context`, no `emit`, halt parents the call, every other line parents the call.
- One pin: exactly one `context`, parent the pin; halt parents the pin; every `emit` and every post-pin `refuse` parents the pin. A `verdict` of `hit-same-indication` has zero `emit` lines. Each `emit` has `kind` `hypothesis` and the disclaimer. Steps follow §5.5, including the key-shape rule.

Lines stay in the head when R9 or R10 fails. The store does not delete. The head is partial, and partial is not a result.

The receiver does not open `graph.json` and does not fetch `rev`. A reader who has the pinned blob may compare its git id to `rev`. That comparison is the reader's, and a missing blob is not a failed trace.

## 8. Language

The trace language is the preimage in §5. The question of a host language is closed inside this repository.

Rust is refused inside this repository. A crate needs a package manifest, which `AGENTS.md` §0 refuses, and a program beside this file would be a second statement of the same rules. The second statement is where they diverge. Agents that cannot run the binary would log in prose, and a prose log is a dialect that admits the fields §5.2 has no production for.

Outside this repository, a host language is conforming exactly when `admit` accepts its bytes and §7 is what it computes. No language is preferred. A preferred language becomes the implementation agents without it will imitate badly.

## 9. Worked example

Illustration only. The `spec` and the pin `rev` are forty `a`s and forty `b`s so nobody can mistake them for a pin of this repository. The `propose` triple is a grammar fixture (`aa:ACD`, `uniprot:P12345`, `pmid:1`), not a claim that a paper reports benefit. Recomputation: SHA-256 of the core bytes below is `run`, and SHA-256 of a line with its second token removed is that line's `id`.

`core.trace`:

```
%trace-core/1
bound-n:"1"
bound-tok:"8000"
skill:"propose-pairs"
spec:"aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"
```

`run` = `d2066050893688b4fc69def4b3c03ffa9ee8b06ef14858786224a7adf2684853`.

`a1.trace`:

```
%trace/1 core=d2066050893688b4fc69def4b3c03ffa9ee8b06ef14858786224a7adf2684853 spec=aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa
call 82d0bb98077f59cb3544536e2023d4cf99699408e57250de2ce20d3e0b20a294 ^0 run=d2066050893688b4fc69def4b3c03ffa9ee8b06ef14858786224a7adf2684853 skill=propose-pairs
pin 2f3f7335675c72766882db3b0dea24b20818183f1934fd10eb131a10ba13fba4 ^82d0bb98077f59cb3544536e2023d4cf99699408e57250de2ce20d3e0b20a294 run=d2066050893688b4fc69def4b3c03ffa9ee8b06ef14858786224a7adf2684853 skill=propose-pairs path:"graph.json" rev:"bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb"
refuse 4d25814dcfdc011016c4c4126bb3a220e4a69e52d7517a9d7b395a8c7d40dfbe ^2f3f7335675c72766882db3b0dea24b20818183f1934fd10eb131a10ba13fba4 run=d2066050893688b4fc69def4b3c03ffa9ee8b06ef14858786224a7adf2684853 skill=propose-pairs gate:"illegal-payload" subject:"helm:PEPTIDE1{[CCO]}$$$$"
propose 179014b62688af1357af3e8dad3f4dd0fcf0e4675426115a52390b8e02ae4b46 ^2f3f7335675c72766882db3b0dea24b20818183f1934fd10eb131a10ba13fba4 run=d2066050893688b4fc69def4b3c03ffa9ee8b06ef14858786224a7adf2684853 skill=propose-pairs binder:"aa:ACD" pmid:"pmid:1" target:"uniprot:P12345"
halt 9d2001abc00391ea2c66714740c2ba9ec5c279405495498f51a72db31be4d6a3 ^2f3f7335675c72766882db3b0dea24b20818183f1934fd10eb131a10ba13fba4 run=d2066050893688b4fc69def4b3c03ffa9ee8b06ef14858786224a7adf2684853 skill=propose-pairs bound-n:"1" bound-tok:"8000" oracle:"not-discharged"
```

One call, fixed by the core. One pin of `graph.json`. One payload refusal, parented to that pin, carrying the offending HELM as `subject` so it is not admitted as a binder. One proposal with no dictionary field. One halt that can say only `not-discharged`. A second worker appending the same `call` line adds no node.

## 10. Known weaknesses

1. **A legal line can be false.** The grammar fixes the shape of an act. It cannot make the act one the worker performed, and it cannot see a propose the worker never wrote. R1–R10 holding is internal consistency of the head, not a witness that the paper was read or that the service was called.
2. **Format freedom is 1, not 0.** The worker filename is chosen. It is constrained by §3 and it is not hashed into the line, so two filenames with the same bytes are one head. A filename outside the grammar is not a trace file.
3. **`unencodable` and `unquotable` drop the offending bytes.** The alternatives reintroduce an escape language.
4. **A missing sibling is invisible.** The receiver knows the control lines (call, pin, halt, context) by their counts. It does not know how many candidates the run should have had. Recall against the catalogue is the skill's acceptance test (`skills/propose-pairs.md` §6), not a field here.
5. **The store grows for the life of the run and is then discarded.** There is no compaction that preserves "a dropped line is still readable" inside the run. Discarding the directory at the end is the collection. Keeping it would make it a second catalogue.
6. **No concurrency proof is claimed.** The merge is set union of content-addressed lines, argued from the same three laws as BENCH, and it has not been model-checked in this repository. Nothing in §7 was executed here: this checkout contains no tracer program (§0, §8).
7. **Gate coverage is not patient benefit.** A `result` on a design run means a hypothesis was emitted with its disclaimer, or was refused at a named gate, under a pinned spec. It does not mean the hypothesis will help anyone.

## 11. Status

Design, **not implemented**. No code in this repository emits a line or evaluates R1–R10, and no implementation is proposed here (§0, §8).
