⚠️ ACADEMIC RESEARCH PURPOSES ONLY; NOT FOR MEDICAL USE WITHOUT LICENSED OVERSIGHT

**Licensed oversight is required for any use of this system; none has been performed to date.**

# `TRACES` — formal system

`type: resource.system` · `spec: agent.fleet` · subordinate to `follow-agent-contract.md`, which governs on any conflict (`follow-agent-contract.md` §0).

A trace is an act log of one `agent.fleet` run. This file is a formal system: a language, carrier sets written out as literals, total functions, and judgements. The checker `verifier/verify.py --trace` is the transcription of those judgements. It decides them from bytes. It does not discharge `follow-agent-contract.md` §8.16.

```
Freedom  = 1
Coverage = Result
```

`Freedom` is the number of format parameters a legal line leaves open. The one parameter is the worker basename. `Coverage` is the judgement `Result`. There is no term for an area, a rank, a grade, a score, a tier, a study type, or a utility. Those strings are not field names.

## 0. Language

Terminals are UTF-8. A file that is not valid UTF-8, or that contains `U+0000` or `CR`, has no derivation. No byte is rewritten as `U+FFFD`.

```
CoreFile   = "%trace-core/1" NL
             "bound-n:" Q(Int) NL
             "bound-tok:" Q(Int) NL
             "skill:" Q(Skill) NL
             "spec:" Q(Hex40) NL
WorkerFile = Header { Line }
Header     = "%trace/1 core=" Hex64 " spec=" Hex40 NL
Line       = Act SP Id SP Parent SP "run=" Hex64 SP "skill=" Skill [ SP Field { SP Field } ] NL
Field      = Key ":" Q(Chars)
Parent     = "^0" | "^" Hex64
Q(x)       = '"' x '"'
NL = "\n"    SP = " "
```

`Id` is `Hex64`. Keys on a `Line` occur in ascending byte order. A file ends on the `NL` of its last line and does not end on `NL NL`.

```
Hex64 = 64 * HexDig
Hex40 = 40 * HexDig
HexDig = "0" … "9" | "a" … "f"
Int    = "1" … "9" { "0" … "9" }
Skill  = "resolve-key" | "propose-pairs" | "design-binder"
Act    = "call" | "pin" | "refuse" | "unresolved" | "unavailable"
       | "propose" | "context" | "emit" | "halt"
Key    = Lower { Lower | Digit | "-" }
Worker = Lower { Lower | Digit | "-" }        length 1..32
```

`Chars` is a non-empty UTF-8 string of at most 4096 bytes containing no `"` and no ASCII control (`U+0000`–`U+001F`, `U+007F`). `Subject` is `Chars` of at most 1024 bytes, or the literal `unencodable`, or the literal `unquotable`.

The preimage of a line is that line with the `Id` token and the final `NL` removed. `H` is SHA-256, 64 lowercase hex digits, of the UTF-8 preimage. `run` is `H` of the core file's exact bytes.

## 1. Carrier sets

Hard-coded. A token outside its set has no production.

```
Acts(resolve-key)    = { call, refuse, unresolved, unavailable, halt }
Acts(propose-pairs)  = { call, pin, refuse, unresolved, unavailable, propose, halt }
Acts(design-binder)  = { call, pin, context, refuse, unresolved, unavailable, emit, halt }

Gates(resolve-key)   = { grammar, scope, ascii }
Gates(propose-pairs) = { out-of-scope, illegal-payload, duplicate-triple, duplicate-molecule }
Gates(design-binder) = { grammar, species, not-protein, indication-absent,
                         selectivity, immunogenicity, developability, no-assay }
PrePin               = { grammar, species, not-protein, indication-absent }

Steps(resolve-key)   = { resolve }
Steps(propose-pairs) = { 3, 4 }
Steps(design-binder) = { catalogue, generator, model }

Path                 = { graph.json }
Oracle               = { not-discharged }
Kind                 = { hypothesis }
Disclaimer           = the first non-blank line of this file, byte-identical

Fields(call)        = ( )
Fields(pin)         = ( path, rev )
Fields(refuse)      = ( gate, subject )
Fields(unresolved)  = ( key, release, retrieved, source, step )
Fields(unavailable) = ( key, release, retrieved, source, step )
Fields(propose)     = ( binder, pmid, target )
Fields(emit)        = ( binder, disclaimer, kind, target )
Fields(halt)        = ( bound-n, bound-tok, oracle )

Context(hit-same-indication)  = gloss stop
                                fields ( binder, gloss, pmid, target, verdict )
Context(hit-other-indication) = gloss transfers-not
                                fields ( binder, gloss, pmid, target, verdict )
Context(absent)               = gloss not-a-negative
                                fields ( gloss, target, verdict )
```

Field tuples are the sorted key order. `gloss` and `verdict` are members of the row they are written on and of no other row.

`binder` holds iff the value satisfies `follow-agent-contract.md` §8.7 and §8.8. `target` holds iff it satisfies §8.9. `pmid` holds iff it satisfies §8.10. The checker calls those predicates. It does not restate them. `subject` is not sent through them.

```
key(propose-pairs, 3)          = binder
key(propose-pairs, 4)          = target
key(design-binder, catalogue)  = target
key(design-binder, generator)  = target
key(design-binder, model)      = binder
key(resolve-key, resolve)      = binder ∨ target
```

`source` and `release` match `[A-Za-z0-9._:/-]{1,64}`. `release` may be the literal `unspecified`. `retrieved` is a real Gregorian date `YYYY-MM-DD`, the UTC day, with no zone suffix. `rev` is `Hex40`. `bound-n` and `bound-tok` are `Int` and equal the core.

## 2. Functions

Total. The first matching clause wins.

```
callId(C) = H( "call ^0 run=" run(C) " skill=" skill(C) )

parent(C, ℓ, H) =
    act(ℓ) = call                                          → ^0                          (P1)
    act(ℓ) = pin                                           → ^ callId(C)                 (P2)
    skill(C) = resolve-key                                 → ^ callId(C)                 (P3)
    skill(C) = design-binder ∧ act = refuse ∧ gate ∈ PrePin → ^ callId(C)                (P4)
    skill(C) = design-binder ∧ act = halt ∧ pins(H) = ∅    → ^ callId(C)                 (P5)
    |pins(H)| = 1                                          → ^ id(the pin)               (P6)
    otherwise                                              → ⊥
```

`sameMolecule` is `follow-agent-contract.md` §8.13 on the binder strings of `propose` lines: equal `aa:` multisets, equal `helm:` payloads after polymer-index normalisation, or an `aa:` key and a plain-L-chain `helm:` key with that sequence. One string used twice is one key.

## 3. Judgements

```
C ⊢ CoreOk
C, ℓ ⊢ Admit
C, F ⊢ FileOk
C, H ⊢ Rk          k ∈ 1..10
C, H ⊢ Result
decide(F) = result(run)  |  partial(code)
```

`Admit` is local. `Rk` is stated of the head of admitted lines. `decide` is total: it returns the first failure in the order below, else `result`.

`Admit` holds iff all of these hold, and the code is the first that fails:

| code | condition |
|---|---|
| `syntax` | the line matches §0, keys sorted, each value inside its byte cap |
| `hash` | `Id = H(preimage)` |
| `run` | the line's `run` equals `run(C)` |
| `skill` | the line's `skill` equals `skill(C)` |
| `act` | `act ∈ Acts(skill)` |
| `fields` | the key tuple equals `Fields(act)`, or the `Context` row when `act = context` |
| `value` | every value meets §1; `halt` bounds equal the core |
| `parent` | `Parent` is `^0` or `^Hex64`, and it equals P1–P4 where those clauses do not read `H`; a P6-shaped line's parent is `^Hex64` and is not `^0` and is not `^callId(C)`; a `design-binder` `halt` may use either `^callId(C)` or another `^Hex64` |

`FileOk` holds iff the core basename is `core.trace`, every worker basename is `Worker ".trace"`, every header equals `%trace/1 core=<run(C)> spec=<spec(C)>`, and every line admits. Otherwise `decide` returns `partial(R1)` when the core has no derivation, `partial(R3)` when a name or header fails, and `partial(admit)` when a line fails `Admit`. Line failures are reported before the R-curve. A line that fails `Admit` is not in `H`.

On a head that passed `FileOk`:

| id | holds iff |
|---|---|
| R1 | `C ⊢ CoreOk` and `run(C) = H(bytes(C))` |
| R2 | every line in `H` carries `run(C)` and `skill(C)` |
| R3 | every worker header matches §0 for this core, and every basename matches §0 |
| R4 | `H` contains one `call`, and it is the line with id `callId(C)` |
| R5 | `H` contains one `halt`; its bounds equal the core; its oracle is `not-discharged`; its parent is `^callId(C)` when `pins(H) = ∅`, the pin's id when `|pins(H)| = 1`, and there is no derivation when `|pins(H)| > 1` |
| R6 | every parent id other than `^0` is the id of a line in `H` |
| R7 | every line's act is in `Acts(skill)` and its parent equals `parent(C, ℓ, H)` |
| R8 | every value in `H` meets §1 |
| R9 | no two distinct `propose` binders are one molecule under `sameMolecule` |
| R10 | the skill shape below |

```
propose-pairs:
    |pins| = 1 ∧ pin parents callId
    ∧ every other non-call line parents that pin
    ∧ no context line ∧ no emit line

resolve-key:
    pins = proposes = contexts = emits = ∅
    ∧ every non-call line parents callId

design-binder, pins = ∅:
    at least one refuse whose gate ∈ PrePin
    ∧ no context ∧ no emit
    ∧ every non-call line parents callId

design-binder, |pins| = 1:
    exactly one context, parent the pin
    ∧ halt parents the pin
    ∧ every emit parents the pin
    ∧ every refuse whose gate ∉ PrePin parents the pin
    ∧ verdict hit-same-indication ⇒ no emit
    ∧ every emit has kind hypothesis and Disclaimer
```

`C, H ⊢ Result` iff `FileOk` and R1 ∧ … ∧ R10. `decide` prints `result` and `run(C)`, or `partial` and the first code. It does not print a fraction.

Merge of workers is set union on `Id`. Identical bytes are one line. Union is associative, commutative, and idempotent because `Id` is `H` of the preimage.

## 4. Non-theorems

The following are not judgements. A checker that returns `result` has not decided them.

- A line's act is an event that occurred. `Admit` decides shape.
- The catalogue blob named by `rev` was fetched. `decide` does not open `graph.json`.
- `follow-agent-contract.md` §8.16. The only derived oracle string is `not-discharged`.
- Patient benefit. `Result` on a design head is a hypothesis carrying `Disclaimer`, or a named refusal. `Disclaimer` sits inside the preimage, so a line with the disclaimer removed has a different `Id` and fails `hash`.
- Any area under a curve. `Coverage` is the judgement `Result`, not a number.

A `.trace` byte string is not a `proposals.json` element and not a `.bench` line. `%trace/` does not parse as `%bench/`.

## 5. Witness

Illustration. `spec` is forty `a`s and `rev` is forty `b`s. The proposal `aa:ACD` / `uniprot:P12345` / `pmid:1` is a grammar fixture, not a claim of benefit. `H` of the core bytes is `run`. `H` of a line with its second token removed is that line's `Id`.

`core.trace`:

```
%trace-core/1
bound-n:"1"
bound-tok:"8000"
skill:"propose-pairs"
spec:"aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"
```

`run` = `d2066050893688b4fc69def4b3c03ffa9ee8b06ef14858786224a7adf2684853`.

`a1.trace`:

```
%trace/1 core=d2066050893688b4fc69def4b3c03ffa9ee8b06ef14858786224a7adf2684853 spec=aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa
call 82d0bb98077f59cb3544536e2023d4cf99699408e57250de2ce20d3e0b20a294 ^0 run=d2066050893688b4fc69def4b3c03ffa9ee8b06ef14858786224a7adf2684853 skill=propose-pairs
pin 2f3f7335675c72766882db3b0dea24b20818183f1934fd10eb131a10ba13fba4 ^82d0bb98077f59cb3544536e2023d4cf99699408e57250de2ce20d3e0b20a294 run=d2066050893688b4fc69def4b3c03ffa9ee8b06ef14858786224a7adf2684853 skill=propose-pairs path:"graph.json" rev:"bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb"
refuse 4d25814dcfdc011016c4c4126bb3a220e4a69e52d7517a9d7b395a8c7d40dfbe ^2f3f7335675c72766882db3b0dea24b20818183f1934fd10eb131a10ba13fba4 run=d2066050893688b4fc69def4b3c03ffa9ee8b06ef14858786224a7adf2684853 skill=propose-pairs gate:"illegal-payload" subject:"helm:PEPTIDE1{[CCO]}$$$$"
propose 179014b62688af1357af3e8dad3f4dd0fcf0e4675426115a52390b8e02ae4b46 ^2f3f7335675c72766882db3b0dea24b20818183f1934fd10eb131a10ba13fba4 run=d2066050893688b4fc69def4b3c03ffa9ee8b06ef14858786224a7adf2684853 skill=propose-pairs binder:"aa:ACD" pmid:"pmid:1" target:"uniprot:P12345"
halt 9d2001abc00391ea2c66714740c2ba9ec5c279405495498f51a72db31be4d6a3 ^2f3f7335675c72766882db3b0dea24b20818183f1934fd10eb131a10ba13fba4 run=d2066050893688b4fc69def4b3c03ffa9ee8b06ef14858786224a7adf2684853 skill=propose-pairs bound-n:"1" bound-tok:"8000" oracle:"not-discharged"
```

`decide` of this pair of files is `result`.

## 6. Status

`decide` is implemented by `verifier/verify.py --trace`; `fleet/fleet.py` emits the language through
the verifier's own `trace_emit`, then hands every completed run back to that checker. Extension
predicate E4 decides the bijection between `follow-agent-contract.md` §11 and the files
`systems/*.md` and `traces/*.md`. Neither judgement is §8.16.
