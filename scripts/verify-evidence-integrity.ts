/**
 * Verifies data/evidence/peptide-claims.compact.sha256 matches the JSON file.
 */
import { createHash } from "node:crypto";
import { readFileSync, existsSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

const ROOT = join(dirname(fileURLToPath(import.meta.url)), "..");
const jsonPath = join(ROOT, "data", "evidence", "peptide-claims.compact.json");
const sidecarPath = join(ROOT, "data", "evidence", "peptide-claims.compact.sha256");

function main() {
  if (!existsSync(jsonPath) || !existsSync(sidecarPath)) {
    console.error("Missing evidence corpus or sha256 sidecar");
    process.exit(1);
  }
  const json = readFileSync(jsonPath);
  const expected = createHash("sha256").update(json).digest("hex");
  const line = readFileSync(sidecarPath, "utf8").trim();
  const [recorded] = line.split(/\s+/, 1);
  if (recorded !== expected) {
    console.error(`SHA-256 mismatch: sidecar=${recorded} computed=${expected}`);
    process.exit(1);
  }
  console.log("Evidence integrity OK:", expected);
}

main();
