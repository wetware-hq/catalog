import { readFileSync, existsSync } from "node:fs";
import type { CompactClaim, EvidenceCorpus } from "../types/catalog.js";
import { repoPath } from "./paths.js";

let cached: EvidenceCorpus | null = null;

export function loadEvidenceCorpus(): EvidenceCorpus {
  if (cached) return cached;
  const path = repoPath("data", "evidence", "peptide-claims.compact.json");
  if (!existsSync(path)) {
    throw new Error(
      `Missing ${path}. Run: npm run build:evidence (requires fleet v3 uploads; see data/evidence/PROVENANCE.md)`,
    );
  }
  cached = JSON.parse(readFileSync(path, "utf8")) as EvidenceCorpus;
  return cached;
}

export function claimsById(): Map<string, CompactClaim> {
  const corpus = loadEvidenceCorpus();
  return new Map(corpus.claims.map((c) => [c.claim_id, c]));
}

export function claimsForSlug(slug: string): CompactClaim[] {
  const corpus = loadEvidenceCorpus();
  const ids = corpus.by_slug[slug] ?? [];
  const byId = claimsById();
  return ids.map((id) => byId.get(id)).filter(Boolean) as CompactClaim[];
}
