import { createServer, type IncomingMessage, type ServerResponse } from "node:http";
import { readFileSync } from "node:fs";
import Ajv2020Import from "ajv/dist/2020.js";

const Ajv2020 = Ajv2020Import as unknown as new (opts?: object) => import("ajv/dist/2020.js").default;
import type { CatalogConfig } from "./lib/config.js";
import { loadConfig } from "./lib/config.js";
import { repoPath } from "./lib/corpus.js";
import { normalizePatientInput } from "./lib/patient.js";
import { loadEvidenceCorpus } from "./lib/corpus.js";
import { loadRegistryEntries } from "./lib/registry.js";
import { rank } from "./lib/rank.js";
import { catalogAgentCard } from "./lib/registry.js";

export const MAX_BODY_BYTES = 64 * 1024;

const ROUTES: Record<string, Set<string>> = {
  "/.well-known/agent-card.json": new Set(["GET"]),
  "/health": new Set(["GET"]),
  "/catalog/v1/rank": new Set(["POST"]),
};

const ajv = new Ajv2020({ allErrors: true, strict: false });
for (const file of ["a2a-agent-card.schema.json", "rank-request.schema.json", "rank-response.schema.json"]) {
  ajv.addSchema(JSON.parse(readFileSync(repoPath("schemas", file), "utf8")));
}
const validateRankRequest = ajv.getSchema("rank-request.schema.json")!;
const validateRankResponse = ajv.getSchema("rank-response.schema.json")!;

function json(status: number, body: unknown): { status: number; body: string } {
  return { status, body: JSON.stringify(body) };
}

export function handleRequest(
  config: CatalogConfig,
  method: string,
  path: string,
  rawBody: Buffer,
): { status: number; body: string; headers?: Record<string, string> } {
  const pathname = path.split("?")[0]!;
  const verb = method.toUpperCase();
  const allowed = ROUTES[pathname];
  if (!allowed) return json(404, { error: "not_found" });
  if (!allowed.has(verb)) {
    return {
      ...json(405, { error: "method_not_allowed" }),
      headers: { Allow: [...allowed].join(", ") },
    };
  }

  if (pathname === "/health") return json(200, { ok: true });
  if (pathname === "/.well-known/agent-card.json") {
    return json(200, catalogAgentCard(config.publicBaseUrl));
  }

  if (rawBody.length > MAX_BODY_BYTES) return json(413, { error: "payload_too_large" });
  let parsed: unknown;
  try {
    parsed = rawBody.length ? JSON.parse(rawBody.toString("utf8")) : null;
  } catch {
    return json(400, { error: "invalid_json" });
  }
  if (!validateRankRequest(parsed)) return json(400, { error: "invalid_request" });
  try {
    const input = parsed as { domainId: string; patient: unknown; limit?: number };
    const domainId = input.domainId;
    const patient = normalizePatientInput(input.patient);
    const result = rank(patient, loadRegistryEntries(domainId), loadEvidenceCorpus(), {
      domainId,
      limit: input.limit ?? 10,
    });
    if (!validateRankResponse(result)) return json(500, { error: "internal_error" });
    return json(200, result);
  } catch {
    return json(500, { error: "internal_error" });
  }
}

async function readBody(req: IncomingMessage): Promise<Buffer> {
  const chunks: Buffer[] = [];
  let size = 0;
  for await (const chunk of req) {
    const buf = Buffer.isBuffer(chunk) ? chunk : Buffer.from(chunk);
    size += buf.length;
    if (size > MAX_BODY_BYTES) {
      req.destroy();
      throw new Error("payload_too_large");
    }
    chunks.push(buf);
  }
  return Buffer.concat(chunks as readonly Uint8Array[]);
}

function write(res: ServerResponse, status: number, body: string, extraHeaders?: Record<string, string>): void {
  res.statusCode = status;
  res.setHeader("Content-Type", "application/json; charset=utf-8");
  for (const [k, v] of Object.entries(extraHeaders ?? {})) res.setHeader(k, v);
  res.end(body);
}

export function createCatalogServer(config: CatalogConfig = loadConfig()) {
  return createServer(async (req, res) => {
    try {
      const host = req.headers.host ?? `${config.host}:${config.port}`;
      const url = new URL(req.url ?? "/", `http://${host}`);
      const hasBody = req.method !== "GET" && req.method !== "HEAD";
      let raw = Buffer.alloc(0);
      if (hasBody) {
        try {
          raw = Buffer.from(await readBody(req));
        } catch (e) {
          if ((e as Error).message === "payload_too_large") {
            write(res, 413, JSON.stringify({ error: "payload_too_large" }));
            return;
          }
          throw e;
        }
      }
      const out = handleRequest(config, req.method ?? "GET", url.pathname, raw);
      write(res, out.status, out.body, out.headers);
    } catch {
      write(res, 500, JSON.stringify({ error: "internal_error" }));
    }
  });
}

/*
 * References:
 * [1] JSON Schema draft 2020-12 — rank-request / rank-response validation.
 *     https://json-schema.org/draft/2020-12/json-schema-core
 * [2] Node.js HTTP module. https://nodejs.org/api/http.html
 */
