⚠️ ACADEMIC RESEARCH PURPOSES ONLY; NOT FOR MEDICAL USE WITHOUT LICENSED OVERSIGHT

# run a campaign

`spec: fleet.campaign` · subordinate to `follow-agent-contract.md`, which governs on any conflict.

`fleet.py` is the standard-library reference harness for one `fleet.campaign` run. It executes
`skills/design-binder.md`, writes BENCH and TRACES artifacts outside this repository, and hands the
trace back to `verifier/verify.py --trace`. It declares no `type`: it is not a row of
`follow-agent-contract.md` §0c. The run is the one §11 describes: one core, one hash, bounds, one halt.
`agent.swarm` and `agent.fleet` are not specs. Wikidata Q863960 names collective behaviour of decentralized, self-organized systems, and that item is a different object from this run. The run is the `fleet.campaign` in `follow-agent-contract.md` §11.

## preflight

```bash
python3 fleet/fleet.py preflight \
  --budget-usd 2.00 \
  --target uniprot:P01111 \
  --models vendor/model \
  --candidates 3 \
  --min-aa 45 --max-aa 110 \
  --prompt-tokens 700 --completion-tokens 1400
```

Every flag above is an argument. None of them has a default: a missing bound is a refusal, not a standing policy. The model id is the caller's. Preflight is read-only and submits no compute. It pins `graph.json` at a commit SHA — the checkout's HEAD, never a branch name — checks UniProt and NCBI, authenticates Boltz and Modal, reads the OpenRouter key budget, prices the models named on the command, and returns `launch=false` when any required service is unavailable or the projection crosses the cap. Boltz is required. OpenRouter is an advisory panel and never substitutes for the hosted Boltz design engine. NCBI is probed with a pmid taken from the pinned catalogue. Vendor bases and the Modal app name come from the environment; the harness embeds none.

## run

```bash
python3 fleet/fleet.py run \
  --target uniprot:P01111 \
  --indication "research" \
  --out /tmp/catalog-fleet \
  --models vendor/model \
  --candidates 3 \
  --bound-tok 60000 \
  --max-tokens 2600 \
  --timeout 180 \
  --min-aa 45 --max-aa 110 \
  --live
python3 fleet/fleet.py verify /tmp/catalog-fleet
```

`--min-aa` and `--max-aa` are sent only on the Boltz design request. They are not a grammar gate: `follow-agent-contract.md` §3 bounds the alphabet, not the length. The harness admits the target when UniProt names the organism *Homo sapiens*, pins `graph.json` to the checkout SHA, builds the target reverse index, authenticates and estimates the Boltz request, then fans out the advisory panel. A failed Boltz authentication records `unavailable` with `step:"generator"` and halts before that panel. Candidate sequences are hypotheses; nothing writes `graph.json` or `proposals.json`.

A `grammar` refusal parents the call. For `design-binder`, grammar, species, not-protein, and indication-absent parent the call even when the candidate was produced after the pin (`tracer/record-fleet-traces.md`).

A service failure records the source and the status. It does not record a response body.

`core.trace` and one `<worker>.trace` per worker implement TRACES. `core.bench` and one
`<worker>.bench` per worker implement BENCH; even an empty worker head is represented by a
header-only file. The core bench file is `%bench-core/1`, because its hash is the run id and so
cannot appear inside itself (`systems/use-bench.md`). Every trace is decided at the end of the run.
`result` proves only trace shape, not that an event occurred, not paper inclusion, and not patient benefit.

## tests

```bash
python3 fleet/tests/test_fleet.py
python3 verifier/tests/test_verify.py
python3 verifier/verify.py graph.json --repo .
```

The harness suite is hermetic. It covers content-addressed BENCH lines, tier refusal, binder admission,
the named developability motifs, JSON parsing, pre-pin refusal, Boltz fail-closed behaviour, budget
preflight, full worker-file materialization, and an end-to-end `result` trace with live calls faked.
