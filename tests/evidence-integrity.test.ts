import { describe, expect, it } from "vitest";
import { createHash } from "node:crypto";
import { readFileSync } from "node:fs";
import { repoPath } from "../src/lib/corpus.js";

describe("evidence corpus integrity", () => {
  it("matches peptide-claims.compact.sha256 sidecar", () => {
    const jsonPath = repoPath("data", "evidence", "peptide-claims.compact.json");
    const sidecarPath = repoPath("data", "evidence", "peptide-claims.compact.sha256");
    const json = readFileSync(jsonPath);
    const expected = createHash("sha256").update(json).digest("hex");
    const [recorded] = readFileSync(sidecarPath, "utf8").trim().split(/\s+/, 1);
    expect(recorded).toBe(expected);
  });
});
