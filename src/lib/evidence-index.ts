import type { CompactClaim, EvidenceCorpus } from "../types/catalog.js";

export type EvidenceIndex = {
  claimsById: ReadonlyMap<string, CompactClaim>;
  claimsForSlug: (slug: string) => CompactClaim[];
};

/** Pure index from an in-memory corpus (order of `claims[]` does not affect lookup). */
export function indexEvidence(corpus: EvidenceCorpus): EvidenceIndex {
  const claimsById = new Map(corpus.claims.map((c) => [c.claim_id, c]));
  return {
    claimsById,
    claimsForSlug(slug: string) {
      return (corpus.by_slug[slug] ?? [])
        .map((id) => claimsById.get(id))
        .filter((c): c is CompactClaim => c != null);
    },
  };
}
