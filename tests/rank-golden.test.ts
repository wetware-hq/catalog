import { describe, expect, it } from "vitest";
import { readFileSync } from "node:fs";
import { repoPath } from "../src/lib/corpus.js";
import { stableStringify } from "../src/lib/stable-json.js";
import { rankFixture } from "./helpers/rank-fixture.js";

const FIXTURES = [
  { patient: "synthetic-athlete-tendon-simple.json", golden: "synthetic-athlete-tendon-simple.rank.json", limit: 10 },
  { patient: "synthetic-t2dm-weight-simple.json", golden: "synthetic-t2dm-weight-simple.rank.json", limit: 10 },
  { patient: "synthetic-fertility-fhir.json", golden: "synthetic-fertility-fhir.rank.json", limit: 10 },
] as const;

describe("rank golden outputs", () => {
  for (const { patient, golden, limit } of FIXTURES) {
    it(`matches committed golden for ${patient}`, () => {
      const result = rankFixture(patient, limit);
      const expected = readFileSync(repoPath("tests", "goldens", "rank", golden), "utf8");
      expect(stableStringify(result)).toBe(expected);
    });
  }
});
