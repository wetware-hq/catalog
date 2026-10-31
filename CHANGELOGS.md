⚠️ ACADEMIC RESEARCH PURPOSES ONLY; NOT FOR MEDICAL USE WITHOUT LICENSED OVERSIGHT

# changelogs

## 2026-10-31 — minimal stable live fleet

### changed

- Unified all run terminology on `fleet`. `agent.fleet` is the only run unit in the contract; the
  removed alternate label had no production.
- Added `fleet/fleet.py`, a standard-library runner for `design-binder` with budget preflight,
  catalogue and UniProt gates, a required Boltz design gate, a multi-model OpenRouter advisory
  panel, BENCH worker heads, TRACES act logs and final trace verification.
- Added the truthful `design-binder` trace step `generator`, keyed by target. Before this change a
  generator could fail before producing a binder, but the grammar offered only `model`, which
  required a binder key and could not encode that event.
- Materialized a header-only `.bench` file for workers that append no records. An absent worker file
  no longer masquerades as an empty worker head.
- Made truncated or unparseable model output `unavailable`; it is no longer counted as a successful
  answer with zero candidates.
- Enforced the 45–110 residue design brief during candidate admission and corrected post-pin
  `grammar` refusals to use the parent required by the trace judgement.
- Closed trace files with context managers, removing resource warnings from the suite.

### tested

- Added eleven hermetic fleet tests: BENCH content addressing and tier refusal, key and length
  admission, hard developability screens, fenced/truncated JSON, pre-pin refusal, Boltz fail-closed
  behavior, budget preflight, worker-head materialization, and a complete `result` trace.
- Retained all 36 verifier tests and all graph/E1/E2/E4 predicates.
- Added the fleet suite to `.github/workflows/validate.yml` and made `fleet/**` changes trigger CI.
- Ran a six-model live advisory fleet. After tightening the prompt and parser, all six providers
  returned three parseable candidates; no candidate was emitted as a therapy or catalogue row.
- Probed the deployed Modal fleet and launched a 50,000-repeat synthetic sequence-design workload.
- Authenticated the refreshed Boltz workspace key and priced the exact run: USD 0.90 for 18 designs,
  plus USD 0.015582 for the advisory panel, under a USD 2.00 cap. Hosted `boltzprot` completed all
  18 designs without an API error. Eleven passed the local hard developability screen; all 18 passed
  the deployed Modal homology gates against their explicitly synthetic reference fixtures. The
  resulting BENCH/TRACES run decided `result` and emitted zero candidates because the two killing
  assays were not run.

### known limits

- The live Boltz run is prediction, not measurement. It does not discharge paper inclusion,
  binding, selectivity, immunogenicity, developability, safety or patient benefit.
- Modal's shipped human and hazard references are synthetic fixtures, not the human proteome or a
  hazard inventory. Their pass is an integration result only and is not a safety claim.
- BENCH query/index/replication and pose operations remain specifications, not implementations.
- Healthy-tissue expression, paralogue-panel affinity, MHC-II prediction and the two killing assays
  remain required before any candidate may be emitted.
