⚠️ ACADEMIC RESEARCH PURPOSES ONLY; NOT FOR MEDICAL USE WITHOUT LICENSED OVERSIGHT

# Biofleet EGFR campaign summary (A2A Agent Card specification)

This file records one `fleet.campaign` run against the pinned catalogue at commit `4108e940ee5f8c8aad7d8e1ae173bbe166c718cb`. It is a descriptive Agent Card, not a live A2A endpoint. Runtime authority remains [`systems/run-campaign.md`](../systems/run-campaign.md).

## Campaign summary

Two phases executed outside this repository under `/home/ubuntu/biofleet/`.

| Phase | When (Australia/Sydney) | Outcome |
|---|---|---|
| Catalogue gate | 4 Nov 2026, 9:13 am | Ranked oncology/immunology `pair` targets; selected `uniprot:P00533` (EGFR); **hit-same-indication** on cetuximab for head and neck SCC (pmid:16467544); **no design spend** |
| Blinded positive control | 4 Nov 2026, 9:21–9:27 am | Boltz peptide design on EGFR domain III (PDB 1YY9 crop, 22 epitope indices); **positive-control-failed** (`binding_confidence` bar 0.7); **USD 0.25 estimated**; **zero binders emitted** |

Ranking law: within dictionary `pair` only; count in-scope papers whose read area is oncology or immunology; descending; tie-break target key ascending. Seven targets tied at two in-scope citations; EGFR sorts first on accession. VEGFA has four clinical citations but only one in-scope (bevacizumab in mCRC).

Positive control withheld catalogue Fab chains and sequences. Primary pass metric: `metrics.binding_confidence` ≥ 0.7. Supporting metrics (`iptm`, `structure_confidence`, `min_interaction_pae`) did not substitute. Best candidate: `SLSEAEQKLLDEVKSLS` at binding confidence 0.108, 15/22 epitope contacts within 4.5 Å.

Trace judgements: gate `result` run `f941afe146343fab22fff05cab5ebacf416b9dcfa84ae07cd5a490fd27094695`; calibration `result` run `d0c39db694ec49716002d67433092e0053a3b527f53b263a2b93c4ab73a468c5`. Paper oracle: **not-discharged**.

External run reports (not committed here): `/home/ubuntu/biofleet/runs/20261104T091305+1100/report.json`, `/home/ubuntu/biofleet/runs/20261104T092853+1100/report.json`.

## Agent Card (A2A v1.0 shape)

```json
{
  "name": "catalog-biofleet-egfr-2026-11-04",
  "description": "Pinned-catalogue fleet.campaign: rank oncology and immunology pair targets, run the design-binder gate, then blinded Boltz peptide calibration on the cetuximab EGFR epitope without revealing catalogue binder sequences.",
  "version": "1.0.0",
  "documentationUrl": "https://github.com/wetware-hq/catalog/blob/4108e940ee5f8c8aad7d8e1ae173bbe166c718cb/systems/run-campaign.md",
  "supportedInterfaces": [
    {
      "url": "https://github.com/wetware-hq/catalog/tree/4108e940ee5f8c8aad7d8e1ae173bbe166c718cb",
      "protocolBinding": "DOCUMENTATION",
      "protocolVersion": "1.0"
    }
  ],
  "provider": {
    "organization": "Wetware",
    "url": "https://github.com/wetware-hq/catalog"
  },
  "capabilities": {
    "streaming": false,
    "pushNotifications": false,
    "extensions": [],
    "extendedAgentCard": false
  },
  "defaultInputModes": ["application/json"],
  "defaultOutputModes": ["application/json", "text/markdown"],
  "skills": [
    {
      "id": "rank-oncology-immunology-pair-targets",
      "name": "Rank oncology and immunology pair targets",
      "description": "Build a reverse index from pinned graph.json pair rows; rank by in-scope pmid count within oncology or immunology reads; never pool preclinical.",
      "tags": ["catalogue", "pair", "oncology", "immunology", "ranking"]
    },
    {
      "id": "design-binder-catalogue-gate",
      "name": "Design-binder catalogue gate",
      "description": "Stop on hit-same-indication; branch hit-other-indication only after reading the paper; record hit-unread without designing.",
      "tags": ["design-binder", "gate", "indication-aware"]
    },
    {
      "id": "blinded-positive-control-calibration",
      "name": "Blinded positive control calibration",
      "description": "Epitope-conditioned provider design on a mapped co-structure with reference binder chains withheld; pass only if binding_confidence crosses a pre-registered bar and geometry contacts the mapped epitope.",
      "tags": ["positive-control", "boltz", "epitope", "binding_confidence"]
    }
  ],
  "extensions": {
    "fleet.campaign": {
      "specCommit": "4108e940ee5f8c8aad7d8e1ae173bbe166c718cb",
      "selectedTarget": "uniprot:P00533",
      "gene": "EGFR",
      "phases": [
        {
          "id": "catalogue-gate",
          "verdict": "hit-same-indication",
          "stoppingPmid": "pmid:16467544",
          "stoppingDrug": "cetuximab",
          "indication": "locoregionally advanced squamous-cell carcinoma of the head and neck",
          "designRequests": 0,
          "estimateRequests": 0,
          "traceRun": "f941afe146343fab22fff05cab5ebacf416b9dcfa84ae07cd5a490fd27094695"
        },
        {
          "id": "blinded-calibration",
          "verdict": "positive-control-failed",
          "contextVerdict": "hit-other-indication",
          "indication": "blinded recovery of the mapped cetuximab epitope on EGFR",
          "providerRun": "prot_des_6SDannvhmPSi293YAsJ2",
          "providerStatus": "succeeded",
          "estimatedCostUsd": "0.2500",
          "requestSha256": "b615e910dbf792b808e0a0639a7e057c38934418f510c4e75daeae33f089d944",
          "primaryMetric": "metrics.binding_confidence",
          "primaryBar": 0.7,
          "bestBindingConfidence": 0.10832766083050813,
          "bestCandidateId": "pres_Bxgm7DvSbKwlNY7MP4yd",
          "candidatesGenerated": 10,
          "candidatesEmitted": 0,
          "traceRun": "d0c39db694ec49716002d67433092e0053a3b527f53b263a2b93c4ab73a468c5"
        }
      ],
      "structure": {
        "pdb": "1YY9",
        "pdbSha256": "e574b33a287c4100ff35f8346a6eadba1486d4a90464f4344f3189115f6d5fa8",
        "cropAuthor": "310-514",
        "cropUniprot": "334-538",
        "epitopeResidueCount": 22,
        "withheldChains": ["C", "D"]
      },
      "oracle": "not-discharged"
    }
  }
}
```

## Licence

MIT
