import { readFileSync } from "node:fs";
import { loadEvidenceCorpus, repoPath } from "../../src/lib/corpus.js";
import { normalizePatientInput } from "../../src/lib/patient.js";
import { rank } from "../../src/lib/rank.js";
import { loadRegistryEntries } from "../../src/lib/registry.js";

export function rankFixture(basename: string, limit = 10) {
  const raw = JSON.parse(readFileSync(repoPath("fixtures", "patients", basename), "utf8"));
  const patient = normalizePatientInput(raw);
  return rank(patient, loadRegistryEntries("peptides"), loadEvidenceCorpus(), {
    domainId: "peptides",
    limit,
  });
}
