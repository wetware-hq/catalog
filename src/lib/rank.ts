import { claimsById, claimsForSlug } from "./evidence.js";
import { getRegistryEntry, loadRegistryEntries } from "./registry.js";
import type {
  CatalogRegistryEntry,
  NormalizedPatient,
  RankResponse,
  RankedAgent,
} from "../types/catalog.js";

const DISCLAIMER =
  "Clinical decision support only — not prescribing advice. Rankings reflect rule-based matching of synthetic patient features to catalog metadata and verified peptide claim references. Verify regulatory status and contraindications before any clinical action.";

const GOAL_PEPTIDE_MAP: Record<string, { slugs: string[]; tags: string[] }> = {
  weight: { slugs: ["tirzepatide", "semaglutide", "liraglutide"], tags: ["metabolic", "glp1"] },
  obesity: { slugs: ["tirzepatide", "semaglutide"], tags: ["metabolic", "glp1"] },
  diabetes: { slugs: ["tirzepatide", "semaglutide", "liraglutide"], tags: ["metabolic", "t2dm"] },
  injury: { slugs: ["bpc-157", "tb-500"], tags: ["tissue-repair", "compounded"] },
  tendon: { slugs: ["bpc-157", "tb-500"], tags: ["tissue-repair"] },
  muscle: { slugs: ["bpc-157", "ipamorelin"], tags: ["recovery", "gh-axis"] },
  gh: { slugs: ["ipamorelin", "tesamorelin", "sermorelin"], tags: ["gh-axis"] },
  lipodystrophy: { slugs: ["tesamorelin"], tags: ["hiv", "artg"] },
  fertility: { slugs: ["kisspeptin-10"], tags: ["reproductive"] },
  skin: { slugs: ["ghk-cu", "palmitoyl-pentapeptide-4"], tags: ["cosmetic", "dermatology"] },
  antiaging: { slugs: ["ghk-cu", "epitalon"], tags: ["longevity"] },
};

function matchGoals(patient: NormalizedPatient): { slugs: Set<string>; tags: Set<string>; notes: string[] } {
  const slugs = new Set<string>();
  const tags = new Set<string>();
  const notes: string[] = [];
  const hay = [...patient.clinicalGoals, ...patient.conditions].join(" ").toLowerCase();
  for (const [key, mapping] of Object.entries(GOAL_PEPTIDE_MAP)) {
    if (hay.includes(key) || [...patient.tokens].some((t) => t.includes(key))) {
      mapping.slugs.forEach((s) => slugs.add(s));
      mapping.tags.forEach((t) => tags.add(t));
      notes.push(`Clinical theme "${key}" → peptides: ${mapping.slugs.join(", ")}`);
    }
  }
  return { slugs, tags, notes };
}

function skillTags(skillId: string, entry: CatalogRegistryEntry): string[] {
  const skill = entry.agentCard.skills.find((s) => s.id === skillId);
  return skill?.tags ?? [];
}

function scoreSkill(
  skillId: string,
  entry: CatalogRegistryEntry,
  patient: NormalizedPatient,
  themeTags: Set<string>,
  themeSlugs: Set<string>,
): { score: number; matches: RankedAgent["matchedSkills"][0]["matches"] } {
  const matches: RankedAgent["matchedSkills"][0]["matches"] = [];
  let score = 0;
  const tags = skillTags(skillId, entry);
  const routingTags = entry.routing?.indicationTags ?? [];

  for (const tag of routingTags) {
    if (themeTags.has(tag) || [...patient.tokens].some((t) => tag.includes(t) || t.includes(tag))) {
      score += 0.15;
      matches.push({
        kind: "indication",
        detail: `Patient context aligns with routing tag "${tag}"`,
        weight: 0.15,
      });
    }
  }

  for (const skillTag of tags) {
    if (themeTags.has(skillTag)) {
      score += 0.1;
      matches.push({
        kind: "skill-tag",
        detail: `Skill ${skillId} tag "${skillTag}" matches clinical theme`,
        weight: 0.1,
      });
    }
  }

  const slugs = entry.routing?.peptideSlugs ?? [];
  const overlap = slugs.filter((s) => themeSlugs.has(s));
  if (overlap.length) {
    score += Math.min(0.4, overlap.length * 0.12);
    matches.push({
      kind: "peptide-slug",
      detail: `Peptide focus overlap: ${overlap.join(", ")}`,
      weight: Math.min(0.4, overlap.length * 0.12),
    });
  }

  if (skillId.includes("regulatory") && patient.countryCode === "AU") {
    score += 0.2;
    matches.push({
      kind: "locale",
      detail: "Australian regulatory skill relevant (TGA / Poisons Standard / local context)",
      weight: 0.2,
    });
  }

  if (skillId.includes("wada") && patient.flags.competitiveAthlete) {
    score += 0.35;
    matches.push({
      kind: "athlete",
      detail: "Competitive athlete flag → WADA S0 / GHRP screening skill",
      weight: 0.35,
    });
  }

  if (skillId.includes("contraindication") || skillId.includes("safety")) {
    if (patient.allergies.length || patient.medications.length || patient.flags.pregnantOrBreastfeeding) {
      score += 0.25;
      matches.push({
        kind: "safety-input",
        detail: "Allergies, medications, or pregnancy flag present → safety screen prioritized",
        weight: 0.25,
      });
    }
  }

  if (skillId.includes("evidence")) {
    if (themeSlugs.size > 0) {
      score += 0.15;
      matches.push({
        kind: "evidence",
        detail: "Peptide themes identified → evidence summary skill",
        weight: 0.15,
      });
    }
  }

  if (skillId.includes("holistic") && themeSlugs.size > 0) {
    score += 0.2;
    matches.push({
      kind: "holistic",
      detail: "Active peptide clinical themes → holistic recommendation skill",
      weight: 0.2,
    });
  }

  return { score: Math.min(1, score), matches };
}

function regulatoryAlerts(patient: NormalizedPatient, slugs: Set<string>): string[] {
  const alerts: string[] = [];
  const byId = claimsById();

  if (patient.flags.seekingCompoundedPeptides) {
    alerts.push(
      "Patient flagged as seeking compounded peptides — verify TGA compounding exemptions, prescriber eligibility, and ARTG status before any supply pathway discussion.",
    );
  }

  for (const slug of slugs) {
    const claims = claimsForSlug(slug);
    for (const c of claims) {
      if (c.claim_type === "tga_artg_status" && c.verified && c.verdict === "not_found") {
        alerts.push(
          `[${slug}] Verified claim ${c.claim_id}: no TGA ARTG entry located (${c.verification_status}).`,
        );
      }
      if (c.claim_type === "wada_status" && c.verified && c.verdict === "supported" && patient.flags.competitiveAthlete) {
        alerts.push(
          `[${slug}] WADA prohibited-list match (${c.verification_status}, claim ${c.claim_id}) — athlete use may be prohibited.`,
        );
      }
      if (c.claim_type === "tga_poisons_schedule" && c.verified) {
        alerts.push(
          `[${slug}] Poisons Standard / SUSMP schedule claim available (${c.claim_id}, ${c.verification_status}). Review Appendix D context.`,
        );
      }
    }
    void byId;
  }
  return [...new Set(alerts)];
}

function contraindicationAlerts(patient: NormalizedPatient, entry: CatalogRegistryEntry): string[] {
  const alerts: string[] = [];
  if (patient.flags.pregnantOrBreastfeeding) {
    alerts.push("Pregnancy/breastfeeding flag — peptide safety data often limited; avoid GH-secretagogue routing.");
  }
  for (const tag of entry.routing?.contraindicationTags ?? []) {
    for (const cond of patient.conditions) {
      if (cond.toLowerCase().includes(tag) || tag.includes(cond.toLowerCase())) {
        alerts.push(`Condition "${cond}" matches contraindication tag "${tag}" for agent ${entry.registryId}.`);
      }
    }
  }
  return alerts;
}

function evidenceForSkill(entry: CatalogRegistryEntry, skillId: string) {
  const refs = entry.skillEvidence?.[skillId] ?? [];
  const byId = claimsById();
  return refs.map((r) => {
    const c = byId.get(r.claim_id);
    return {
      claim_id: r.claim_id,
      verification_status: r.verification_status,
      verified: r.verified,
      claim_type: c?.claim_type,
      slug: c?.slug,
    };
  });
}

export function rankAgents(domainId: string, patient: NormalizedPatient, limit = 10): RankResponse {
  const entries = loadRegistryEntries(domainId);
  if (!entries.length) {
    throw new Error(`No registry entries for domain "${domainId}"`);
  }

  const { slugs: themeSlugs, tags: themeTags, notes: themeNotes } = matchGoals(patient);
  const ranked: RankedAgent[] = [];

  for (const entry of entries) {
    const matchedSkills: RankedAgent["matchedSkills"] = [];
    let agentScore = 0;

    for (const skill of entry.agentCard.skills) {
      const { score, matches } = scoreSkill(skill.id, entry, patient, themeTags, themeSlugs);
      if (score <= 0 && matches.length === 0) continue;
      agentScore = Math.max(agentScore, score);
      matchedSkills.push({
        skillId: skill.id,
        skillScore: score,
        matches,
        evidenceRefs: evidenceForSkill(entry, skill.id),
      });
    }

    agentScore += (entry.routing?.priority ? (100 - entry.routing.priority) / 500 : 0);
    if (matchedSkills.length === 0) {
      agentScore = 0.05;
      matchedSkills.push({
        skillId: entry.agentCard.skills[0]?.id ?? "unknown",
        skillScore: 0.05,
        matches: [{ kind: "fallback", detail: "General peptide domain agent (weak match)", weight: 0.05 }],
        evidenceRefs: [],
      });
    }

    const featureMatches = themeNotes.map((n) => ({
      patientFeature: "clinicalGoals/conditions",
      matchedTo: n,
      effect: "increased peptide theme weight",
    }));

    for (const goal of patient.clinicalGoals) {
      featureMatches.push({
        patientFeature: `goal:${goal}`,
        matchedTo: entry.routing?.indicationTags?.join(", ") ?? entry.registryId,
        effect: "routing tag overlap",
      });
    }

    ranked.push({
      registryId: entry.registryId,
      relevanceScore: Math.min(1, Math.round(agentScore * 1000) / 1000),
      agentCard: entry.agentCard,
      matchedSkills: matchedSkills.sort((a, b) => b.skillScore - a.skillScore),
      rationale: {
        summary: buildSummary(entry, patient, themeSlugs, matchedSkills),
        featureMatches,
        regulatoryAlerts: regulatoryAlerts(patient, themeSlugs),
        contraindicationAlerts: contraindicationAlerts(patient, entry),
      },
    });
  }

  ranked.sort((a, b) => b.relevanceScore - a.relevanceScore);

  return {
    domainId,
    disclaimer: DISCLAIMER,
    patientSummary: {
      id: patient.id,
      displayName: patient.displayName,
      source: patient.source,
      countryCode: patient.countryCode,
      flags: patient.flags,
      inferredPeptideSlugs: [...themeSlugs],
      themeNotes,
    },
    rankedAgents: ranked.slice(0, limit),
  };
}

function buildSummary(
  entry: CatalogRegistryEntry,
  patient: NormalizedPatient,
  slugs: Set<string>,
  skills: RankedAgent["matchedSkills"],
): string {
  const top = skills[0];
  const slugPart = slugs.size ? ` Peptide themes: ${[...slugs].join(", ")}.` : "";
  const skillPart = top ? ` Top skill "${top.skillId}" (score ${top.skillScore}).` : "";
  const athlete = patient.flags.competitiveAthlete ? " Athlete flag elevates regulatory/WADA skills." : "";
  return `${entry.agentCard.name} matched for ${patient.displayName} (${patient.countryCode}).${slugPart}${skillPart}${athlete}`;
}

export function rankByRegistryId(registryId: string, patient: NormalizedPatient): RankedAgent | undefined {
  const entry = getRegistryEntry(registryId);
  if (!entry) return undefined;
  const res = rankAgents(entry.domainId, patient, 50);
  return res.rankedAgents.find((r) => r.registryId === registryId);
}

/*
 * References (third-party sources cited in regulatory routing and alerts):
 * [1] Therapeutic Goods Administration (TGA) — Australian Register of Therapeutic Goods (ARTG).
 *     https://www.tga.gov.au/resources/artg
 * [2] TGA Poisons Standard (Standard for the Uniform Scheduling of Medicines and Poisons, SUSMP),
 *     including Appendix D (e.g. instrument F2026L01327 as recorded on related claims).
 *     https://www.legislation.gov.au/F2026L01327
 * [3] World Anti-Doping Agency (WADA) Prohibited List (S0 / GHRP-related entries).
 *     https://www.wada-ama.org/en/resources/world-anti-doping-code-and-international-standards/prohibited-list
 */
