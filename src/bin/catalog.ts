#!/usr/bin/env node
import { readFileSync } from "node:fs";
import { parseArgs } from "node:util";
import { serve } from "@hono/node-server";
import { loadConfig } from "../lib/config.js";
import { normalizePatientInput } from "../lib/patient.js";
import { rankAgents } from "../lib/rank.js";
import { getRegistryEntry, listDomainIds, loadRegistryEntries } from "../lib/registry.js";
import { validateCatalog } from "../lib/validate.js";
import { createApp } from "../server/app.js";
import { formatList, formatRank, formatShow, formatValidate } from "../cli/format.js";

const DISCLAIMER =
  "Decision support only — not prescribing advice. Synthetic fixtures only; no real PHI.";

function readPatientArg(path: string): unknown {
  return JSON.parse(readFileSync(path, "utf8"));
}

async function main() {
  const { values, positionals } = parseArgs({
    allowPositionals: true,
    options: {
      help: { type: "boolean", short: "h" },
      json: { type: "boolean" },
      domain: { type: "string", default: "peptides" },
      limit: { type: "string", default: "10" },
      patient: { type: "string" },
      port: { type: "string" },
      host: { type: "string" },
    },
  });

  const cmd = positionals[0];
  const json = values.json ?? false;

  if (values.help || !cmd) {
    console.log(`Wetware catalog CLI — ${DISCLAIMER}

Usage:
  catalog list [--domain peptides] [--json]
  catalog show <registryId> [--json]
  catalog rank --patient <file.json> [--domain peptides] [--limit N] [--json]
  catalog validate [--json]
  catalog serve [--port 8787] [--host 127.0.0.1]

Environment (serve / HTTP):
  CATALOG_X402_ENABLED=true|false (default false)
  CATALOG_X402_PAY_TO, CATALOG_X402_AMOUNT, CATALOG_X402_NETWORK, ...
  CATALOG_PUBLIC_BASE_URL=http://127.0.0.1:8787
`);
    process.exit(cmd ? 0 : 1);
  }

  if (cmd === "list") {
    const domain = values.domain!;
    const entries = loadRegistryEntries(domain);
    if (json) {
      console.log(JSON.stringify({ domainId: domain, agents: entries }, null, 2));
    } else {
      console.log(formatList(domain, entries));
    }
    return;
  }

  if (cmd === "show") {
    const id = positionals[1];
    if (!id) {
      console.error("Usage: catalog show <registryId>");
      process.exit(1);
    }
    const entry = getRegistryEntry(id);
    if (!entry) {
      console.error(`Unknown registryId: ${id}`);
      process.exit(1);
    }
    if (json) console.log(JSON.stringify(entry, null, 2));
    else console.log(formatShow(entry));
    return;
  }

  if (cmd === "rank") {
    const patientPath = values.patient;
    if (!patientPath) {
      console.error("Usage: catalog rank --patient fixtures/<file>.json");
      process.exit(1);
    }
    const raw = readPatientArg(patientPath);
    const patient = normalizePatientInput(raw);
    const result = rankAgents(values.domain!, patient, Number(values.limit));
    if (json) console.log(JSON.stringify(result, null, 2));
    else console.log(formatRank(result));
    return;
  }

  if (cmd === "validate") {
    const issues = validateCatalog();
    const errors = issues.filter((i) => i.level === "error");
    if (json) {
      console.log(JSON.stringify({ ok: errors.length === 0, issues }, null, 2));
    } else {
      console.log(formatValidate(issues));
    }
    process.exit(errors.length ? 1 : 0);
  }

  if (cmd === "serve") {
    const config = loadConfig({
      port: values.port ? Number(values.port) : undefined,
      host: values.host,
    });
    const app = createApp(config);
    console.error(`Catalog listening on http://${config.host}:${config.port}`);
    console.error(`Agent card: ${config.publicBaseUrl}/.well-known/agent-card.json`);
    console.error(`x402 rank gate: ${config.x402.enabled ? "enabled" : "disabled"}`);
    serve({ fetch: app.fetch, port: config.port, hostname: config.host });
    return;
  }

  console.error(`Unknown command: ${cmd}`);
  process.exit(1);
}

main().catch((e) => {
  console.error(e);
  process.exit(1);
});
