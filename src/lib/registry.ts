import { readFileSync, readdirSync, existsSync } from "node:fs";
import { join } from "node:path";
import type { AgentCard, CatalogRegistryEntry } from "../types/catalog.js";
import { repoPath } from "./paths.js";

const REGISTRY_ROOT = repoPath("registry");

export function listDomainIds(): string[] {
  const domainsDir = join(REGISTRY_ROOT, "domains");
  if (!existsSync(domainsDir)) return [];
  return readdirSync(domainsDir, { withFileTypes: true })
    .filter((d) => d.isDirectory())
    .map((d) => d.name)
    .sort();
}

export function loadRegistryEntries(domainId?: string): CatalogRegistryEntry[] {
  const domains = domainId ? [domainId] : listDomainIds();
  const entries: CatalogRegistryEntry[] = [];
  for (const domain of domains) {
    const dir = join(REGISTRY_ROOT, "domains", domain);
    if (!existsSync(dir)) continue;
    for (const file of readdirSync(dir).filter((f) => f.endsWith(".json"))) {
      const raw = JSON.parse(readFileSync(join(dir, file), "utf8")) as CatalogRegistryEntry;
      entries.push(raw);
    }
  }
  return entries.sort(
    (a, b) => (a.routing?.priority ?? 100) - (b.routing?.priority ?? 100),
  );
}

export function getRegistryEntry(registryId: string): CatalogRegistryEntry | undefined {
  return loadRegistryEntries().find((e) => e.registryId === registryId);
}

export function catalogAgentCard(baseUrl: string): AgentCard {
  return {
    name: "Wetware Biomedical Agent Catalog",
    description:
      "Decision-support catalog that ranks A2A peptide specialist agents from synthetic patient context. Not a prescriber.",
    version: "0.1.0",
    documentationUrl: "https://github.com/wetware-hq/catalog",
    provider: {
      organization: "Wetware (Mathew Chu)",
      url: "https://github.com/wetware-hq",
    },
    supportedInterfaces: [
      {
        url: `${baseUrl.replace(/\/$/, "")}/a2a/v1`,
        protocolBinding: "JSONRPC",
        protocolVersion: "1.0",
      },
    ],
    capabilities: {
      streaming: false,
      pushNotifications: false,
      extensions: [
        {
          uri: "https://wetware.health/catalog/v1/rank",
          description: "Rank registered agents for a patient context (HTTP POST mirror of JSON-RPC method)",
          required: false,
        },
      ],
    },
    defaultInputModes: ["application/json", "application/fhir+json"],
    defaultOutputModes: ["application/json"],
    skills: [
      {
        id: "catalog-rank",
        name: "Rank agents for patient",
        description:
          "Accepts FHIR R4 Bundle or wetware.simple.v1 JSON; returns ordered agent cards with relevance scores and clinical rationales.",
        tags: ["catalog", "routing", "peptides", "decision-support"],
        examples: [
          "Rank peptide agents for a synthetic patient with type 2 diabetes seeking weight management",
        ],
        inputModes: ["application/json", "application/fhir+json"],
        outputModes: ["application/json"],
      },
      {
        id: "catalog-list",
        name: "List registry entries",
        description: "Returns registered agent cards for a biomedical domain.",
        tags: ["catalog", "registry"],
      },
    ],
  };
}
