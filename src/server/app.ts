import { Hono } from "hono";
import { createHash } from "node:crypto";
import type { CatalogConfig } from "../lib/config.js";
import { loadConfig } from "../lib/config.js";
import { cacheControlPublic, computeEtag, negotiateJson } from "../lib/http-cache.js";
import { normalizePatientInput } from "../lib/patient.js";
import { rankAgents } from "../lib/rank.js";
import { catalogAgentCard, listDomainIds, loadRegistryEntries } from "../lib/registry.js";
import {
  createFacilitator,
  decodeHeaderJson,
  encodeHeaderJson,
  paymentRequiredBody,
  type PaymentPayload,
  type SettlementResponse,
} from "../lib/x402.js";

export function createApp(config: CatalogConfig = loadConfig()) {
  const app = new Hono();
  const facilitator = createFacilitator(config.x402);

  function jsonResponse(
    req: { header: (n: string) => string | undefined },
    body: unknown,
    opts: { status?: number; cacheSeconds?: number; links?: string[]; paymentResponse?: SettlementResponse } = {},
  ): Response {
    const json = JSON.stringify(body, null, 2);
    const etag = computeEtag(json);
    const inm = req.header("if-none-match");
    const headers = new Headers({
      "Content-Type": "application/json; charset=utf-8",
      "Cache-Control": cacheControlPublic(opts.cacheSeconds ?? 60),
      ETag: etag,
    });
    for (const link of opts.links ?? []) {
      headers.append("Link", link);
    }
    if (opts.paymentResponse) {
      headers.set("X-PAYMENT-RESPONSE", encodeHeaderJson(opts.paymentResponse));
    }
    if (inm === etag && (opts.status ?? 200) === 200) {
      return new Response(null, { status: 304, headers });
    }
    return new Response(json, { status: opts.status ?? 200, headers });
  }

  app.get("/.well-known/agent-card.json", (c) => {
    const accept = c.req.header("accept");
    const neg = negotiateJson(accept);
    if (!neg.ok) return c.text("Not Acceptable", 406);
    const card = catalogAgentCard(config.publicBaseUrl);
    return jsonResponse(c.req, card, {
      cacheSeconds: 300,
      links: [
        `<${config.publicBaseUrl}/catalog/v1/index>; rel="index"`,
        `<${config.publicBaseUrl}/catalog/v1/domains>; rel="collection"`,
      ],
    });
  });

  app.get("/catalog/v1/index", (c) => {
    const neg = negotiateJson(c.req.header("accept"));
    if (!neg.ok) return c.text("Not Acceptable", 406);
    const index = {
      name: "Biomedical Agent Catalog",
      version: "0.1.0",
      domains: listDomainIds(),
      links: {
        agentCard: `${config.publicBaseUrl}/.well-known/agent-card.json`,
        domains: `${config.publicBaseUrl}/catalog/v1/domains`,
        rank: `${config.publicBaseUrl}/catalog/v1/rank`,
        a2a: `${config.publicBaseUrl}/a2a/v1`,
      },
      x402: {
        enabled: config.x402.enabled,
        paidOperations: config.x402.enabled ? ["POST /catalog/v1/rank"] : [],
      },
    };
    return jsonResponse(c.req, index, {
      links: [`<${config.publicBaseUrl}/.well-known/agent-card.json>; rel="describedby"`],
    });
  });

  app.get("/catalog/v1/domains", (c) => {
    const neg = negotiateJson(c.req.header("accept"));
    if (!neg.ok) return c.text("Not Acceptable", 406);
    const domains = listDomainIds().map((id) => ({
      domainId: id,
      agentCount: loadRegistryEntries(id).length,
      href: `${config.publicBaseUrl}/catalog/v1/domains/${id}/agents`,
    }));
    return jsonResponse(c.req, { domains });
  });

  app.get("/catalog/v1/domains/:domainId/agents", (c) => {
    const neg = negotiateJson(c.req.header("accept"));
    if (!neg.ok) return c.text("Not Acceptable", 406);
    const domainId = c.req.param("domainId");
    const agents = loadRegistryEntries(domainId).map((e) => ({
      registryId: e.registryId,
      agentCard: e.agentCard,
      href: `${config.publicBaseUrl}/catalog/v1/agents/${e.registryId}`,
    }));
    return jsonResponse(c.req, { domainId, agents });
  });

  app.get("/catalog/v1/agents/:registryId", (c) => {
    const neg = negotiateJson(c.req.header("accept"));
    if (!neg.ok) return c.text("Not Acceptable", 406);
    const registryId = c.req.param("registryId");
    const entry = loadRegistryEntries().find((e) => e.registryId === registryId);
    if (!entry) return c.json({ error: "not_found" }, 404);
    return jsonResponse(c.req, entry);
  });

  async function handleRank(c: import("hono").Context) {
    const neg = negotiateJson(c.req.header("accept"));
    if (!neg.ok) return c.text("Not Acceptable", 406);

    const resourceUrl = `${config.publicBaseUrl}/catalog/v1/rank`;
    let paymentResponse: SettlementResponse | undefined;

    if (config.x402.enabled) {
      const payHeader = c.req.header("x-payment");
      if (!payHeader) {
        const body = paymentRequiredBody(config.x402, resourceUrl);
        return jsonResponse(c.req, body, {
          status: 402,
          paymentResponse: { success: false, errorReason: "payment_required", network: config.x402.network },
        });
      }
      let payload: PaymentPayload;
      try {
        payload = decodeHeaderJson<PaymentPayload>(payHeader);
      } catch {
        return c.json({ error: "invalid_payment_header" }, 400);
      }
      const requirements = paymentRequiredBody(config.x402, resourceUrl).accepts[0]!;
      const verified = await facilitator.verify(payload, requirements);
      if (!verified.valid) {
        paymentResponse = {
          success: false,
          errorReason: verified.reason ?? "verification_failed",
          network: config.x402.network,
          payer: verified.payer,
          transaction: "",
        };
        const body = paymentRequiredBody(config.x402, resourceUrl, "Payment verification failed");
        return jsonResponse(c.req, body, { status: 402, paymentResponse });
      }
      paymentResponse = await facilitator.settle(payload, requirements);
      if (!paymentResponse.success) {
        const body = paymentRequiredBody(config.x402, resourceUrl, paymentResponse.errorReason ?? "settlement_failed");
        return jsonResponse(c.req, body, { status: 402, paymentResponse });
      }
    }

    const input = (await c.req.json()) as { domainId?: string; patient?: unknown; limit?: number };
    if (!input.domainId || input.patient === undefined) {
      return c.json({ error: "domainId and patient required" }, 400);
    }
    const patient = normalizePatientInput(input.patient);
    const result = rankAgents(input.domainId, patient, input.limit ?? 10);
    return jsonResponse(c.req, result, {
      paymentResponse,
      links: [`<${config.publicBaseUrl}/catalog/v1/index>; rel="index"`],
    });
  }

  app.post("/catalog/v1/rank", (c) => handleRank(c));

  app.post("/a2a/v1", async (c) => {
    const neg = negotiateJson(c.req.header("accept"));
    if (!neg.ok) return c.text("Not Acceptable", 406);
    const rpc = (await c.req.json()) as { jsonrpc?: string; id?: unknown; method?: string; params?: Record<string, unknown> };
    if (rpc.jsonrpc !== "2.0") {
      return c.json({ jsonrpc: "2.0", id: rpc.id ?? null, error: { code: -32600, message: "Invalid Request" } }, 400);
    }
    const id = rpc.id ?? null;
    try {
      if (rpc.method === "catalog/list") {
        const domainId = rpc.params?.domainId as string | undefined;
        const entries = loadRegistryEntries(domainId);
        return jsonResponse(c.req, { jsonrpc: "2.0", id, result: { agents: entries } });
      }
      if (rpc.method === "catalog/rank") {
        const domainId = rpc.params?.domainId as string;
        const patient = rpc.params?.patient;
        const limit = rpc.params?.limit as number | undefined;
        if (!domainId || patient === undefined) throw new Error("domainId and patient required");
        const normalized = normalizePatientInput(patient);
        const result = rankAgents(domainId, normalized, limit ?? 10);
        return jsonResponse(c.req, { jsonrpc: "2.0", id, result });
      }
      return jsonResponse(c.req, {
        jsonrpc: "2.0",
        id,
        error: { code: -32601, message: "Method not found" },
      });
    } catch (e) {
      return jsonResponse(c.req, {
        jsonrpc: "2.0",
        id,
        error: { code: -32000, message: (e as Error).message },
      });
    }
  });

  app.get("/health", (c) => c.json({ ok: true }));

  return app;
}

export function stableConfigFingerprint(config: CatalogConfig): string {
  return createHash("sha256").update(JSON.stringify(config.x402)).digest("hex").slice(0, 8);
}
