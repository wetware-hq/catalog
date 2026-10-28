import { describe, expect, it } from "vitest";
import { readFileSync } from "node:fs";
import { createApp } from "../src/server/app.js";
import { loadConfig } from "../src/lib/config.js";
import { mockPaymentHeader } from "../src/lib/x402.js";
import { repoPath } from "../src/lib/corpus.js";

describe("HTTP catalog", () => {
  const baseConfig = loadConfig({ port: 0, publicBaseUrl: "http://127.0.0.1:8787" });

  it("serves agent card with Link headers and ETag", async () => {
    const app = createApp(baseConfig);
    const res1 = await app.request("/.well-known/agent-card.json");
    expect(res1.status).toBe(200);
    expect(res1.headers.get("content-type")).toContain("application/json");
    expect(res1.headers.get("etag")).toBeTruthy();
    expect(res1.headers.get("link")).toContain("catalog/v1/index");
    const etag = res1.headers.get("etag");
    const res2 = await app.request("/.well-known/agent-card.json", {
      headers: { "if-none-match": etag! },
    });
    expect(res2.status).toBe(304);
  });

  it("returns 406 for unsupported Accept", async () => {
    const app = createApp(baseConfig);
    const res = await app.request("/catalog/v1/index", {
      headers: { Accept: "text/html" },
    });
    expect(res.status).toBe(406);
  });

  it("gates rank with x402 when enabled", async () => {
    const cfg = loadConfig({
      publicBaseUrl: "http://127.0.0.1:8787",
      x402: { enabled: true, facilitatorMode: "mock" },
    });
    const app = createApp(cfg);
    const patient = JSON.parse(
      readFileSync(repoPath("fixtures", "patients", "synthetic-t2dm-weight-simple.json"), "utf8"),
    );
    const body = JSON.stringify({ domainId: "peptides", patient, limit: 3 });

    const unpaid = await app.request("/catalog/v1/rank", {
      method: "POST",
      headers: { "content-type": "application/json" },
      body,
    });
    expect(unpaid.status).toBe(402);
    const pr = JSON.parse(await unpaid.text());
    expect(pr.x402Version).toBe(1);
    expect(pr.accepts[0].resource).toContain("/catalog/v1/rank");
    expect(unpaid.headers.get("x-payment-response")).toBeTruthy();

    const paid = await app.request("/catalog/v1/rank", {
      method: "POST",
      headers: {
        "content-type": "application/json",
        "x-payment": mockPaymentHeader(cfg.x402),
      },
      body,
    });
    expect(paid.status).toBe(200);
    expect(paid.headers.get("x-payment-response")).toBeTruthy();
    const ranked = JSON.parse(await paid.text());
    expect(ranked.rankedAgents.length).toBeGreaterThan(0);
  });

  it("rank is free when x402 disabled", async () => {
    const cfg = loadConfig({ x402: { enabled: false } });
    const app = createApp(cfg);
    const patient = JSON.parse(
      readFileSync(repoPath("fixtures", "patients", "synthetic-athlete-tendon-simple.json"), "utf8"),
    );
    const res = await app.request("/catalog/v1/rank", {
      method: "POST",
      headers: { "content-type": "application/json" },
      body: JSON.stringify({ domainId: "peptides", patient }),
    });
    expect(res.status).toBe(200);
  });
});
