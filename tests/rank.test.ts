import { describe, expect, it } from "vitest";
import { readFileSync } from "node:fs";
import { repoPath } from "../src/lib/paths.js";
import { normalizePatientInput } from "../src/lib/patient.js";
import { rankAgents } from "../src/lib/rank.js";

describe("rankAgents", () => {
  it("ranks regulatory agent highly for competitive athlete peptide seeker", () => {
    const raw = JSON.parse(
      readFileSync(repoPath("fixtures", "patients", "synthetic-athlete-tendon-simple.json"), "utf8"),
    );
    const patient = normalizePatientInput(raw);
    const result = rankAgents("peptides", patient, 5);
    expect(result.rankedAgents.length).toBeGreaterThan(0);
    const top = result.rankedAgents[0]!;
    expect(top.registryId).toMatch(/regulatory|clinical/);
    expect(result.patientSummary.inferredPeptideSlugs).toContain("bpc-157");
    const reg = result.rankedAgents.find((a) => a.registryId.includes("regulatory"));
    expect(reg?.rationale.regulatoryAlerts.some((a) => /WADA|ARTG|compounded/i.test(a))).toBe(true);
  });

  it("ranks metabolic agents for T2DM/obesity fixture", () => {
    const raw = JSON.parse(
      readFileSync(repoPath("fixtures", "patients", "synthetic-t2dm-weight-simple.json"), "utf8"),
    );
    const patient = normalizePatientInput(raw);
    const result = rankAgents("peptides", patient, 3);
    expect(result.patientSummary.inferredPeptideSlugs).toEqual(
      expect.arrayContaining(["tirzepatide", "semaglutide"]),
    );
  });

  it("parses FHIR bundle fixture", () => {
    const raw = JSON.parse(
      readFileSync(repoPath("fixtures", "patients", "synthetic-fertility-fhir.json"), "utf8"),
    );
    const patient = normalizePatientInput(raw);
    expect(patient.source).toBe("fhir");
    const result = rankAgents("peptides", patient, 5);
    expect(result.patientSummary.inferredPeptideSlugs).toContain("kisspeptin-10");
  });
});
