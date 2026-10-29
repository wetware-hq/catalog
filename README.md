# catalog

A **bipartite graph** of biological **binders** and protein **targets**, with PubMed citations that support **clinical benefit** for each binder–target pair, plus a regulatory **status** per binder.

## `graph.json`

One UTF-8 JSON object at the repo root:

- **`pair`** — binder → target → sorted, de-duplicated list of `pmid:<digits>` citations
- **`status`** — binder → `approved`, `investigational`, or `unapproved`

Empty catalogue today: `{"pair":{},"status":{}}`.

Keys use `aa:` (canonical peptide chains), `helm:` (HELM from source), and `uniprot:` targets. Only pairs with at least one qualifying PMID are stored.

## Agents

**[AGENTS.md](./AGENTS.md)** is the full contract: schema, key grammar, inclusion rules, canonical serialisation, merge laws, read-time ranking, validation predicates, and the background-update contract. Implement validators and extensions from that file alone.
