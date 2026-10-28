import type { CatalogRegistryEntry, RankResponse } from "../types/catalog.js";
import type { ValidationIssue } from "../lib/validate.js";

export function formatList(domain: string, entries: CatalogRegistryEntry[]): string {
  const lines = [`Domain: ${domain}`, ""];
  for (const e of entries) {
    lines.push(`• ${e.registryId}`);
    lines.push(`  ${e.agentCard.name} (v${e.agentCard.version})`);
    lines.push(`  skills: ${e.agentCard.skills.map((s) => s.id).join(", ")}`);
    lines.push("");
  }
  return lines.join("\n");
}

export function formatShow(entry: CatalogRegistryEntry): string {
  const lines = [
    `${entry.registryId} [${entry.domainId}]`,
    entry.agentCard.name,
    entry.agentCard.description,
    "",
    "Interfaces:",
    ...entry.agentCard.supportedInterfaces.map(
      (i) => `  ${i.protocolBinding} ${i.protocolVersion} → ${i.url}`,
    ),
    "",
    "Skills:",
    ...entry.agentCard.skills.map((s) => `  - ${s.id}: ${s.name}`),
  ];
  if (entry.routing?.peptideSlugs?.length) {
    lines.push("", "Peptide slugs:", entry.routing.peptideSlugs.join(", "));
  }
  return lines.join("\n");
}

export function formatRank(result: RankResponse): string {
  const lines = [
    result.disclaimer,
    "",
    `Patient: ${result.patientSummary.displayName} (${result.patientSummary.id})`,
    `Inferred peptide themes: ${(result.patientSummary.inferredPeptideSlugs as string[]).join(", ") || "(none)"}`,
    "",
    "Ranked agents:",
  ];
  result.rankedAgents.forEach((a, i) => {
    lines.push(`${i + 1}. ${a.registryId}  score=${a.relevanceScore}`);
    lines.push(`   ${a.rationale.summary}`);
    const topSkill = a.matchedSkills[0];
    if (topSkill) {
      lines.push(`   top skill: ${topSkill.skillId} (${topSkill.skillScore})`);
      for (const m of topSkill.matches.slice(0, 3)) {
        lines.push(`     - [${m.kind}] ${m.detail}`);
      }
    }
    if (a.rationale.regulatoryAlerts.length) {
      lines.push("   regulatory:");
      for (const r of a.rationale.regulatoryAlerts.slice(0, 2)) {
        lines.push(`     ! ${r}`);
      }
    }
    if (a.rationale.contraindicationAlerts.length) {
      lines.push("   contraindications:");
      for (const r of a.rationale.contraindicationAlerts.slice(0, 2)) {
        lines.push(`     ! ${r}`);
      }
    }
    lines.push("");
  });
  return lines.join("\n");
}

export function formatValidate(issues: ValidationIssue[]): string {
  if (!issues.length) return "validate: OK";
  return issues.map((i) => `${i.level.toUpperCase()} ${i.path}: ${i.message}`).join("\n");
}
