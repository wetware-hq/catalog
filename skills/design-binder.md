⚠️ ACADEMIC RESEARCH PURPOSES ONLY; NOT FOR MEDICAL USE WITHOUT LICENSED OVERSIGHT

# `design-binder` — de novo binder design

`type: agent.skill` · `class: special` · `spec: agent.fleet` · subordinate to `AGENTS.md`, which governs on any conflict.

**This is not a catalogue procedure.** It needs no directory of its own: it writes nothing (§1), so there is no output boundary left to erode — the same contract `resolve-key` already has.

The other two procedures here are **conservative**: `resolve-key` and `propose-pairs` only relocate facts that already exist somewhere — a key's names, a paper's pair. Neither ever manufactures a claim, and the worst either can do is produce a wrong row. This one **originates**: it creates a sequence no source has ever reported and asserts it might bind. Its worst failure is not a wrong row; it is someone treating a hypothesis as a therapy. That asymmetry is the whole reason for the `special` class.

It writes no file in this repository and its output can never become a row (§1). Its oracle is a wet-lab measurement, not a read paper. Read §1 before running it.

A binder this procedure returns is a hypothesis, not a therapy, and carries no evidence of benefit, safety or activity in any system. **Nothing this procedure returns has been shown to help anyone.**

## 0. Objective

Given a **native human protein target** and a **clinical or research indication**, design candidate synthetic binders, rank them, and return the **single best candidate**.

Input: `(uniprot:<accession>, indication)`. Output: one binder key — `aa:` or `helm:`, canonical per §3 — with the design rationale that produced it.

## 1. Write scope: none

**This procedure writes nothing in this repository.** Not `graph.json`, not `proposals.json`, on any branch.

The reason is structural, not a restriction to be relaxed later. `graph.json` admits a pair only when a paper reports benefit for that pair (§4), and `proposals.json` requires a `pmid` on every element (§9.4). A de novo design has **no paper**, so there is no element of either file it could legally occupy. A designed binder becomes catalogue-eligible only by the ordinary route: someone runs the experiment, someone publishes it, and a reader admits the row. Design is upstream of intake, and `propose-pairs` — not this procedure — is the entry point when that paper exists.

Returning the candidate to the requester is the whole output. A run that wrote a row would be asserting evidence it does not have.

## 2. Specification

The query carries three things. Only the first is a key.

- **Target** — `uniprot:` accession, admitted per §3 below.
- **Indication** — clinical or research. It is **not** stored anywhere and must not be: `AGENTS.md` §2 fixes the root to exactly `version`, `pair` and `preclinical`, and an indication field would have no merge law. It lives in the query.
- **Target expression in healthy tissue** — recorded with the query, because on-target off-tissue toxicity is the usual clinical killer and it is a property of the **target**, not of the binder. No design fixes it. A target expressed widely in healthy tissue constrains or refuses the brief before any sequence exists.

**Both kill conditions are pre-registered here, before the swarm runs.** They are **defaults in this file**, not parameters a run chooses. A run may override one, and then the report states the override and its reason — a run that loosened the selectivity window says so out loud instead of starting from blank. Thresholds supplied per run are the same refitting hole one level up. Kill conditions chosen while holding a candidate get fitted to it — the panel quietly becomes the one it does not cross-react with — and a screen fitted after the fact screens nothing.

- **Paralogue panel.** Every human protein at or above 30% identity to the target over the domain carrying the epitope; at or above 50%, the counter-screen is mandatory rather than optional. Fixed by the threshold, never hand-picked per target.
- **Healthy-tissue bar.** The target is disqualified outright where protein-level expression is medium or high in myocardium, lung alveolar epithelium or haematopoietic progenitors, and in CNS where the construct is designed to cross. Overridable by the indication only, and the override is written down with its reason.

These are conventions from developability and selectivity practice, **not cutoffs validated against patient outcome**. They exclude what is predictably unsafe or undevelopable. None of them predicts clinical benefit.

## 3. Target admission

Refuse before designing, naming the condition that failed:

- Target key fails §3 → refuse (grammar).
- Accession is **not the human protein** → refuse (scope). `AGENTS.md` §8.9 accepts any valid accession, including an ortholog; this procedure does not. A mouse surrogate is a different key and fragments coverage of the human target it stands in for. One accession, one species, and here it is *Homo sapiens*.
- Target is not a protein → refuse (§3, §8.8). Nucleic acids and small molecules are out of scope by design.
- Indication absent → refuse. It is not stored anywhere, and it is not decoration: it sets the required modality, route, residence time and off-target tolerance, which select the scaffold in §4.

## 4. Look it up before designing it

**Design does not fire until the catalogue has been asked and has come back empty for this target in this indication.** A swarm invented to find a molecule for a target that already has one sitting in the file is pure waste.

Build the reverse index for the target per §7 — pin the read to a commit SHA or tag, never a branch name.

- **Any hit, and the gate is indication-aware.** The reverse index answers *some binder helped patients against this target*, not *against this target in this indication*. An evidenced anti-HER2 binder says nothing about anti-HER2 in a different disease or population. The indication is not in the file, so read the pair's PMID and take it from the paper — the same oracle step this skill needs anyway. Hit in this indication: **report the evidenced binder and stop.** That is the answer, and it is a better one than any design.
- **Hit in a different indication:** design may fire, and the report must name the evidenced binder, its indication, and why it does not transfer.
- **No hit:** design fires, but a target with no evidenced binder is **not** open ground. **Absence is not a negative** (§7): it means no qualifying paper has been entered. At present coverage it says nothing about whether a binder exists.
- `uniprot:` cannot express an epitope. Two binders against distinct sites on one protein collapse to one target key, so the catalogue cannot tell you which site is taken. Resolve the epitope from structure, not from this file.

## 5. Design

Fan out a swarm of scientist agents over the design space in parallel, each carrying the same specification — target, epitope, indication-derived constraints — and reporting candidates in a common schema. Breadth is the point: independent scaffolds and independent methods, so the ranking in §5 compares genuinely different hypotheses rather than variations of one.

Scaffold follows the indication, never the other way round. Minibinders and designed miniproteins, nanobodies and single-domain formats, constrained peptides and macrocycles, designed ankyrin and other repeat proteins, and conventional Fv-derived formats are all admissible; a molecule needing non-standard residues, terminal caps or an explicit disulfide pattern must be written `helm:` (§3, §8.8), and one expressible as plain L-chains must be written `aa:` (§8.13c).

Every candidate is carried as its **sequence**. A design has no name to drift, which is why the catalogue's sequence-keying costs this procedure nothing.

### Method selection — `EVOLVE`

The design methods are not fixed in this file, because they move faster than it does. Before fanning out, the swarm reads the current state of the art and chooses from it, under three constraints.

**Read the benchmark, and pin it.** Check current swarm and design architectures against the primary literature — arXiv and equivalent preprint and journal records — and the standing benchmarks those methods are scored on. A SOTA claim read at runtime is a **dated measurement, not a standing fact**: the same query two days apart returns a different answer. So the benchmark read is pinned exactly as the catalogue read is pinned to a SHA (§4), and the report's `generator` field records which benchmark, which version, which numbers and which date chose the method. A method selected from an unrecorded read is unreproducible, and a run nobody can reproduce is not a result.

**Name the axes before using the word frontier.** A Pareto frontier is meaningless without its axes. Here they are, at most: benchmark performance on the published task, compute and token cost per candidate, and wall-clock latency. **Cheapest-first — surface the Pareto-minimal solution before spending anything beyond it.** If the cheapest method on the frontier already meets the benchmark the brief requires, the run stops there and reports it; the expensive end of the frontier is entered only when the cheap end has been tried and has failed against a stated bar.

**No clinical axis exists.** Benchmarks score structure and affinity prediction. Not one of them scores patient benefit, so no point on this frontier is closer to clinical utility than any other, and the frontier must never be reported as though it were. Where a brief names a clinical benchmark, it is a benchmark of a *prediction*, and the report labels it so.

**Token-efficiency is a stopping rule, not a style.** The §4 lookup gate is the largest saving available and runs first. Within a run: breadth buys independent hypotheses and nothing else, so the swarm fans out once over genuinely distinct scaffolds and methods rather than iterating variations, and a candidate excluded by a stage-one screen (§6) is dropped immediately rather than carried, re-scored or argued with.

**The auto-loop needs a stopping condition or it is a hypothesis pump.** Looping `EVOLVE` is admissible only with all of: a bar stated before the loop starts, in the axes above; a bounded iteration count and token budget; and a requirement that each iteration either crosses the bar or names what it learned that changed the next one. A loop that generates candidates at zero marginal cost and never terminates is the cheapest possible way to look productive, and every candidate it emits still owes §7 two killing assays and somebody who could run them. That obligation, not the loop, is what bounds this procedure.

## 6. Screen, then order

Two stages, and they are different operations. The ordering is **computed per run and never stored** (§7), and it is **not** the catalogue's ordering: §7 ranks evidenced binders by citation count within one dictionary, and a designed candidate and a `pair` row are no more comparable than a `preclinical` row and a `pair` row.

**Stage one — hard screens. They exclude; they never penalise.** A candidate failing one is out, and the report names the screen.

- **Selectivity.** Exclude unless predicted or measured affinity for every panel member is at least two logs weaker than for the target. A 10-fold window is not a window.
- **Immunogenicity.** Count promiscuous predicted MHC-II binders — peptides in the top 2% against a common DRB1 allele panel that hit three or more alleles — over non-germline regions only, and exclude above the count seen in marketed therapeutic antibodies. **This is the weakest screen and is reported as such:** prediction here is poor, and the real readout is an anti-drug antibody assay.
- **Developability.** Exclude on any of: an unpaired cysteine, an N-glycosylation sequon in a CDR, Asn-Gly or Asp-Pro in a CDR, or a hydrophobic patch score above the approved-antibody range.

A weighted sum cannot do this job: a total can be high for the wrong reason, and a liability that kills a molecule does not trade off against affinity.

**Stage two — order the survivors, and name the scorer.** No candidate is called best without the computable quantity that chose it stated outright, with its value and its uncertainty: predicted binding free energy or interface score, structural confidence, agreement between independent predictors. Every signal is labelled **prediction** or **measurement**.

**There is no computable score for clinical utility.** Affinity, developability and epitope content are computable, and not one of them predicts patient benefit. That is the oracle, and no swarm closes it. Where the top two are separated only by prediction, the honest output is **unranked candidates**, not a confident first place; a run returning a #1 with no stated scorer is manufacturing the oracle step.

## 7. Output

Report, and write nothing. A single binder is emitted only when §6 earns it, and then it is labelled **by the criterion that chose it**, never as *best*.

**The disclaimer travels with the sequence.** The report carries the canonical line verbatim on the same block as every binder key it hands back, not once at the top. A warning works only at the point of harm, and the thing that causes harm is the sequence, which exists to leave this repository and land on a bench. Nothing validates a report, so the obligation lives here: a warning that does not survive a copy-paste of the sequence protects nobody.

| field | content |
|---|---|
| binder | one `aa:` or `helm:` key, canonical per §3 |
| target | the `uniprot:` key as admitted in §2 |
| scaffold | the format chosen, and the indication constraint that chose it |
| rationale | epitope, design method, and why this candidate beat the runner-up |
| evidence | each ranking signal, labelled prediction or measurement |
| screens | each stage-one screen and its result, including for excluded candidates |
| scorer | the quantity that produced the order, with values and uncertainty |
| expected success rate | the median expected success rate for the scorer used, at the thresholds **as the source labels them**, with any internal inconsistency in the source flagged rather than resolved, and the pre-selection bias of the benchmark targets noted beside it. This replaces a bare confidence score: "what fraction of what I order will bind" is the question a bench campaign actually asks, and every discriminator number is a proxy for it. |
| killing assays | **two**, with thresholds and who could run each. A binding assay kills the affinity claim with a measured Kd. A counter-screen against the pre-registered paralogue panel and the healthy-tissue expression bar kills the safety claim even when the Kd is perfect — a binder that binds beautifully and also binds something in the myocardium is the failure mode that reaches patients. |
| generator | what produced the sequence, standing in for the citation it does not have: the run, the design and scoring models with versions, the inputs, the date, and the catalogue PMIDs that justified choosing this target |
| catalogue context | evidenced binders against this target at the pinned SHA with the indication read from each paper, or the explicit statement that none are entered and that this is not a negative |

Two refusals, two verdicts, as §7 requires them kept apart: a source that does not answer yields `unavailable` — retry, cache nothing; a specification admitting no candidate yields no binder and names the constraint that emptied the space. Neither is catalogue absence, and neither is reported as a resolve failure.

Nobody in this room can run a binding assay. So the output is a **worklist for an experiment**, not a database, and a candidate without both named assays, their thresholds, and somebody who could run them is not emitted at all — a hypothesis accumulated at zero cost is the cheapest way to look productive. That obligation is what makes the output falsifiable, and it is why nothing persists here: a worklist belongs where the experiment is run.

## 8. Acceptance

This procedure asserts nothing about patients and is therefore not acceptance-tested by rediscovery, as `propose-pairs` is. It passes when, for a target whose evidenced binders are already in `graph.json`, a run that is **blind to those rows** returns a candidate engaging the same epitope by an independent route. That is a test of the design process, not of the catalogue, and failing it bars no row — it tells you the ranking in §5 is not yet measuring what it claims to.
