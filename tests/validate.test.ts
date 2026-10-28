import { describe, expect, it } from "vitest";
import { validateCatalog } from "../src/lib/registry.js";

describe("validateCatalog", () => {
  it("passes with no errors on seeded registry", () => {
    const issues = validateCatalog();
    const errors = issues.filter((i) => i.level === "error");
    expect(errors).toEqual([]);
  });
});
