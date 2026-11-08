⚠️ ACADEMIC RESEARCH PURPOSES ONLY; NOT FOR MEDICAL USE WITHOUT LICENSED OVERSIGHT

# catalog

`type: initialization` · non-normative. `docs/follow-agent-contract.md` governs on any conflict.

Route a catalogue task through the smallest sufficient path in the documentation DAG. The normative contract always wins.

## Specification

```json
{
  "id": "docs/read-repository.md",
  "type": "initialization",
  "role": "route tasks through the documentation DAG",
  "reads": ["graph.json", "neighbor Markdown on demand"],
  "writes": [],
  "must": ["load the contract before any procedure", "treat absence as unknown"],
  "check": ["E1", "E6", "E7"]
}
```

## Graph

- → [follow-agent-contract.md](follow-agent-contract.md)

## Composition

```toml
root = "this file"
sink = "systems/run-campaign.md"
stop = "first sufficient route"
```

## Indications

| Task | Minimum read |
|---|---|
| read or rank rows | [`contract`](follow-agent-contract.md) |
| resolve a key | contract → [`resolve-key`](../skills/resolve-key.md) |
| propose a pair | contract → [`resolve-key`](../skills/resolve-key.md) → [`propose-pairs`](../skills/propose-pairs.md) |
| design | contract → [`falsify`](falsify.md) → [`pins`](pin-references.md) → [`design`](../skills/design-binder.md) → [`traces`](../systems/record-traces.md) → [`seal`](../systems/seal-og.md); [`bench`](../systems/use-bench.md) → [`record`](../tmp/record-egfr-calibration.md) → [`run`](../systems/run-campaign.md) |
| falsify | contract → [`falsify`](falsify.md); the runtime is written outside the repository |
| traces | contract + [`traces`](../systems/record-traces.md) → that runtime's trace judgement |

Stop at the row's endpoint. Design continues to the sink.

## Contraindications

- `graph.json` is evidence metadata, not a formulary, prescription, or ranking.
- `pair` and `preclinical` never pool. Absence is not evidence of no binder.
- Automation never discharges §8.16. An unread `pair` hit stops design.
- A collapsed fence stays closed until the route names its label.

## Algorithm

### Variables

```toml
objective = "select the smallest sufficient read-before route"

[independent]
task = "read | resolve | propose | design | falsify"

[dependent]
route = "ordered Markdown path ending at the first sufficient node"

[controlled]
revision = "one pinned repository commit"
contract = "docs/follow-agent-contract.md governs every route"
```

### Process

```csv
operator,law
controls,one pinned commit
design,smallest task row
transport,next neighbor only
stopping,first sufficient node
search,task table match
filters,contract before any procedure
recovery,a refusal returns to the contract
```

```mermaid
stateDiagram-v2
    [*] --> Contract
    Contract --> Read: catalogue query
    Contract --> Resolve: key query
    Resolve --> Propose: intake query
    Contract --> Falsify: falsify query
    Falsify --> Pins: de novo query
    Pins --> Design
    Design --> Trace
    Propose --> Trace
    Contract --> Bench
    Trace --> Seal
    Seal --> Run
    Bench --> Summary
    Summary --> Run
    Read --> [*]
    Propose --> [*]
    Run --> [*]
```

```mermaid
flowchart LR
    Rev[Pin] --> Contract
    Contract --> Next
    Next --> Stop
```

## Citations

| Pin | Supports |
|---|---|
| [CommonMark 0.31.2](https://spec.commonmark.org/0.31.2/) | headings, lists, and links |
| [AgentKit, arXiv:2404.11483v2](https://arxiv.org/abs/2404.11483v2) | dependency DAGs |
| [AGENTS.md `d001185`](https://github.com/agentsmd/agents.md/tree/d001185d792eb6402a58e4cbef1c228b309ec25d) | path-local disclosure |

Retrieved 1 Nov 2026 (Australia/Sydney). Representation only, not catalogue evidence.

## Falsification

| Challenge | Failure signal |
|---|---|
| Delete or reverse one graph edge | E6 rejects the route |
| Skip the contract | the oracle boundary is absent |
| Read a branch twice | bytes can differ |
| Treat a missing row as a negative | the file does not say that |
| Treat one green run as confirmation | a pass is not a contradicting observation |

## Licence

MIT
