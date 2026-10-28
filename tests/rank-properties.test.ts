import { describe, expect, it } from "vitest";
import { readFileSync } from "node:fs";
import type { RankResponse } from "../src/types/catalog.js";
import { loadEvidenceCorpus, repoPath } from "../src/lib/corpus.js";
import { normalizePatientInput } from "../src/lib/patient.js";
import { rank } from "../src/lib/rank.js";
import { loadRegistryEntries } from "../src/lib/registry.js";
import { stableStringify } from "../src/lib/stable-json.js";
import { rankFixture } from "./helpers/rank-fixture.js";

function shuffle<T>(arr: T[]): T[] {
  const out = [...arr];
  for (let i = out.length - 1; i > 0; i--) {
    const j = (i * 17 + 3) % (i + 1);
    [out[i], out[j]] = [out[j]!, out[i]!];
  }
  return out;
}

function collectEvidenceClaimIds(result: RankResponse): string[] {
  const ids: string[] = [];
  for (const agent of result.rankedAgents) {
    for (const skill of agent.matchedSkills) {
      for (const ref of skill.evidenceRefs) {
        ids.push(ref.claim_id);
      }
    }
  }
  return ids;
}

describe("rank properties", () => {
  it("is invariant under registry entry reordering", () => {
    const raw = JSON.parse(
      readFileSync(repoPath("fixtures", "patients", "synthetic-athlete-tendon-simple.json"), "utf8"),
    );
    const patient = normalizePatientInput(raw);
    const corpus = loadEvidenceCorpus();
    const registry = loadRegistryEntries("peptides");
    const a = rank(patient, registry, corpus, { domainId: "peptides", limit: 10 });
    const b = rank(patient, shuffle(registry), corpus, { domainId: "peptides", limit: 10 });
    expect(stableStringify(b)).toBe(stableStringify(a));
  });

  it("is invariant under evidence claim reordering", () => {
    const raw = JSON.parse(
      readFileSync(repoPath("fixtures", "patients", "synthetic-t2dm-weight-simple.json"), "utf8"),
    );
    const patient = normalizePatientInput(raw);
    const corpus = loadEvidenceCorpus();
    const shuffledCorpus = { ...corpus, claims: shuffle([...corpus.claims]) };
    const registry = loadRegistryEntries("peptides");
    const a = rank(patient, registry, corpus, { domainId: "peptides", limit: 10 });
    const b = rank(patient, registry, shuffledCorpus, { domainId: "peptides", limit: 10 });
    expect(stableStringify(b)).toBe(stableStringify(a));
  });

  it("fail-closed: every evidenceRef claim_id exists in the corpus", () => {
    const result = rankFixture("synthetic-fertility-fhir.json", 10);
    const ids = new Set(loadEvidenceCorpus().claims.map((c) => c.claim_id));
    for (const claimId of collectEvidenceClaimIds(result)) {
      expect(ids.has(claimId)).toBe(true);
    }
  });
});
