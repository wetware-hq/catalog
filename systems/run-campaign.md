⚠️ ACADEMIC RESEARCH PURPOSES ONLY; NOT FOR MEDICAL USE WITHOUT LICENSED OVERSIGHT

# run a campaign

`type: agent.system` · `spec: fleet.campaign` · subordinate to `docs/follow-agent-contract.md`, which governs on any conflict.

`fleet/fleet.py` is the standard-library reference harness for one `fleet.campaign` run. It executes
`skills/design-binder.md`, writes BENCH and TRACES artifacts outside this repository, and hands the
trace back to `verifier/verify.py --trace`. The code stays under `fleet/`. This file is the
specification of that harness and a row of `docs/follow-agent-contract.md` §11. The run is one core,
one hash, bounds, one halt.
`agent.swarm` and `agent.fleet` are not specs. Wikidata Q863960 names collective behaviour of decentralized, self-organized systems, and that item is a different object from this run. The run is the `fleet.campaign` in `docs/follow-agent-contract.md` §11. Re-checked 1 Nov 2026 (Australia/Sydney): arXiv:2502.14743 was still v2, arXiv:2411.11616 was still v2, and arXiv:2510.10379 was still v1, and the PDF byte hashes matched §11. Workers in this harness do not read one another's bench lines. The swarm paper is about agents that learn from local messages. The fleet-manager paper keeps allocating work after a plan exists. A `pair` hit ends this run before Boltz and before the advisory panel.

## Document graph

- ← [systems/record-traces.md](record-traces.md)

## Specification card

| role | does | reads | writes | must | check |
|---|---|---|---|---|---|
| campaign system | preflight and run `design-binder` | bounds; pinned catalogue; services | `.bench`, `.trace` outside repo | catalogue hit stops before spend | fleet tests; trace `result` |

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

`--min-aa` and `--max-aa` are sent only on the Boltz design request. They are not a grammar gate: `docs/follow-agent-contract.md` §3 bounds the alphabet, not the length. The harness admits the target when UniProt names the organism *Homo sapiens* and pins `graph.json` to the checkout SHA. It builds the target reverse index. If `pair` has any binder for that target, the context verdict is `hit-unread` and the run halts. The paper was not read, so the harness does not record `hit-same-indication` or `hit-other-indication`, and it does not call Boltz or the advisory panel. The context line carries the §7 rank winner and that binder's first `pmid`. The report lists every `pair` row in that order, and any `preclinical` rows under `preclinical_rows`. If `pair` has no binder for the target, the context verdict is `absent`. Only then does the harness authenticate and estimate the Boltz request and fan out the advisory panel. A failed Boltz authentication records `unavailable` with `step:"generator"` and halts before that panel. Candidate sequences are hypotheses; nothing writes `graph.json` or `proposals.json`.

A `grammar` refusal parents the call. For `design-binder`, grammar, species, not-protein, and indication-absent parent the call even when the candidate was produced after the pin (`systems/record-traces.md`).

A service failure records the source and the status. It does not record a response body.

`core.trace` and one `<worker>.trace` per worker implement TRACES. `core.bench` and one
`<worker>.bench` per worker implement BENCH; even an empty worker head is represented by a
header-only file. The core bench file is `%bench-core/1`, because its hash is the bench-store id and so
cannot appear inside itself (`systems/use-bench.md`). The campaign id is the hash of `core.trace`. The bench
core records that hash as `trace`. Every trace is decided at the end of the run.
`result` proves only trace shape, not that an event occurred, not paper inclusion, and not patient benefit.

## tests

```bash
python3 fleet/tests/test_fleet.py
python3 verifier/tests/test_verify.py
python3 verifier/verify.py graph.json --repo .
```

The harness suite is hermetic. It covers content-addressed BENCH lines, tier refusal, binder admission,
the named developability motifs, JSON parsing, pre-pin refusal, Boltz fail-closed behaviour, budget
preflight, full worker-file materialization, an unread `pair` hit that halts before Boltz and before
the advisory panel, and an end-to-end `result` trace with live calls faked.
