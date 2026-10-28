/**
 * Validates MADR-style ADR markdown under docs/adr/.
 */
import { readFileSync, readdirSync } from "node:fs";
import { join, dirname } from "node:path";
import { fileURLToPath } from "node:url";

const ADR_DIR = join(dirname(fileURLToPath(import.meta.url)), "..", "docs", "adr");
const REQUIRED_SECTIONS = ["## Status", "## Context", "## Decision", "## Consequences"];

function main() {
  const files = readdirSync(ADR_DIR)
    .filter((f) => f.endsWith(".md"))
    .sort();
  if (files.length === 0) {
    console.error("No ADR files in docs/adr/");
    process.exit(1);
  }
  for (const file of files) {
    const content = readFileSync(join(ADR_DIR, file), "utf8");
    if (!content.startsWith("# ")) {
      fail(file, "must start with # title");
    }
    for (const section of REQUIRED_SECTIONS) {
      if (!content.includes(section)) {
        fail(file, `missing section ${section}`);
      }
    }
  }
  console.log(`Validated ${files.length} ADR(s)`);
}

function fail(file: string, msg: string): never {
  console.error(`ADR ${file}: ${msg}`);
  process.exit(1);
}

main();
