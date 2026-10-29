# get_info

Resolve a key in `graph.json` to labels, annotations and linked data.
Derived, never stored. The database holds identity and evidence only.

## Invariants

- NEVER write any output of this procedure back into `graph.json`. Derived means recomputed, every call.
- NEVER report a value a record did not return. No nearest match, no inference, no prose summary of a search result. Unresolvable is `unresolved`, and `unresolved` is a correct answer.
- NEVER use web search. A bare residue string resolves to unrelated documents (measured: a real 40-mer of P04626 returned mouse Fab 1RIV, "not identified").
- Service down or non-200: return `unresolved`, with the status. Do not fall back to another engine.
- Stamp every extrinsic value with its source and the release that answered.

## Intrinsic labels — from the key's bytes, no network, cannot fail

| label | rule |
|---|---|
| tier | `aa:` → PROTEIN. `uniprot:` → PROTEIN. HELM `PEPTIDE` → PROTEIN. HELM `RNA` with `R` sugar → RNA, with `[dR]` → DNA. `CHEM` contributes no tier. Chimera returns the set, not a precedence. |
| length | residue count after the prefix |
| composition | residue frequency |
| polymer type | HELM block names, verbatim |

Compute these first. Most questions end here.

## Extrinsic labels — oracle, dated, may be empty

### Targets (`uniprot:` keys) and any natural sequence

Discovered molecules. A reference proteome contains them, so they always resolve.

1. Fetch the sequence: `https://rest.uniprot.org/uniprotkb/<accession>.fasta`
2. CRC64, **ISO polynomial `0xD800000000000000`**, not the Jones variant most libraries ship. Reflected, init 0, no final xor. Hex, uppercase, 16 digits.
3. `https://rest.uniprot.org/uniparc/search?query=checksum:<CRC64>&format=json`

One hit, deterministic, no alignment. Verified tonight on all 41 landed targets: 41/41 single hit. P04626 → `39E9DFDA04DCF962` → `UPI000003F55F`.

MD5 appears in the record but is not a searchable field. `checksum:` is.

Then read annotations from the UniProtKB entry: gene symbol, protein name, subcellular localisation, and the feature table. Boundaries — signal peptide, propeptide, chain, transmembrane — come back here. They are annotations on a sequence, not part of the identity.

Canonical and mature chain both resolve (P04626 23–1255 → `8AC3B9634520796F` → `UPI0003E74441`). Canonical is far more densely cross-referenced, 818 against 43, so prefer it when either would do.

For a sequence with no accession in hand: ≤30 residues through UniProt/PIR Peptide Match, longer through BLAST at a stated identity threshold reported with the answer.

### Binders (`aa:`, `helm:` keys)

Invented molecules. Nothing in nature carries a therapeutic antibody's CDRs, so a sequence database returns germline immunoglobulin genes — the closest natural thing, which is a miss, not an answer. Do not report it as the drug.

Identity lives in the record that named the molecule:

1. WHO INN lists, which publish full chains beside the name
2. Thera-SAbDab, secondary index for antibodies

No hit in either: `unresolved`. Expected for engineered and grey-market sequences, and correct.

Short peptides fan out — a 9-mer occurs inside many proteins. Return the set, labelled as a set, never one member of it.

## Output

Intrinsic labels, then extrinsic ones with source and release, then `unresolved` for everything that did not resolve. A key with no public identity is a valid key.
