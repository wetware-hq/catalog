/**
 * Derives compact peptide evidence from verification uploads (not committed raw).
 * Run: npm run build:evidence
 *
 * Provenance: see data/evidence/PROVENANCE.md
 */
import { createHash } from "node:crypto";
import { readFileSync, writeFileSync, mkdirSync, existsSync, readdirSync } from "node:fs";
import { basename, dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

const __dirname = dirname(fileURLToPath(import.meta.url));
const ROOT = join(__dirname, "..");
const UPLOADS = process.env.CLAIM_UPLOADS_DIR ?? join(ROOT, "data", "evidence", "uploads");

type MergedClaim = {
  claim_id: string;
  claim_type: string;
  slug: string;
  status: string;
  verdict: string;
  fact?: unknown;
  value?: unknown;
  identifiers?: Record<string, unknown>;
  evidence_quote?: string | null;
  voters?: { verdict: string; fact?: unknown }[];
  representative?: {
    subject?: { slug?: string; name?: string };
    claim_text?: string;
    authority?: string;
    evidence_type?: string;
    note?: string;
  };
};

type TieClaim = MergedClaim & { worker?: { agent_id?: string } };

type SpotRow = { claim_id: string; agree: boolean; note?: string };

function resolveUploadFile(pattern: RegExp, preferredName: string): string {
  const preferred = join(UPLOADS, preferredName);
  if (existsSync(preferred)) return preferred;
  if (existsSync(UPLOADS)) {
    const hit = readdirSync(UPLOADS).find((f) => pattern.test(f));
    if (hit) return join(UPLOADS, hit);
  }
  return preferred;
}

function loadJsonl<T>(path: string): T[] {
  return readFileSync(path, "utf8")
    .split("\n")
    .filter((l) => l.trim())
    .map((l) => JSON.parse(l) as T);
}

function majorityVerdict(verdicts: string[]): string | null {
  const counts = new Map<string, number>();
  for (const v of verdicts) {
    counts.set(v, (counts.get(v) ?? 0) + 1);
  }
  let best: string | null = null;
  let bestN = 0;
  for (const [v, n] of counts) {
    if (n > bestN) {
      bestN = n;
      best = v;
    }
  }
  return bestN >= 2 ? best : null;
}

const VERIFIED_STATUSES = new Set([
  "confirmed_2of2",
  "confirmed_2of2_same_family",
  "confirmed_2of3",
  "spot_check_confirmed",
]);

function sanitizeAuthority(authority: string | null | undefined): string | null {
  if (!authority) return null;
  return authority.replace(/\s*\(rater V\d+ from fetched primary sources\)/i, " (from primary sources)");
}

function resolveStatus(
  merged: MergedClaim,
  tie: TieClaim | undefined,
  spot: SpotRow | undefined,
): { verification_status: string; verified: boolean; resolution_note?: string } {
  if (spot && !spot.agree) {
    return {
      verification_status: "unresolvable",
      verified: false,
      resolution_note: "spot_check_disagree: 5% spot-check reviewer disagreed with merged verification verdict.",
    };
  }

  if (merged.status === "needs_tiebreak" && tie) {
    const verdicts = [...(merged.voters ?? []).map((v) => v.verdict), tie.verdict];
    const maj = majorityVerdict(verdicts);
    if (maj) {
      const base = spot?.agree ? "spot_check_confirmed" : "confirmed_2of3";
      return {
        verification_status: base,
        verified: true,
        resolution_note: "Resolved needs_tiebreak via 2-of-3 majority (tie-break pass).",
      };
    }
    return {
      verification_status: "unresolvable",
      verified: false,
      resolution_note: "needs_tiebreak: no 2-of-3 majority after tie-break pass.",
    };
  }

  if (merged.status === "needs_tiebreak" && !tie) {
    return {
      verification_status: "unresolvable",
      verified: false,
      resolution_note: "needs_tiebreak: missing tie-break record.",
    };
  }

  if (spot?.agree && VERIFIED_STATUSES.has(merged.status)) {
    return {
      verification_status: "spot_check_confirmed",
      verified: true,
      resolution_note: "Spot-check agreed with prior verification verdict.",
    };
  }

  const status = merged.status;
  const verified = VERIFIED_STATUSES.has(status);
  return { verification_status: status, verified };
}

function main() {
  const outPath = join(ROOT, "data", "evidence", "peptide-claims.compact.json");
  const mergedPath = resolveUploadFile(/^merged_claims.*\.jsonl$/, "merged_claims.jsonl");
  const tiePath = resolveUploadFile(/^(tiebreak|T01).*\.jsonl$/i, "tiebreak_claims.jsonl");
  const spotPath = resolveUploadFile(/^spot_check.*\.jsonl$/, "spot_check_results.jsonl");

  if (!existsSync(mergedPath)) {
    if (existsSync(outPath)) {
      console.log("Uploads missing; keeping existing", outPath);
      return;
    }
    throw new Error(`Missing uploads at ${UPLOADS} and no existing ${outPath}`);
  }

  const merged = loadJsonl<MergedClaim>(mergedPath);
  const ties = new Map(
    (existsSync(tiePath) ? loadJsonl<TieClaim>(tiePath) : []).map((c) => [c.claim_id, c]),
  );
  const spots = new Map(
    (existsSync(spotPath) ? loadJsonl<SpotRow>(spotPath) : []).map((s) => [s.claim_id, s]),
  );

  const outClaims = merged.map((m) => {
    const tie = ties.get(m.claim_id);
    const spot = spots.get(m.claim_id);
    const { verification_status, verified, resolution_note } = resolveStatus(m, tie, spot);
    const rep = m.representative;
    return {
      claim_id: m.claim_id,
      slug: m.slug ?? rep?.subject?.slug ?? "",
      peptide_name: rep?.subject?.name ?? null,
      claim_type: m.claim_type,
      verification_status,
      verified,
      verdict: m.verdict,
      claim_text: rep?.claim_text ?? null,
      authority: sanitizeAuthority(rep?.authority ?? null),
      evidence_type: rep?.evidence_type ?? null,
      identifiers: m.identifiers ?? {},
      resolution_note: resolution_note ?? null,
    };
  });

  const bySlug = new Map<string, typeof outClaims>();
  for (const c of outClaims) {
    if (!c.slug) continue;
    const arr = bySlug.get(c.slug) ?? [];
    arr.push(c);
    bySlug.set(c.slug, arr);
  }

  const summary = {
    generated_at: new Date().toISOString(),
    source_files: {
      merged: basename(mergedPath),
      tiebreaker: basename(tiePath),
      spot_check: basename(spotPath),
    },
    total_claims: outClaims.length,
    verified_count: outClaims.filter((c) => c.verified).length,
    status_counts: outClaims.reduce(
      (acc, c) => {
        acc[c.verification_status] = (acc[c.verification_status] ?? 0) + 1;
        return acc;
      },
      {} as Record<string, number>,
    ),
    unique_slugs: bySlug.size,
  };

  const by_slug: Record<string, string[]> = {};
  for (const [slug, claims] of bySlug) {
    by_slug[slug] = claims.map((c) => c.claim_id);
  }
  const payload = { summary, claims: outClaims, by_slug };
  const json = JSON.stringify(payload);
  const sha256 = createHash("sha256").update(json).digest("hex");

  const outDir = join(ROOT, "data", "evidence");
  mkdirSync(outDir, { recursive: true });
  writeFileSync(outPath, json);
  writeFileSync(
    join(outDir, "peptide-claims.compact.sha256"),
    `${sha256}  peptide-claims.compact.json\n`,
  );

  console.log("Wrote", outPath);
  console.log(JSON.stringify(summary, null, 2));
}

main();
