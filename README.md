# catalog graph

Canonical data lives in **`graph.json`** at the repo root: three dictionaries `{ pair, status, ref }`.

## Canonical serialization

- Top-level keys are exactly `pair`, `status`, and `ref`, in that order in the on-disk file.
- Every object key at every level is sorted lexicographically.
- Each citation list in `pair` is deduplicated and sorted lexicographically.
- No trailing whitespace on any line; the file ends with a single trailing newline.

Validate with:

```bash
node src/check.js graph.json
```

## Key grammar

| Role | Prefix | Form |
|------|--------|------|
| Binder | `aa:` | Canonical L-amino acid chains (uppercase one-letter codes). Multi-chain binders: sort chain strings lexicographically and join with `/`. |
| Binder | `helm:` | Modified peptides: HELM string verbatim from ChEMBL (non-whitespace payload after `helm:`). |
| Target | `uniprot:` | UniProt accession. |
| Citation | `pmid:` or `doi:` | PubMed id or DOI. |

Every binder in `pair` must appear in `status`. Every citation in `pair` must appear in `ref`.

## Evidence grades (`ref` values)

Strongest to weakest:

`meta` > `rct` > `trial` > `observational` > `case` > `animal` > `in_vitro` > `claim`

## Regulatory status (`status` values)

`approved`, `investigational`, or `unapproved`.
