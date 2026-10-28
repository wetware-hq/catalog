/** A2A v1.0 AgentCard (required fields enforced at validate time). */
export type AgentInterface = {
  url: string;
  protocolBinding: "JSONRPC" | "GRPC" | "HTTP+JSON";
  protocolVersion: string;
};

export type AgentSkill = {
  id: string;
  name: string;
  description: string;
  tags: string[];
  examples?: string[];
  inputModes?: string[];
  outputModes?: string[];
};

export type AgentCard = {
  name: string;
  description: string;
  version: string;
  supportedInterfaces: AgentInterface[];
  capabilities: {
    streaming?: boolean;
    pushNotifications?: boolean;
    extendedAgentCard?: boolean;
    extensions?: { uri: string; description?: string; required?: boolean }[];
  };
  defaultInputModes: string[];
  defaultOutputModes: string[];
  skills: AgentSkill[];
  documentationUrl?: string;
  provider?: { organization: string; url?: string };
  securitySchemes?: Record<string, unknown>;
  securityRequirements?: Record<string, string[]>[];
};

export type CatalogRegistryEntry = {
  registryId: string;
  domainId: string;
  agentCard: AgentCard;
  routing?: {
    priority?: number;
    indicationTags?: string[];
    contraindicationTags?: string[];
    peptideSlugs?: string[];
  };
  skillEvidence?: Record<
    string,
    { claim_id: string; verification_status: string; verified: boolean }[]
  >;
};

export type SimplePatient = {
  format?: "catalog.simple.v1";
  id: string;
  displayName: string;
  ageYears?: number;
  sex?: "male" | "female" | "other" | "unknown";
  countryCode?: string;
  conditions?: string[];
  clinicalGoals?: string[];
  allergies?: string[];
  medications?: string[];
  observations?: Record<string, number>;
  flags?: {
    competitiveAthlete?: boolean;
    pregnantOrBreastfeeding?: boolean;
    seekingCompoundedPeptides?: boolean;
  };
};

export type NormalizedPatient = {
  source: "simple" | "fhir";
  id: string;
  displayName: string;
  ageYears?: number;
  sex?: string;
  countryCode: string;
  conditions: string[];
  clinicalGoals: string[];
  allergies: string[];
  medications: string[];
  observations: Record<string, number>;
  flags: {
    competitiveAthlete: boolean;
    pregnantOrBreastfeeding: boolean;
    seekingCompoundedPeptides: boolean;
  };
  tokens: Set<string>;
};

export type RankedAgent = {
  registryId: string;
  relevanceScore: number;
  agentCard: AgentCard;
  matchedSkills: {
    skillId: string;
    skillScore: number;
    matches: { kind: string; detail: string; weight: number }[];
    evidenceRefs: {
      claim_id: string;
      verification_status: string;
      verified: boolean;
      claim_type?: string;
      slug?: string;
    }[];
  }[];
  rationale: {
    summary: string;
    featureMatches: { patientFeature: string; matchedTo: string; effect: string }[];
    regulatoryAlerts: string[];
    contraindicationAlerts: string[];
  };
};

export type RankResponse = {
  domainId: string;
  disclaimer: string;
  patientSummary: Record<string, unknown>;
  rankedAgents: RankedAgent[];
};

export type CompactClaim = {
  claim_id: string;
  slug: string;
  peptide_name: string | null;
  claim_type: string;
  verification_status: string;
  verified: boolean;
  verdict: string;
  claim_text: string | null;
  authority: string | null;
  evidence_type: string | null;
  identifiers: Record<string, unknown>;
  resolution_note: string | null;
};

export type EvidenceCorpus = {
  summary: Record<string, unknown>;
  claims: CompactClaim[];
  by_slug: Record<string, string[]>;
};
