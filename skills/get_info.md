# get_info

Resolve a database key to labels. Read-only. Never writes.

## Folder contract (all skills here)

Notation: one per folder. Blocks below are formal algorithms, not sample programs.

```
skill   : input -> output | failure
total   : every input returns; no undefined case
pure    : output depends on input + named release only
no-write: output goes to the caller, never into the database
```

## Types

```
Key       = "aa:" Residues | "helm:" Helm | "uniprot:" Accession
Identity  = { accession | inn_name , source , release , retrieved }
Failure   = unresolved        -- record answered, says nothing. final. cacheable.
          | unavailable       -- service did not answer. nothing learned. retry. cache nothing.
```

`unresolved` and `unavailable` are never merged. One value for both writes outages into the catalogue as findings.

## Stage 0 - intrinsic

```
intrinsic : Key -> { tier, length, composition, shape }
total. no network. never fails.

tier <- namespace, sole source:
    aa:      -> PROTEIN
    helm:    -> first polymer block TYPE:
                   PEPTIDE        -> PROTEIN
                   RNA, R(..)     -> RNA
                   RNA, [dR](..)  -> DNA
                   CHEM           -> no tier
    chimera  -> the SET of tiers. never a precedence.

alphabet : refuse-if-illegal. never classify.
    no residue letter distinguishes a tier: A/C/G/T/U are also Ala/Cys/Gly/Thr/Sec,
    and O is Pyl. a letter test cannot decide tier; it can only reject a payload
    whose characters fall outside the declared tier's monomer set.

ascii : every byte of every Key <= 0x7F, no BOM.
    assertion over existing bytes, never a re-serialization.
    a non-ASCII byte in a key is a wrong row, not lint: return it to verification.
    closes homoglyph duplication (Cyrillic A != Latin A, identical on screen, two keys).
```

## Stage 1 - resolve

```
resolve : Key -> Identity | unresolved | unavailable
total. deterministic. no free-text search. single path, never fanned out.

uniprot: / discovered sequence
    crc64 <- CRC64, ISO polynomial 0xD800000000000000   (NOT the Jones variant)
    GET https://rest.uniprot.org/uniparc/search?query=checksum:<crc64>
    GET https://rest.uniprot.org/uniprotkb/<accession>
    exact lookup. no alignment. no search engine.
    verified 2026-10-29: 41/41 keys -> exactly one UniParc entry.
    check case: P04626 canonical 1255 aa -> 39E9DFDA04DCF962 -> UPI000003F55F
                mature chain 23-1255 1233 aa -> 8AC3B9634520796F -> UPI0003E74441
    MD5 is published in the record and is NOT searchable. use CRC64.

aa: / helm: invented molecule (therapeutic antibody, de novo binder)
    UNMEASURED. no route specified. return unresolved.
    candidate authorities, untested as of 2026-10-29: WHO INN records, Thera-SAbDab.
    do not substitute an endpoint.

shard unit: a BATCH of keys, never one key per worker.
    measured 2026-10-29: 41 single lookups = 103 s; 307 accessions batched = 35 s.
```

## Stage 2 - enrich

```
enrich : Identity -> Findings        -- note the domain: Identity, NOT Key
fleet / swarm. open. parallel. no coordinator. no shared mutable state.

stage 1 returning unresolved HALTS enrichment for that key. fail-closed.
no worker may put residues into a search. a real 40-mer of P04626 returned an
unrelated mouse Fab (PDB 1RIV), engine verdict "not identified".

merge law: UNION with per-worker attribution. never a vote, never a collapse to
one value. N workers reading one page are not N confirmations.

every finding carries source + release + retrieved. nothing a page merely said.
rate limit: honour the service's published limit; a throttled swarm returns
unavailable, never unresolved.
```

## Not derivable

A citation is not recoverable from residues. Names are derivable; evidence is not. `pmid:` stays stored in the database.
