/**
 * Generates data/evidence/REFERENCES.md from peptide-claims.compact.json.
 * Lists authorities and bibliographic identifiers present in the corpus (no invented metadata).
 */
import { createHash } from "node:crypto";
import { readFileSync, writeFileSync, mkdirSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

const ROOT = join(dirname(fileURLToPath(import.meta.url)), "..");
const CORPUS = join(ROOT, "data", "evidence", "peptide-claims.compact.json");
const OUT = join(ROOT, "data", "evidence", "REFERENCES.md");

type Claim = {
  authority?: string | null;
  identifiers?: { url?: string; pmid?: string; doi?: string; nct?: string };
};

function main() {
  const claims = (JSON.parse(readFileSync(CORPUS, "utf8")) as { claims: Claim[] }).claims;
  const authorityStats = new Map<string, { count: number; sampleUrl?: string }>();
  const pmids = new Set<string>();
  const dois = new Set<string>();
  const ncts = new Set<string>();

  for (const c of claims) {
    if (c.authority) {
      const cur = authorityStats.get(c.authority) ?? { count: 0 };
      cur.count++;
      const url = c.identifiers?.url;
      if (url && !cur.sampleUrl) cur.sampleUrl = url;
      authorityStats.set(c.authority, cur);
    }
    if (c.identifiers?.pmid) pmids.add(String(c.identifiers.pmid));
    if (c.identifiers?.doi) dois.add(String(c.identifiers.doi));
    if (c.identifiers?.nct) ncts.add(String(c.identifiers.nct));
  }

  const corpusHash = createHash("sha256").update(readFileSync(CORPUS)).digest("hex").slice(0, 16);
  const lines: string[] = [
    "# Evidence corpus references",
    "",
    `Auto-generated from \`peptide-claims.compact.json\` (corpus sha256 prefix \`${corpusHash}\`).`,
    "Regenerate with `npm run generate:evidence-references` after corpus changes.",
    "",
    "Per-claim citations remain inline in the JSON (`authority`, `identifiers.url`, PMID, DOI, NCT).",
    "",
    "## Regulatory and database authorities",
    "",
    "| Ref | Authority (as recorded on claims) | Example URL in corpus | Claims |",
    "|-----|-----------------------------------|------------------------|--------|",
  ];

  const sortedAuthorities = [...authorityStats.entries()].sort((a, b) => b[1].count - a[1].count);
  let ref = 1;
  const authorityRef = new Map<string, number>();
  for (const [name, stat] of sortedAuthorities) {
    authorityRef.set(name, ref);
    const url = stat.sampleUrl ?? "—";
    lines.push(`| [A${ref}] | ${name.replace(/\|/g, "\\|")} | ${url.replace(/\|/g, "\\|")} | ${stat.count} |`);
    ref++;
  }

  lines.push(
    "",
    "## PubMed identifiers (PMID)",
    "",
    `${pmids.size} unique PMIDs. Resolve at \`https://pubmed.ncbi.nlm.nih.gov/{pmid}/\`.`,
    "",
  );
  for (const pmid of [...pmids].sort()) {
    lines.push(`- [P${pmid}](https://pubmed.ncbi.nlm.nih.gov/${pmid}/)`);
  }

  lines.push(
    "",
    "## DOI identifiers",
    "",
    `${dois.size} unique DOIs. Resolve at \`https://doi.org/{doi}\`.`,
    "",
  );
  for (const doi of [...dois].sort()) {
    lines.push(`- [D${doi}](https://doi.org/${doi})`);
  }

  lines.push(
    "",
    "## ClinicalTrials.gov identifiers (NCT)",
    "",
    `${ncts.size} unique NCT numbers. Resolve at \`https://clinicaltrials.gov/study/{nct}\`.`,
    "",
  );
  for (const nct of [...ncts].sort()) {
    lines.push(`- [N${nct}](https://clinicaltrials.gov/study/${nct})`);
  }

  lines.push("");
  mkdirSync(dirname(OUT), { recursive: true });
  writeFileSync(OUT, lines.join("\n"));
  console.log(
    `Wrote ${OUT} (${authorityStats.size} authorities, ${pmids.size} PMIDs, ${dois.size} DOIs, ${ncts.size} NCTs)`,
  );
}

main();
