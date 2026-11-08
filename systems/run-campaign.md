# run a campaign

`type: agent.system` · `spec: fleet.campaign` · subordinate to `docs/follow-agent-contract.md`, which governs on any conflict.

Specify one bounded design campaign in Markdown, from catalogue gate through positive-control calibration, epitope-conditioned generation, reporting, and trace verification. The caller supplies the target and the model composition. This file names neither, and no repository-local fleet program supplies hidden defaults or request bodies.

## Specification

```json
{
  "id": "systems/run-campaign.md",
  "type": "agent.system",
  "role": "execute one caller-targeted, caller-composed design campaign",
  "reads": ["caller manifest", "pinned graph.json", "caller-supplied structures", "current provider schema"],
  "writes": [".bench and .trace files outside the repository"],
  "must": ["take target and composition from the manifest", "condition on a mapped epitope", "halt when the binding control fails", "keep the fleet image a DAG", "write merkle.trace for the fleet image"],
  "check": ["positive-control verdict", "trace result", "E4", "E5", "E6", "E7"]
}
```

## Graph

- ← [../tmp/record-egfr-calibration.md](../tmp/record-egfr-calibration.md)
- ← [seal-og.md](seal-og.md)

## Composition

```toml
authority = "this Markdown file; no repository-local fleet executable"
inputs = ["target", "model composition"]
phases = ["preflight", "catalogue gate", "target preparation", "positive control", "design", "screen", "verify"]
stores = [".bench", ".trace"]
graph = "Graph section; this file is the sink"
structure = "prolog dag"
image = "agent_fleet"
```

## Indications

- Execute `design-binder` for a caller-supplied admitted human target and explicit indication.
- Run exactly the caller-supplied model composition, after that same composition passes a blinded positive control on a caller-supplied known interface.
- Materialize predictions and acts in disposable BENCH and TRACES stores outside this repository.

## Contraindications

- Do not launch novel-target generation with a missing bound, moving catalogue read, unread `pair` hit, unavailable required service, or failed positive control.
- Do not select a target, a control, a provider, an engine, a length window, or a component list that the manifest did not name.
- Do not send an available structured interface as an unconstrained full-length target. A whole-protein request with no epitope or hotspot restriction is a configuration failure, under whatever field name the provider uses.
- Do not substitute sequence validity, length compliance, structure generation, or any fold or interface-geometry score for the pre-registered primary binding criterion.
- Advisory components may inspect evidence, choose methods, and audit outputs. Text they invent is not a designed sequence. Candidate sequences come only from components whose role is `design`.
- A verified trace proves format, not service execution, molecular binding, safety, paper inclusion, or benefit.

## Algorithm

### Variables

```toml
objective = "recover a known interface before spending on an unknown one"

[independent]
target = "caller-supplied human uniprot:"
indication = "explicit caller input"
model_composition = "caller-supplied components and roles; this file names no provider and no panel"
target_basis = "immutable structure artifact when available, otherwise a documented sequence construct"
epitope = "non-empty mapped target-residue set supplied with the target"
positive_control = "caller-supplied known co-structure, hidden from every design component"
bounds = "spend, tokens, calls, candidates, length, wall time, and iterations"

[dependent]
launch = "true only after preflight, catalogue gate, and positive-control pass"
control_verdict = "pass | positive-control-failed | unavailable"
candidates = "design-component hypotheses that cross the registered binding gate"

[controlled]
catalogue_pin = "40-hex commit SHA; resolve a tag before the run"
provider_request = "priced bytes equal submitted bytes, for every design component"
primary_control_metric = "binding criterion fixed before generation; the manifest names the field"
oracle = "not-discharged"
```

### Process

```mermaid
stateDiagram-v2
    [*] --> Manifest
    Manifest --> Refuse: missing target, composition, epitope, or control bar
    Manifest --> Catalogue
    Catalogue --> Halt: unread or same-indication pair hit
    Catalogue --> PrepareTarget: design is permitted
    PrepareTarget --> Refuse: construct or residue map is invalid
    PrepareTarget --> Calibrate
    Calibrate --> Halt: unavailable or positive-control-failed
    Calibrate --> Design: binding control passes
    Design --> Screen
    Screen --> Materialize
    Materialize --> VerifyTrace
    VerifyTrace --> [*]
    Halt --> VerifyTrace
    Refuse --> VerifyTrace
```

```mermaid
flowchart LR
    Manifest[Manifest] --> Gate[Catalogue gate]
    Gate --> Control[Blinded control]
    Control --> Novel[Novel target]
    Novel --> Trace[Trace check]
```

```csv
operator,law
controls,take target composition epitope and bar from the manifest
design,calibrate that same composition on a blinded known interface
transport,submit only the priced epitope-conditioned request
stopping,halt before novelty when the binding control fails
search,read the provider schema and the pinned reverse index
filters,drop advisory sequences and unconstrained full-length targets
recovery,record unavailable or positive-control and still verify the trace
```

Symbolic reasoning. `type: sandbox.playground`.

```tla
---- MODULE Campaign ----
\* model agent. source of nature.
\* A Lisp variation is a proposal only when this module grounds it.
\* Novel launch requires a passed control and a manifest target.
CONSTANTS control_pass, manifest_target
Launch == control_pass /\ manifest_target
====
```

```lisp
;; write agent. executable image. grounded in the tla module only.
(defun launchp (control-pass manifest-target)
  (and control-pass manifest-target))
```

```lean
-- model agent. forward pass. discharge and refinement check.
-- autoproof: tla source -> lisp image -> Ti -> bend breakpoint -> tla
-- E7 does not compile this fence.
def lispLaunch (control manifest : Bool) : Bool :=
  control && manifest

theorem Ti :
    (lispLaunch false false = false) ∧
    (lispLaunch false true = false) ∧
    (lispLaunch true false = false) ∧
    (lispLaunch true true = true) :=
  And.intro rfl (And.intro rfl (And.intro rfl (rfl)))
```

```bend
# proof agent. backward pass. search under Ti.
# ti_holds is a number. 0 takes the refuse branch.
# breakpoint: launch only after the binding control and a manifest target
# This value is not a .trace file. E7 does not run this fence.
object Trace { name, holds }

def backward(ti_holds):
  if ti_holds:
    return Trace { name: "breakpoint", holds: 1 }
  else:
    return Trace { name: "refuse", holds: 0 }
```

#### Structure image

The phase diagram above is the control flow. The fence below is the membership DAG of one `fleet.campaign`. `core` is the root. `halt` is the end of the run. `worker` is the member role, and the manifest names the heads. `bench` and `trace` are the stores a member appends. `trace` has parents `core` and `worker`. The bench Merkle DAG stays inside the store `bench`. The trace Merkle tree is the ramification of this DAG under [`record-traces.md`](record-traces.md). E7 checks this fence equal to the rendering of `agent.fleet` in `checker literals`. The fence stays outside compression. A fleet program stays outside this repository, and a YAML manifest stays out of this image.

```prolog
image(agent_fleet).
shape(dag).
node(bench).
node(core).
node(halt).
node(trace).
node(worker).
edge(core, halt).
edge(core, trace).
edge(core, worker).
edge(worker, bench).
edge(worker, trace).
```

#### 0. The manifest supplies the target and the composition

The caller supplies a run manifest; the executing agent reads this file at a pinned commit and follows it. There is no repository-local fleet executable, generated configuration module, default target, default model composition, default length range, or vendor request body. A runtime may use any current client or tool that can satisfy the semantics below. It may not weaken them because a provider schema differs, and it may not fill a blank with a target or a component this file once mentioned.

The manifest fixes before any paid call:

| class | required value |
|---|---|
| identity | target key, indication, pinned specification commit, and catalogue revision |
| target | selected construct and canonical sequence map; structure artifact, digest, chain, crop, and structure-residue map when available; epitope residues and any non-binding surface |
| control | caller-supplied co-structure, hidden reference binder, interface-contact rule, primary binding metric, its field name, and its pass bar |
| composition | ordered components; each has role `design` or `advisory`, a provider, an engine and version, a modality, and the fields it may emit |
| binding | for each design component, the dated schema and the request field that carries each invariant, including that schema's index origin |
| bounds | spend, tokens, calls, wall time, polling time, iterations, candidate count, and sequence-length range |
| output | external run directory, BENCH heads, TRACE workers, and assay owners required by `design-binder` |

A missing item is a refusal. Defaults exposed by a provider are copied into the manifest before pricing; an omitted field is not an invisible choice. A provider field name belongs in the manifest after the schema is read. It does not belong in this file.

A component with role `design` may return candidate sequences. It receives the construct and the epitope, and it does not receive the reference binder sequence, the binder chains, or the catalogue answer. A component with role `advisory` may inspect, recommend, or criticize. Any sequence in its text is excluded unread. One design component is a complete composition. Several design components are complete only when each is an independent method or scaffold family and all share the target, epitope, bounds, and gates.

#### 1. Preflight and catalogue gate

Pin `graph.json` to the specification commit or another explicit 40-hex commit SHA. Resolve a tag to that SHA before creating the run core; never put a tag or branch name in the trace. Admit the manifest's target and indication under `skills/design-binder.md`, build the reverse index, and stop on an unread or same-indication `pair` hit before any design call. A different-indication branch opens only after the paper is read. Catalogue absence remains `absent`, never a negative.

For each design component, resolve the current provider schema, authentication, quota, and engine version. Build the complete epitope-conditioned control request, then estimate the exact request that would be submitted. Redact credentials, but retain the request, provider response identifiers, schema retrieval date, and cost estimate in the run report. If estimate and submission differ in any design-bearing field, stop and re-price.

#### 2. Prepare the target construct and epitope

The catalogue key remains the whole `uniprot:` accession named in the manifest. The design target is a documented construct of that protein. When a structure is available, map every selected structure residue back to the canonical sequence, record missing residues and index conventions, and reject ambiguous mappings. Crop to the smallest independently folded construct that contains the intended epitope and required structural context. Without a suitable structure, record the sequence interval and canonical-residue map that define the construct. Do not send signal peptide, transmembrane, cytosolic, or unrelated sequence merely because it occurs under the same accession.

The epitope is non-empty and comes from the manifest:

1. derive its target residues from a pinned co-structure, competition data, or a separately justified hotspot analysis;
2. record the derivation, contact cutoff or other rule, chain, author residue ids, insertion codes, and provider indices;
3. prove every epitope residue lies in the selected construct and no residue also appears in the non-binding set;
4. inspect each materialized design request and fail unless that component will apply those same structural residues. Record the provider's index origin. An unchecked index transform is a refusal, as is an epitope that disappears during client serialization.

Template-free target mode is admissible only when no suitable structure exists and every design component can still encode the mapped epitope. If a component cannot express the required epitope, record `unavailable` for that component; never fall back to unconstrained whole-target design.

#### 3. Calibrate with a blinded positive control

Every design component, modality, target-preparation rule, and scoring configuration in the manifest must first run against the positive control named in the manifest. The control may be the novel target or another admitted target. The caller chooses it before the run. This file does not. Each design component receives the control construct and epitope but not the reference binder sequence, binder chains, or catalogue answer. Use the same candidate count, length window, modality, filters, scoring path, and compute bounds proposed for the novel run. This tests independent recovery of an interface, not sequence rediscovery.

The reference structure shows where to condition. It is not a binder template, and its binder chains stay out of every design request.

The control passes only if at least one candidate from a design component:

- crosses the pre-registered primary binding bar on the field the manifest named;
- satisfies the pre-registered geometric contact rule on the mapped epitope;
- stays inside all sequence, modality, and developability constraints; and
- is not selected by a supporting fold or interface-geometry score in place of either condition above.

A missing primary binding value is not zero and is not a pass; it is `unavailable`. Store each returned field under the name the provider used. Do not rename a missing field onto another score. A completed control with no candidate across the bar is `positive-control-failed`, a specification refusal parented to the catalogue pin. Halt before the novel target and report the composition as uncalibrated. Sequences from a failed control are not emitted and are not seeds for a later request.

Length compliance, an accepted alphabet, and a returned structure establish only that transport and generation worked. They do not establish binding.

#### 4. Generate, screen, and report

Only a passed control opens the novel-target design call, and only for the composition already calibrated. Do not add a component, drop a component, or swap a provider between the control and the novel target. Advisory output may recommend or criticize. Its literal sequences are excluded unread.

Record every returned candidate, not only the apparent winner. Validate the caller's length and alphabet constraints, then preserve each provider's binding and structural metrics as tier-2 predictions in BENCH. Apply `design-binder` stage-one exclusions. The primary binding metric decides whether the control and candidate binding claims survive; supporting metrics diagnose fold and interface geometry but do not overrule it. When prediction alone separates surviving candidates, report them unranked.

The report carries:

- the manifest's target, control, and composition, including every component role;
- the exact redacted control and novel-target requests, response ids, provider and engine versions, prices, and timestamps;
- structure artifact digests, chain and crop choices, both residue-numbering systems, and the mapped epitope;
- every sequence with every returned metric and no silent zero-filling;
- separate operational, fold, interface, and binding verdicts;
- the positive-control result before the novel-target result;
- every refusal and unavailable source;
- the two killing assays and owners required by `design-binder`; and
- BENCH heads, TRACE files, and the final trace judgement.

Every sequence that leaves the run carries the line of `DISCLAIMER` in its own block. No candidate is emitted without both killing assays, regardless of prediction.

#### 5. Materialize and verify

Write `core.bench`, `core.trace`, `merkle.trace`, and one worker head per participating component outside the repository under `systems/use-bench.md` and `systems/record-traces.md`. A failed control records a `refuse` act with gate `positive-control`, then one `halt`; an unavailable provider records `unavailable` at `generator`. The runtime falsifier written from [`docs/falsify.md`](../docs/falsify.md) decides every completed trace. The command below is an example of that program's surface. It is not a path in this repository.

```bash
# Example only. The runtime is written outside this repository.
falsify --trace /path/to/core.trace /path/to/worker.trace
```

This repository ships no unit suite and no committed checker. Repository predicates are that same runtime program reading the contract. There is intentionally no fleet-runtime unit suite: the runtime is this Markdown contract, and provider execution is evidenced by its materialized requests, responses, control result, and trace rather than by mocks of a removed hardcoded client.

## Citations

| Pin | Claim used | Boundary |
|---|---|---|
| [Overath et al., bioRxiv v2](https://doi.org/10.1101/2025.08.14.670059) | interface-focused metrics and operating-point performance vary strongly by target, so no score in this file is a universal binding bar | unrefereed; no substitute for the manifest's registered criterion |
| [`pin-references.md` row 9](../docs/pin-references.md) | exact extraction, metric reads, and uncertainty limits | no clinical outcome and no named target or engine |

## Falsification

| Challenge | Expected break |
|---|---|
| omit the target, the composition, the epitope, or the binding bar | preflight refuses before pricing |
| insert a target, provider, engine, or component this file does not contain | the manifest is no longer the caller's |
| send an available structured interface as an unconstrained full-length target | preflight refuses before pricing |
| omit or ambiguously map one epitope residue | target preparation refuses |
| let serialization drop the epitope, under any field name | materialized-request audit fails |
| leave a provider's index origin unchecked | materialized-request audit fails |
| pass the control on length, structure generation, or any fold or interface-geometry score | verdict remains `positive-control-failed` |
| cross the binding bar but miss the mapped epitope | positive control fails |
| give a design component the reference binder sequence or binder chains | the control is no longer blind |
| accept a sequence from an advisory component | the sequence is excluded unread |
| change the composition between the control and the novel target | novel-target generation does not start |
| emit or reseed any sequence from a failed control | positive control stays failed and no binder is emitted |
| add a repository-local fleet executable or hidden default | Markdown ceases to be the sole runtime authority |
| replace the membership DAG, give `trace` one parent, or wrap the fence | E7 |
| preserve trace shape while faking provider calls | trace may be `result`, exposing why requests and control outputs must also be retained |
| Remove the Campaign playground or launch with the control false | E7, and Launch stays the control plus the manifest |

The strongest break remains experimental: failure of the measured binding assay or binding to the pre-registered counter-screen panel kills the hypothesis even after a calibrated computational run.

## Licence

MIT
