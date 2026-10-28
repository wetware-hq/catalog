/**
 * Validates docs/requirements.yaml structure and verification references.
 */
import { readFileSync, existsSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";
import { parse } from "yaml";

const ROOT = join(dirname(fileURLToPath(import.meta.url)), "..");
const reqPath = join(ROOT, "docs", "requirements.yaml");

type Requirement = {
  id?: string;
  title?: string;
  rationale?: string;
  verification?: { check?: string; tests?: string[] };
};

function main() {
  const doc = parse(readFileSync(reqPath, "utf8")) as {
    schema_version?: string;
    requirements?: Requirement[];
  };
  if (!doc.schema_version) {
    fail("missing schema_version");
  }
  if (!Array.isArray(doc.requirements) || doc.requirements.length === 0) {
    fail("requirements must be a non-empty array");
  }
  const ids = new Set<string>();
  for (const [i, req] of doc.requirements.entries()) {
    const prefix = `requirements[${i}]`;
    for (const field of ["id", "title", "rationale", "verification"] as const) {
      if (req[field] === undefined || req[field] === "") {
        fail(`${prefix} missing ${field}`);
      }
    }
    if (!/^REQ-[A-Z0-9-]+$/.test(req.id!)) {
      fail(`${prefix} id must match REQ-* pattern`);
    }
    if (ids.has(req.id!)) {
      fail(`duplicate requirement id ${req.id}`);
    }
    ids.add(req.id!);
    const v = req.verification!;
    if (!v.check && (!v.tests || v.tests.length === 0)) {
      fail(`${prefix} verification needs check and/or tests`);
    }
    for (const t of v.tests ?? []) {
      const path = join(ROOT, t);
      if (!existsSync(path)) {
        fail(`${prefix} references missing test file ${t}`);
      }
    }
    if (v.check?.includes("openapi/")) {
      const oas = join(ROOT, "openapi", "catalog.openapi.yaml");
      if (!existsSync(oas)) {
        fail(`${prefix} openapi file missing`);
      }
    }
    if (v.check?.includes("PROVENANCE.md")) {
      const prov = join(ROOT, "data", "evidence", "PROVENANCE.md");
      if (!existsSync(prov)) {
        fail(`${prefix} PROVENANCE.md missing`);
      }
    }
  }
  console.log(`Validated ${doc.requirements.length} requirements`);
}

function fail(msg: string): never {
  console.error("requirements.yaml:", msg);
  process.exit(1);
}

main();
