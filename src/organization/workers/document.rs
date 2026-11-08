use crate::definition::{AgentDefinition, AgentId, Capability, Published, Role};

pub enum Agent {}

impl AgentDefinition for Agent {
    const ID: AgentId = AgentId::Document;
    const ROLE: Role = Role::Worker;
    const MODULE: &'static str = "organization::workers::document";
    const CONSUMES: &'static [Capability] =
        &[Capability::RepositoryTree, Capability::CheckerLiterals];
    const PUBLISHES: &'static [Capability] = &[Capability::DocumentVerdict];
}

pub const DEFINITION: Published<Agent> = Published::new();
