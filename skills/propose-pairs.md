⚠️ ACADEMIC RESEARCH PURPOSES ONLY; NOT FOR MEDICAL USE WITHOUT LICENSED OVERSIGHT

# `propose-pairs` — catalogue intake

`type: resource.procedure` · `spec: agent.skill` · subordinate to `docs/follow-agent-contract.md`, which governs on any conflict.

Enumerate structured authorities, resolve complete protein triples, and append unclassified candidates to `proposals.json`. This procedure never writes `graph.json` or chooses a clinical versus preclinical study type.

## Specification

```json
{
  "id": "skills/propose-pairs.md",
  "type": "resource.procedure",
  "role": "prepare evidence candidates for human admission",
  "reads": ["structured authorities", "pinned graph.json", "existing proposals.json"],
  "writes": ["proposals.json"],
  "must": ["emit complete triples only", "never classify study type", "never write graph.json"],
  "check": ["recall 1.0", "zero false-admits", "E2", "E5", "E6", "E7"]
}
```

## Graph

- → [../systems/record-traces.md](../systems/record-traces.md)
- ← [resolve-key.md](resolve-key.md)

## Composition

```toml
steps = ["admit", "resolve payload", "resolve binder", "resolve target", "deduplicate"]
output = "proposals.json"
graph = "Graph section"
```

## Indications

- Prepare machine-resolved triples for later paper review.
- Re-run intake against a pinned catalogue to measure recall.
- Record explicit refusal counts for incomplete or out-of-scope candidates.

## Contraindications

- Do not crawl prose, infer sequences from names, use approximate matches, or admit a row from metadata alone.
- Do not classify `pair` versus `preclinical`; that choice is the paper-reading oracle.
- Do not use DrugBank without re-checking its licence after the dated refusal below.
- Do not store scores, names, indications, doses, labels, or regulatory status.

## Algorithm

### Variables

```toml
objective = "recall committed rows while counting false admissions"

[independent]
record = "structured authority row"
catalogue = "graph.json pinned to a commit SHA"

[dependent]
proposal = "binder, target, pmid"
refusal = "first failed intake step"

[controlled]
serializer = "contract section 5"
merge = "contract section 6 and add-only predicate 19"
drugbank = "refused; licence re-check dated 2026-10-29"
```

### Process

```mermaid
flowchart TD
    E[Enumerate structured records] --> A{Admitted protein payload?}
    A -->|no| R[Record refusal]
    A -->|yes| B[Resolve binder]
    B --> T[Resolve target]
    T --> P[Resolve PMID]
    P --> D{Duplicate?}
    D -->|yes| R
    D -->|no| W[Single-writer append]
    W --> V[Read back at commit SHA]
```

### 0. Objective

Propose `(binder, target)` pairs for `graph.json` by writing them to `proposals.json`. **This procedure never writes `graph.json`**, on any branch (`docs/follow-agent-contract.md` §9). A candidate qualifies when **all** hold:

- binder and target are both **biological** and both **protein** (`docs/follow-agent-contract.md` §3, §8.8);
- the binder resolves to a canonical amino-acid sequence;
- the target resolves to a UniProt accession;
- at least one PubMed identifier reports utility for **that pair**.

The study-type classification — `pair` versus `preclinical` — is **not yours to make**. It requires reading the paper, and the reader who makes it is the one who moves the row into `graph.json`.

### 1. Non-goals

- **Do not crawl prose.** Free-text web search does not resolve binders: it returns the name without the sequence and silently substitutes near-matches (observed once, 2026-10-29: a search on a real human 40-mer returned a non-human Fab). Enumerate records; a page that asserts a pair without a resolvable sequence is not a candidate.
- **Do not use DrugBank.** Its licence was non-commercial when checked on 2026-10-29, which makes it inadmissible for this repository at any scale. That is an external fact with a date on it: re-check the licence before treating the refusal as permanent, and do not relax it without re-checking.
- Do not write ranks, scores, grades, names, labels, indications, doses or regulatory status. They are not in the schema.
- Do not widen the key grammar to admit a molecule you could not resolve. An unresolvable candidate is **dropped**, not approximated.

### 2. Sources

Enumerate structured authorities and follow their cross-references. The reachable universe is bounded and already recorded; the work is resolution, not discovery.

- **UniProt / UniParc** — target accessions; binder sequence identity by CRC64 (ISO polynomial `0xD800000000000000`) against the `checksum:` field.
- **ChEMBL** — binder–target activity records, with PubMed cross-references.
- **Thera-SAbDab** — therapeutic antibody sequences and their targets.
- **PubMed / Europe PMC** — existence and well-formedness of the citation. Reading it is the admitting reader's step, not yours.

A source that answers with an error, a timeout, or a rate limit yields **`unavailable`**: retry it, cache nothing, and never record its silence as a negative. A source that answers and holds no match yields **`unresolved`**: that is a final, cacheable answer about the record.

### 3. Per-candidate record

A candidate is emitted only with all three fields present; a missing field is a drop, never a placeholder.

| field | content |
|---|---|
| `binder` | `aa:` or `helm:` key, canonical per `docs/follow-agent-contract.md` §3, admission-gated per `docs/follow-agent-contract.md` §8.8 |
| `target` | `uniprot:` accession |
| `pmid` | one `pmid:<digits>` |

Store the **canonical** sequence, not the mature chain. Snapshot 2026-10-29 by catalog-systems against the live UniParc service, not reproducible from this checkout: of 33 mature chains, 6 did not resolve at all, and cross-reference collapse put 16 of 27 under 50 residues against canonical ranges — on that evidence a mature-chain key is both less resolvable and silently different from the molecule the record describes.

### 4. Decision procedure

Per candidate, in order. Stop at the first refusal and record which step refused.

1. **Admit gate.** `aa:` / `uniprot:` / HELM in which **every** block is `PEPTIDE` and at least one exists → continue. Anything else → **refuse: out of scope**, unexamined. Do not classify what you can refuse by namespace.
2. **Payload.** Monomers are standard residues or bracketed symbols from the 32-token protein monomer set. A SMILES fragment such as `[CCO]` inside `PEPTIDE1{…}` → **refuse: illegal payload**. This is a different refusal from step 1 and must stay distinguishable; a `d`-prefixed token is a **D-stereoisomer**, never a deoxy sugar.
3. **Resolve binder.** Sequence → CRC64 → UniParc. Batch accessions: in one timing run on 2026-10-29 (catalog-systems, one network path, not reproducible from this checkout) 307 lookups in one call took 35 s against 103 s for 41 single lookups. Batch because the ratio is large, not because of those seconds.
4. **Resolve target.** Accession must exist and be a protein.
5. **Duplicate check.** The triple must not already exist in either dictionary of `graph.json`, nor in `proposals.json`; the molecule must not already exist under a different binder key (`docs/follow-agent-contract.md` §8.13).

### 5. Write protocol

- **`proposals.json` only.** Never write `graph.json`, on any branch. A branch is a mutable name with no merge law for trust: fencing unverified rows behind a branch dissolves at the first merge and relaunders them as read-verified. A file boundary survives every merge, because `proposals.json` merges into `proposals.json`.
- **One serialiser.** Workers emit candidates; a single writer applies them. A file is one path and a path is not a merge law — concurrent writers to the same path lose rows silently.
- Apply candidates with the `docs/follow-agent-contract.md` §6 merge law, which is commutative, associative and idempotent, so a re-run of an overlapping batch is safe.
- Re-serialise per `docs/follow-agent-contract.md` §5 before committing. Never hand-edit the serialised file.
- Add-only (`docs/follow-agent-contract.md` §8.19): no existing proposal is removed or rewritten; removal happens only when a reader admits the row into `graph.json`.
- Verify the committed bytes by reading them back **through the API pinned to the commit SHA**. CDN mirrors serve stale content and will show you your own intent instead of the file.

### 6. Acceptance

A run that cannot reproduce what is already trusted does not get to extend it.

1. **Recall.** Point the criteria at the committed catalogue. A run must rediscover every pair already in it. Report the fraction; below 1.0, fix resolution before adding rows.
2. **False-admit rate.** Of the rows a run would write, the fraction a curator rejects. Report it as a number. Above zero, the oracle step is being manufactured rather than performed, and that is the cost of the gate being skipped.
3. **Refusal ledger.** Count refusals by step (1–5). A step that never fires is untested, not satisfied.

### 7. What a run does not discharge

Condition 16 is an **oracle** predicate: that a paper reports utility for a pair, and in which direction, is not decidable from bytes, from a record, or from a crawl. A passing run proves the pure conditions and nothing more. State what you verified, name what you did not, and leave the claim to the reader who moves the row into `graph.json`. Nothing this procedure writes is ever read as a catalogue.

## Citations

| Source | Use | Pinning note |
|---|---|---|
| [UniProt REST API](https://www.uniprot.org/help/api_queries) | protein accessions and sequence identity | live service; record release and retrieval |
| [ChEMBL web services](https://chembl.gitbook.io/chembl-interface-documentation/web-services) | structured activity and document records | record API release and query |
| [Thera-SAbDab](https://opig.stats.ox.ac.uk/webapps/sabdab-sabpred/therasabdab/) | therapeutic antibody sequences and targets | live database; snapshot outputs |
| [NCBI E-utilities](https://www.ncbi.nlm.nih.gov/books/NBK25501/) | PubMed identifier resolution | metadata does not establish paper content |
| [DrugBank licence](https://go.drugbank.com/legal/academic_license) | dated exclusion check | re-check before changing the 29 Oct 2026 refusal |
| [`follow-agent-contract.md`](../docs/follow-agent-contract.md) | grammar, proposal schema, and oracle boundary | repository commit is the governing pin |

## Falsification

| Challenge | Failure signal |
|---|---|
| Replay against committed catalogue | recall below `1.0` |
| Curator rejects one emitted row before paper classification | false-admit rate above zero |
| Remove `pmid`, binder, or target | candidate must be dropped, never padded |
| Put `[CCO]` in a `PEPTIDE` block | distinct `illegal-payload` refusal |
| Return 429 from one authority | `unavailable`, with no cached negative |
| Run two writers against one proposals path | lost update demonstrates the single-writer requirement |
| Assign `pair` during intake | procedure has crossed predicate 16 without reading the paper |

The refusal ledger must exercise every decision step; a gate with count zero is untested rather than satisfied.

## Licence

MIT
