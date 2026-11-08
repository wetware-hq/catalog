use crate::definition::{AgentDefinition, AgentId, Capability, Published, Role};

pub enum Agent {}

impl AgentDefinition for Agent {
    const ID: AgentId = AgentId::Relation;
    const ROLE: Role = Role::Worker;
    const MODULE: &'static str = "organization::workers::relation";
    const CONSUMES: &'static [Capability] = &[Capability::CatalogueBytes];
    const PUBLISHES: &'static [Capability] = &[Capability::RelationVerdict];
}

pub const DEFINITION: Published<Agent> = Published::new();
