import type { NormalizedPatient, SimplePatient } from "../types/catalog.js";

function tokenize(text: string): string[] {
  return text
    .toLowerCase()
    .replace(/[^a-z0-9+/.-]+/g, " ")
    .split(/\s+/)
    .filter((t) => t.length > 1);
}

function buildTokens(p: Omit<NormalizedPatient, "tokens">): Set<string> {
  const parts = [
    ...p.conditions,
    ...p.clinicalGoals,
    ...p.allergies,
    ...p.medications,
    p.sex ?? "",
    p.countryCode,
    ...Object.keys(p.observations),
  ];
  return new Set(parts.flatMap(tokenize));
}

export function normalizeSimplePatient(raw: SimplePatient): NormalizedPatient {
  const flags = {
    competitiveAthlete: raw.flags?.competitiveAthlete ?? false,
    pregnantOrBreastfeeding: raw.flags?.pregnantOrBreastfeeding ?? false,
    seekingCompoundedPeptides: raw.flags?.seekingCompoundedPeptides ?? false,
  };
  const base: Omit<NormalizedPatient, "tokens"> = {
    source: "simple",
    id: raw.id,
    displayName: raw.displayName,
    ageYears: raw.ageYears,
    sex: raw.sex,
    countryCode: raw.countryCode ?? "AU",
    conditions: raw.conditions ?? [],
    clinicalGoals: raw.clinicalGoals ?? [],
    allergies: raw.allergies ?? [],
    medications: raw.medications ?? [],
    observations: raw.observations ?? {},
    flags,
  };
  return { ...base, tokens: buildTokens(base) };
}

type FhirResource = { resourceType: string; [key: string]: unknown };

function codingText(codeable: unknown): string[] {
  if (!codeable || typeof codeable !== "object") return [];
  const c = codeable as { text?: string; coding?: { display?: string; code?: string }[] };
  const out: string[] = [];
  if (c.text) out.push(c.text);
  for (const coding of c.coding ?? []) {
    if (coding.display) out.push(coding.display);
    if (coding.code) out.push(coding.code);
  }
  return out;
}

export function normalizeFhirBundle(bundle: FhirResource): NormalizedPatient {
  if (bundle.resourceType !== "Bundle") {
    throw new Error("FHIR patient input must be a Bundle resource");
  }
  const entries = (bundle.entry as { resource?: FhirResource }[] | undefined) ?? [];
  const resources = entries.map((e) => e.resource).filter(Boolean) as FhirResource[];

  const patient = resources.find((r) => r.resourceType === "Patient");
  if (!patient) throw new Error("FHIR Bundle must include a Patient resource");

  const names = (patient.name as { text?: string; family?: string; given?: string[] }[]) ?? [];
  const displayName =
    names[0]?.text ??
    [names[0]?.given?.join(" "), names[0]?.family].filter(Boolean).join(" ") ??
    "Synthetic Patient";

  const birthDate = patient.birthDate as string | undefined;
  let ageYears: number | undefined;
  if (birthDate) {
    const born = new Date(birthDate);
    ageYears = Math.floor((Date.now() - born.getTime()) / (365.25 * 24 * 3600 * 1000));
  }

  const gender = (patient.gender as string | undefined) ?? "unknown";
  const id = (patient.id as string) ?? "fhir-patient";

  const conditions: string[] = [];
  for (const r of resources) {
    if (r.resourceType === "Condition") {
      conditions.push(...codingText(r.code));
    }
  }

  const allergies: string[] = [];
  for (const r of resources) {
    if (r.resourceType === "AllergyIntolerance") {
      allergies.push(...codingText(r.code));
    }
  }

  const medications: string[] = [];
  for (const r of resources) {
    if (r.resourceType === "MedicationStatement") {
      const med = r.medicationCodeableConcept;
      medications.push(...codingText(med));
    }
  }

  const observations: Record<string, number> = {};
  for (const r of resources) {
    if (r.resourceType === "Observation") {
      const code = codingText(r.code).join(" ") || "observation";
      const val = r.valueQuantity as { value?: number } | undefined;
      if (typeof val?.value === "number") {
        observations[code.toLowerCase()] = val.value;
      }
    }
  }

  const clinicalGoals: string[] = [];
  for (const r of resources) {
    if (r.resourceType === "Goal") {
      clinicalGoals.push(...codingText(r.description));
    }
  }

  const auAddress = (
    (patient.address as { country?: string }[] | undefined) ?? []
  ).some((a) => (a.country ?? "").toUpperCase() === "AU");

  const base: Omit<NormalizedPatient, "tokens"> = {
    source: "fhir",
    id,
    displayName,
    ageYears,
    sex: gender,
    countryCode: auAddress ? "AU" : "AU",
    conditions,
    clinicalGoals,
    allergies,
    medications,
    observations,
    flags: {
      competitiveAthlete: clinicalGoals.some((g) => /athlete|sport|wada/i.test(g)),
      pregnantOrBreastfeeding: conditions.some((c) => /pregnan|lactat|breastfeed/i.test(c)),
      seekingCompoundedPeptides: clinicalGoals.some((g) => /compound|peptide/i.test(g)),
    },
  };

  return { ...base, tokens: buildTokens(base) };
}

export function normalizePatientInput(patient: unknown): NormalizedPatient {
  if (!patient || typeof patient !== "object") {
    throw new Error("patient must be an object");
  }
  const p = patient as Record<string, unknown>;
  if (p.resourceType === "Bundle") {
    return normalizeFhirBundle(p as FhirResource);
  }
  return normalizeSimplePatient(p as SimplePatient);
}
