/**
 * Ensures data/evidence/REFERENCES.md matches the current corpus.
 */
import { existsSync, readFileSync } from "node:fs";
import { join, dirname } from "node:path";
import { fileURLToPath } from "node:url";
import { execSync } from "node:child_process";

const ROOT = join(dirname(fileURLToPath(import.meta.url)), "..");
const REF = join(ROOT, "data", "evidence", "REFERENCES.md");

function main() {
  if (!existsSync(REF)) {
    console.error("Missing data/evidence/REFERENCES.md — run npm run generate:evidence-references");
    process.exit(1);
  }
  const before = readFileSync(REF, "utf8");
  execSync("npm run generate:evidence-references", { cwd: ROOT, stdio: "pipe" });
  const after = readFileSync(REF, "utf8");
  if (before !== after) {
    console.error("REFERENCES.md is out of sync with peptide-claims.compact.json");
    console.error("Run: npm run generate:evidence-references && git add data/evidence/REFERENCES.md");
    process.exit(1);
  }
  console.log("Evidence REFERENCES.md is in sync");
}

main();
