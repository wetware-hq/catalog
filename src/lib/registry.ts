import { readFileSync, readdirSync, existsSync } from "node:fs";
import { join } from "node:path";
import type { AgentCard, CatalogRegistryEntry } from "../types/catalog.js";
import { claimsById, repoPath } from "./corpus.js";

export type ValidationIssue = {
  level: "error" | "warn";
  path: string;
  message: string;
};

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
  const root = baseUrl.replace(/\/$/, "");
  return {
    name: "Biomedical Agent Catalog",
    description:
      "Decision-support catalog that ranks A2A peptide specialist agents from synthetic patient context. Not a prescriber.",
    version: "0.1.0",
    documentationUrl: `${root}/docs/catalog`,
    provider: {
      organization: "Catalog project",
      url: root,
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
          uri: `${root}/catalog/v1/rank`,
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
          "Accepts FHIR R4 Bundle or catalog.simple.v1 JSON; returns ordered agent cards with relevance scores and clinical rationales.",
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

const REQUIRED_CARD = [
  "name",
  "description",
  "version",
  "supportedInterfaces",
  "capabilities",
  "defaultInputModes",
  "defaultOutputModes",
  "skills",
] as const;

function validateAgentCard(card: AgentCard, prefix: string): ValidationIssue[] {
  const issues: ValidationIssue[] = [];
  for (const key of REQUIRED_CARD) {
    if ((card as Record<string, unknown>)[key] === undefined) {
      issues.push({ level: "error", path: `${prefix}.${key}`, message: "missing required AgentCard field" });
    }
  }
  if (!card.supportedInterfaces?.length) {
    issues.push({ level: "error", path: `${prefix}.supportedInterfaces`, message: "must have ≥1 interface" });
  }
  for (const [i, iface] of (card.supportedInterfaces ?? []).entries()) {
    if (!iface.url?.startsWith("http")) {
      issues.push({ level: "error", path: `${prefix}.supportedInterfaces[${i}].url`, message: "invalid url" });
    }
    if (!["JSONRPC", "GRPC", "HTTP+JSON"].includes(iface.protocolBinding)) {
      issues.push({ level: "error", path: `${prefix}.supportedInterfaces[${i}].protocolBinding`, message: "invalid binding" });
    }
  }
  for (const [i, skill] of (card.skills ?? []).entries()) {
    for (const sk of ["id", "name", "description", "tags"] as const) {
      if ((skill as Record<string, unknown>)[sk] === undefined) {
        issues.push({ level: "error", path: `${prefix}.skills[${i}].${sk}`, message: "missing required AgentSkill field" });
      }
    }
  }
  return issues;
}

function validateRegistryEntry(entry: CatalogRegistryEntry, file: string): ValidationIssue[] {
  const issues: ValidationIssue[] = [];
  const prefix = file;
  if (!entry.registryId) issues.push({ level: "error", path: prefix, message: "missing registryId" });
  if (!entry.domainId) issues.push({ level: "error", path: prefix, message: "missing domainId" });
  issues.push(...validateAgentCard(entry.agentCard, `${prefix}.agentCard`));

  const byId = claimsById();
  for (const [skillId, refs] of Object.entries(entry.skillEvidence ?? {})) {
    if (!entry.agentCard.skills.some((s) => s.id === skillId)) {
      issues.push({ level: "warn", path: `${prefix}.skillEvidence.${skillId}`, message: "skill not on agent card" });
    }
    for (const ref of refs) {
      const claim = byId.get(ref.claim_id);
      if (!claim) {
        issues.push({ level: "error", path: `${prefix}.skillEvidence`, message: `unknown claim_id ${ref.claim_id}` });
      } else if (ref.verification_status !== claim.verification_status) {
        issues.push({
          level: "warn",
          path: `${prefix}.skillEvidence.${skillId}`,
          message: `verification_status drift for ${ref.claim_id} (registry vs corpus)`,
        });
      }
    }
  }
  return issues;
}

export function validateCatalog(): ValidationIssue[] {
  const issues: ValidationIssue[] = [];
  const schemasDir = repoPath("schemas");
  for (const name of [
    "a2a-agent-card.schema.json",
    "catalog-registry-entry.schema.json",
    "rank-request.schema.json",
    "rank-response.schema.json",
  ]) {
    if (!existsSync(join(schemasDir, name))) {
      issues.push({ level: "error", path: `schemas/${name}`, message: "missing schema file" });
    }
  }

  const evidencePath = repoPath("data", "evidence", "peptide-claims.compact.json");
  if (!existsSync(evidencePath)) {
    issues.push({ level: "error", path: evidencePath, message: "missing evidence corpus — run npm run build:evidence" });
  }

  const domainsDir = repoPath("registry", "domains");
  if (!existsSync(domainsDir)) {
    issues.push({ level: "error", path: domainsDir, message: "missing registry/domains" });
    return issues;
  }

  for (const domain of readdirSync(domainsDir, { withFileTypes: true }).filter((d) => d.isDirectory())) {
    const dir = join(domainsDir, domain.name);
    for (const file of readdirSync(dir).filter((f) => f.endsWith(".json"))) {
      const full = join(dir, file);
      try {
        const entry = JSON.parse(readFileSync(full, "utf8")) as CatalogRegistryEntry;
        issues.push(...validateRegistryEntry(entry, `registry/domains/${domain.name}/${file}`));
      } catch (e) {
        issues.push({ level: "error", path: full, message: `JSON parse error: ${(e as Error).message}` });
      }
    }
  }

  return issues;
}
