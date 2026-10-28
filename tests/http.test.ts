import { describe, expect, it } from "vitest";
import { readFileSync } from "node:fs";
import { handleRequest, MAX_BODY_BYTES } from "../src/server.js";
import { loadConfig } from "../src/lib/config.js";
import { repoPath } from "../src/lib/corpus.js";

describe("primitive HTTP (3 routes)", () => {
  const config = loadConfig({ publicBaseUrl: "http://127.0.0.1:8787" });

  it("GET /health returns ok", () => {
    const res = handleRequest(config, "GET", "/health", Buffer.alloc(0));
    expect(res.status).toBe(200);
    expect(JSON.parse(res.body)).toEqual({ ok: true });
  });

  it("GET /.well-known/agent-card.json returns agent card", () => {
    const res = handleRequest(config, "GET", "/.well-known/agent-card.json", Buffer.alloc(0));
    expect(res.status).toBe(200);
    const card = JSON.parse(res.body);
    expect(card.name).toBeTruthy();
    expect(card.skills?.length).toBeGreaterThan(0);
  });

  it("POST /catalog/v1/rank returns ranked agents", () => {
    const patient = JSON.parse(
      readFileSync(repoPath("fixtures", "patients", "synthetic-athlete-tendon-simple.json"), "utf8"),
    );
    const body = Buffer.from(JSON.stringify({ domainId: "peptides", patient }));
    const res = handleRequest(config, "POST", "/catalog/v1/rank", body);
    expect(res.status).toBe(200);
    const ranked = JSON.parse(res.body);
    expect(ranked.rankedAgents.length).toBeGreaterThan(0);
    expect(ranked.domainId).toBe("peptides");
  });

  it("returns 400 for invalid rank body", () => {
    const res = handleRequest(config, "POST", "/catalog/v1/rank", Buffer.from("{"));
    expect(res.status).toBe(400);
    expect(JSON.parse(res.body).error).toBe("invalid_json");
    const bad = handleRequest(
      config,
      "POST",
      "/catalog/v1/rank",
      Buffer.from(JSON.stringify({ domainId: "peptides" })),
    );
    expect(bad.status).toBe(400);
    expect(JSON.parse(bad.body).error).toBe("invalid_request");
  });

  it("returns 404 for unknown route", () => {
    const res = handleRequest(config, "GET", "/catalog/v1/index", Buffer.alloc(0));
    expect(res.status).toBe(404);
  });

  it("returns 413 when body exceeds 64 KiB", () => {
    const res = handleRequest(config, "POST", "/catalog/v1/rank", Buffer.alloc(MAX_BODY_BYTES + 1));
    expect(res.status).toBe(413);
  });
});
