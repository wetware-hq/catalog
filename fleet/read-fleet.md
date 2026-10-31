⚠️ ACADEMIC RESEARCH PURPOSES ONLY; NOT FOR MEDICAL USE WITHOUT LICENSED OVERSIGHT

# run a fleet

`fleet.py` is the standard-library reference harness for one `agent.fleet` run. It executes
`skills/design-binder.md`, writes BENCH and TRACES artifacts outside this repository, and hands the
trace back to `verifier/verify.py --trace`.

## preflight

```bash
python3 fleet/fleet.py preflight --budget-usd 2.00
```

Preflight is read-only and submits no compute. It pins the catalogue, checks UniProt and NCBI,
authenticates Boltz and Modal, reads the OpenRouter key budget, prices the configured model panel,
and returns `launch=false` when any required service is unavailable or the projection crosses the
cap. Boltz is required: OpenRouter is an advisory multi-model panel and never substitutes for the
hosted Boltz design engine.

## run

```bash
python3 fleet/fleet.py run \
  --target uniprot:Q9NZQ7 \
  --indication "non-small cell lung carcinoma" \
  --out /tmp/catalog-fleet \
  --live
python3 fleet/fleet.py verify /tmp/catalog-fleet
```

The harness admits the human protein through UniProt, pins `graph.json` to a Git commit, builds the
target reverse index, authenticates and estimates the exact Boltz design request, then fans out the
advisory panel. A failed Boltz authentication records `unavailable step:"generator"` and halts before
that panel. Candidate sequences are hypotheses; nothing writes `graph.json` or `proposals.json`.

`core.trace` and one `<worker>.trace` per worker implement TRACES. `core.bench` and one
`<worker>.bench` per worker implement BENCH; even an empty worker head is represented by a
header-only file. Every trace is decided at the end of the run. `result` proves only trace shape,
not that an event occurred, not paper inclusion, and not patient benefit.

## tests

```bash
python3 fleet/tests/test_fleet.py
python3 verifier/tests/test_verify.py
python3 verifier/verify.py graph.json --repo .
```

The fleet suite is hermetic. It covers content-addressed BENCH lines, tier refusal, binder admission,
hard developability screens, JSON parsing, pre-pin refusal, Boltz fail-closed behavior, budget
preflight, full worker-file materialization, and an end-to-end `result` trace with live calls faked.
