use crate::definition::{AgentDefinition, AgentId, Capability, Published, Role};

pub enum Agent {}

impl AgentDefinition for Agent {
    const ID: AgentId = AgentId::Grammar;
    const ROLE: Role = Role::Worker;
    const MODULE: &'static str = "organization::workers::grammar";
    const CONSUMES: &'static [Capability] =
        &[Capability::CatalogueBytes, Capability::CheckerLiterals];
    const PUBLISHES: &'static [Capability] = &[Capability::GrammarVerdict];
}

pub const DEFINITION: Published<Agent> = Published::new();
