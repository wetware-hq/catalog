import { readFileSync, existsSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";
import type { CompactClaim, EvidenceCorpus } from "../types/catalog.js";
import { indexEvidence } from "./evidence-index.js";

const packageRoot = join(dirname(fileURLToPath(import.meta.url)), "..", "..");

export function repoPath(...segments: string[]): string {
  return join(packageRoot, ...segments);
}

let cached: EvidenceCorpus | null = null;

export function loadEvidenceCorpus(): EvidenceCorpus {
  if (cached) return cached;
  const path = repoPath("data", "evidence", "peptide-claims.compact.json");
  if (!existsSync(path)) {
    throw new Error(
      `Missing ${path}. Run: npm run build:evidence (requires verification uploads; see data/evidence/PROVENANCE.md)`,
    );
  }
  cached = JSON.parse(readFileSync(path, "utf8")) as EvidenceCorpus;
  return cached;
}

/** Edge loader helper — prefer passing corpus into pure rank(). */
export function claimsById(): Map<string, CompactClaim> {
  return new Map(indexEvidence(loadEvidenceCorpus()).claimsById);
}

export function claimsForSlug(slug: string): CompactClaim[] {
  return indexEvidence(loadEvidenceCorpus()).claimsForSlug(slug);
}
