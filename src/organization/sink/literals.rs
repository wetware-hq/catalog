use crate::definition::{AgentDefinition, AgentId, Capability, Published, Role};

pub enum Agent {}

impl AgentDefinition for Agent {
    const ID: AgentId = AgentId::Literals;
    const ROLE: Role = Role::Sink;
    const MODULE: &'static str = "organization::sink::literals";
    const CONSUMES: &'static [Capability] = &[Capability::Decision, Capability::DocumentVerdict];
    const PUBLISHES: &'static [Capability] = &[Capability::PublishedLiterals];
}

pub const DEFINITION: Published<Agent> = Published::new();
