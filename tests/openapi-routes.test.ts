import { describe, expect, it } from "vitest";
import { readFileSync } from "node:fs";
import { repoPath } from "../src/lib/corpus.js";
import { CATALOG_HTTP_ROUTES, createApp } from "../src/server/app.js";
import { loadConfig } from "../src/lib/config.js";

function openApiPathKeys(): string[] {
  const yaml = readFileSync(repoPath("openapi", "catalog.openapi.yaml"), "utf8");
  const keys: string[] = [];
  for (const line of yaml.split("\n")) {
    const m = line.match(/^  (\/[^\s:]+):\s*$/);
    if (m) keys.push(m[1]!);
  }
  return keys.sort();
}

describe("OpenAPI ↔ HTTP server routes", () => {
  it("lists the same paths as CATALOG_HTTP_ROUTES", () => {
    const fromCode = CATALOG_HTTP_ROUTES.map((r) => r.path).sort();
    const fromOas = openApiPathKeys().map((p) => p.replace(/\{([^}]+)\}/g, ":$1"));
    expect(fromOas).toEqual(fromCode);
  });

  it("server responds on each documented route (no 404)", async () => {
    const app = createApp(loadConfig({ x402: { enabled: false } }));
    for (const route of CATALOG_HTTP_ROUTES) {
      const path = route.path
        .replace(":domainId", "peptides")
        .replace(":registryId", "peptide-evidence");
      const init: RequestInit = {
        method: route.method,
        headers: { Accept: "application/json" },
      };
      if (route.method === "POST" && route.path === "/catalog/v1/rank") {
        init.headers = { ...init.headers, "content-type": "application/json" };
        init.body = JSON.stringify({
          domainId: "peptides",
          patient: { id: "t", displayName: "T", clinicalGoals: ["obesity"] },
        });
      }
      if (route.method === "POST" && route.path === "/a2a/v1") {
        init.headers = { ...init.headers, "content-type": "application/json" };
        init.body = JSON.stringify({ jsonrpc: "2.0", id: 1, method: "catalog/list", params: {} });
      }
      const res = await app.request(path, init);
      expect(res.status, `${route.method} ${path}`).not.toBe(404);
    }
  });
});
