# catalog

A **bipartite graph** of biological **binders** and protein **targets**, with PubMed citations that support **clinical benefit** for each binder–target pair.

## `graph.json`

One UTF-8 JSON object at the repo root:

- **`version`** — schema version, currently `1`
- **`pair`** — binder → target → sorted, de-duplicated list of `pmid:<digits>` citations

Keys use `aa:` (canonical L-chain sequences), `helm:` (HELM copied from the source record), and `uniprot:` targets. Only pairs with at least one qualifying PMID are stored.

The catalogue is **protein-only**. Nucleic-acid and small-molecule blocks are not admissible: a key that is not a protein is refused on admission rather than classified.

Nothing else is stored. There is no regulatory-status field, no evidence grades, and no ranks or scores — a binder's sequence and its citations are the whole record, and anything derivable from them is computed at read time.

## Agents

**[AGENTS.md](./AGENTS.md)** is the full contract: schema, key grammar, inclusion rules, canonical serialisation, merge laws, read-time ranking, validation predicates, and the background-update contract. Implement validators and extensions from that file alone.
