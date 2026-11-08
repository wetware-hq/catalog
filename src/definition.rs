use std::{fmt, marker::PhantomData, str::FromStr};

use serde::{Deserialize, Serialize};
use thiserror::Error;

#[derive(Debug, Clone, Copy, PartialEq, Eq, PartialOrd, Ord, Hash, Serialize, Deserialize)]
#[serde(rename_all = "kebab-case")]
pub enum AgentId {
    Bytes,
    Grammar,
    Identity,
    Relation,
    Oracle,
    Document,
    Trace,
    Decide,
    Literals,
}

impl AgentId {
    pub const ALL: [Self; 9] = [
        Self::Bytes,
        Self::Grammar,
        Self::Identity,
        Self::Relation,
        Self::Oracle,
        Self::Document,
        Self::Trace,
        Self::Decide,
        Self::Literals,
    ];

    pub const fn as_str(self) -> &'static str {
        match self {
            Self::Bytes => "bytes",
            Self::Grammar => "grammar",
            Self::Identity => "identity",
            Self::Relation => "relation",
            Self::Oracle => "oracle",
            Self::Document => "document",
            Self::Trace => "trace",
            Self::Decide => "decide",
            Self::Literals => "literals",
        }
    }
}

impl fmt::Display for AgentId {
    fn fmt(&self, formatter: &mut fmt::Formatter<'_>) -> fmt::Result {
        formatter.write_str(self.as_str())
    }
}

impl FromStr for AgentId {
    type Err = UnknownAgent;

    fn from_str(value: &str) -> Result<Self, Self::Err> {
        Self::ALL
            .into_iter()
            .find(|agent| agent.as_str() == value)
            .ok_or_else(|| UnknownAgent(value.to_owned()))
    }
}

#[derive(Debug, Clone, Error, PartialEq, Eq)]
#[error("unknown agent `{0}`")]
pub struct UnknownAgent(pub String);

#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "kebab-case")]
pub enum Role {
    Worker,
    Join,
    Sink,
}

pub const AGENT_IMAGE: &str = "ghcr.io/wetware-hq/catalog-agent:0.1.0";
pub const TRACER_IMAGE: &str = "ghcr.io/wetware-hq/catalog-tracer:0.1.0";

#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "kebab-case")]
pub enum Program {
    Agent,
}

impl Program {
    pub const fn image(self) -> &'static str {
        match self {
            Self::Agent => AGENT_IMAGE,
        }
    }
}

#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "kebab-case")]
pub enum Capability {
    CatalogueBytes,
    RepositoryTree,
    TraceStore,
    CheckerLiterals,
    BytesVerdict,
    GrammarVerdict,
    IdentityVerdict,
    RelationVerdict,
    OracleStatus,
    DocumentVerdict,
    TraceVerdict,
    Decision,
    PublishedLiterals,
}

#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize)]
pub struct AgentDescriptor {
    pub id: AgentId,
    pub role: Role,
    pub program: Program,
    pub image: &'static str,
    pub module: &'static str,
    pub consumes: &'static [Capability],
    pub publishes: &'static [Capability],
}

pub trait AgentDefinition: Send + Sync + 'static {
    const ID: AgentId;
    const ROLE: Role;
    const PROGRAM: Program = Program::Agent;
    const MODULE: &'static str;
    const CONSUMES: &'static [Capability];
    const PUBLISHES: &'static [Capability];
}

#[derive(Debug, Clone, Copy)]
pub struct Published<D: AgentDefinition>(PhantomData<D>);

impl<D: AgentDefinition> Published<D> {
    pub const fn new() -> Self {
        Self(PhantomData)
    }

    pub const fn descriptor(self) -> AgentDescriptor {
        AgentDescriptor {
            id: D::ID,
            role: D::ROLE,
            program: D::PROGRAM,
            image: D::PROGRAM.image(),
            module: D::MODULE,
            consumes: D::CONSUMES,
            publishes: D::PUBLISHES,
        }
    }
}

impl<D: AgentDefinition> Default for Published<D> {
    fn default() -> Self {
        Self::new()
    }
}

#[cfg(test)]
mod tests {
    use super::{AgentId, UnknownAgent};
    use std::str::FromStr;

    #[test]
    fn agent_ids_round_trip_through_the_published_wire_name() {
        for id in AgentId::ALL {
            assert_eq!(AgentId::from_str(id.as_str()), Ok(id));
        }
    }

    #[test]
    fn unknown_agent_is_typed() {
        assert_eq!(
            AgentId::from_str("missing"),
            Err(UnknownAgent("missing".to_owned()))
        );
    }
}
