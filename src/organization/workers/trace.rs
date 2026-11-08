use crate::definition::{AgentDefinition, AgentId, Capability, Published, Role};

pub enum Agent {}

impl AgentDefinition for Agent {
    const ID: AgentId = AgentId::Trace;
    const ROLE: Role = Role::Worker;
    const MODULE: &'static str = "organization::workers::trace";
    const CONSUMES: &'static [Capability] = &[Capability::TraceStore, Capability::CheckerLiterals];
    const PUBLISHES: &'static [Capability] = &[Capability::TraceVerdict];
}

pub const DEFINITION: Published<Agent> = Published::new();
