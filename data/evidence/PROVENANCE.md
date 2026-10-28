# Peptide evidence provenance (fleet v3)

Compact file `peptide-claims.compact.json` is generated from Wetware fleet v3 claim verification outputs. Raw uploads (~6.8 MB) are **not** committed; regenerate with:

```bash
CLAIM_UPLOADS_DIR=/path/to/uploads npm run build:evidence
```

## Source files (default paths)

| File | Role |
|------|------|
| `merged_claims_*.jsonl` | 2,486 merged claims before tie-break (statuses: `confirmed_2of2`, `confirmed_2of2_same_family`, `needs_tiebreak`, `single_replica`, `unresolvable`) |
| `T01_claims_*.jsonl` | Tie-breaker for 188 `needs_tiebreak` claims (third model family) |
| `spot_check_results_*.jsonl` | 5% spot-check (36 claims); disagreements on **histrelin** and **GHK-Cu** force `unresolvable` |
| `agreement.json`, fleet README | Run metadata |

## Resolution rules (implemented in `scripts/build-evidence.ts`)

1. **`needs_tiebreak`**: apply T01; if any verdict appears ≥2 times across the two replicas + T01 → `confirmed_2of3` (verified).
2. **Spot-check disagree** → `unresolvable` (unverified), regardless of prior status.
3. **Spot-check agree** on an already confirmed claim → label `spot_check_confirmed` (verified).
4. Otherwise carry forward `verification_status` verbatim from merge output.
5. **`verified: true`** only for `confirmed_2of2`, `confirmed_2of2_same_family`, `confirmed_2of3`, or `spot_check_confirmed`.

## Clinical use

Evidence references attached to catalog skills are **decision-support citations**, not prescribing instructions. Unverified claims are labeled explicitly and must not be treated as clinical fact.
