# get-info

Resolve a database key to labels. Read-only. Never writes.

Scope: protein only. The catalogue holds protein binders and protein targets.
Nucleic-acid rows are out of scope and are refused at the door, never classified.

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

No tier is computed and none is stored. A key is an admissible protein or it is refused.

## Stage 0 - intrinsic

```
admit : Key -> { length, composition, shape } | refused
total. no network. never fails. intrinsic: reads the bytes, needs no library and no date.

ns, body = split(Key, ':', 1)
    ns == "aa"                      -> assert body subset_of PROTEIN_MONOMERS ; admit
    ns == "helm", all blocks PEPTIDE-> assert monomers(body) subset_of PROTEIN_MONOMERS ; admit
    ns == "uniprot", body matches AGENTS §3 accession grammar -> admit
    otherwise                       -> refuse (out of scope or ungrammatical)

refuse is not a classification. an RNA or DNA block is refused unexamined;
nothing downstream ever sees a non-protein key. the refusal is recorded.

grammar is checked HERE, never at resolve. an ungrammatical accession makes the
service answer 400: not unresolved (no record answered) and not unavailable (the
service did answer). admitting it would force a third verdict. refusing it keeps
stage 1 two-valued.

PROTEIN_MONOMERS is one flat set. one block type, one alphabet, no per-block scoping.
    d-prefixed tokens are D-stereoisomers, never deoxy: dA is D-alanine, dR is D-arginine.
    with nucleic acids out of scope there is no second reading of d left to disambiguate.

alphabet : refuse-if-illegal. never classify.
    a letter test decides nothing about what a molecule is; it can only reject a
    payload whose characters fall outside PROTEIN_MONOMERS.

ascii : every byte of every Key <= 0x7F, no BOM.
    assertion over existing bytes, never a re-serialization.
    a non-ASCII byte in a key is a wrong row, not lint: return it to verification.
    closes homoglyph duplication (Cyrillic A != Latin A, identical on screen, two keys).

vectors:
    admit  : helm:PEPTIDE1{A.dR.G}$$$$          -> admitted
    refuse : helm:RNA1{R(A)P}$$$$               -> refused, out of scope
    refuse : helm:PEPTIDE1{[CCO]}$$$$           -> refused, monomer outside PROTEIN_MONOMERS
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
    verified 2026-10-29: 41/41 canonical keys -> exactly one UniParc entry.
    hit  : P04626 canonical 1255 aa -> 39E9DFDA04DCF962 -> UPI000003F55F
    miss : P04626 canonical, residue 100 R->A -> 08E37566D061ED3B -> zero hits -> unresolved
           (one letter from a real protein: proves the lookup is exact, not approximate)
    |hit| > 1 -> unresolved. more than one answer is not an answer.
    5xx / 429 -> unavailable. cache nothing. retry.
    MD5 is published in the record and is NOT searchable. use CRC64.

    canonical is the stored string. a mature chain is a different string with its own
    UPI: measured 2026-10-29, 27 of 33 mature chains resolve and 6 do not
    (P08069 P25092 P31358 P40238 P41180 Q02643), and no property of the key tells you
    which. cross-references collapse under maturation (canonical 54-1426, mature 1-336,
    16 of 27 under 50), so a mature UPI keeps resolution and loses corroboration.
    store canonical; any future sequence commit declares its boundary explicitly.

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

A test vector proves a step is specified, not that it is right.
