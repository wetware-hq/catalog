use crate::definition::{AgentDefinition, AgentId, Capability, Published, Role};

pub enum Agent {}

impl AgentDefinition for Agent {
    const ID: AgentId = AgentId::Decide;
    const ROLE: Role = Role::Join;
    const MODULE: &'static str = "organization::decision::decide";
    const CONSUMES: &'static [Capability] = &[
        Capability::BytesVerdict,
        Capability::GrammarVerdict,
        Capability::IdentityVerdict,
        Capability::RelationVerdict,
        Capability::OracleStatus,
        Capability::DocumentVerdict,
        Capability::TraceVerdict,
    ];
    const PUBLISHES: &'static [Capability] = &[Capability::Decision];
}

pub const DEFINITION: Published<Agent> = Published::new();
