pub mod decision;
pub mod sink;
pub mod workers;

use std::collections::{BTreeMap, BTreeSet, VecDeque};

use serde::Serialize;
use thiserror::Error;

use crate::definition::{AgentDescriptor, AgentId};

#[derive(Debug, Clone, Copy, PartialEq, Eq, PartialOrd, Ord, Serialize)]
pub struct Edge {
    pub from: AgentId,
    pub to: AgentId,
}

impl Edge {
    pub const fn new(from: AgentId, to: AgentId) -> Self {
        Self { from, to }
    }
}

#[derive(Debug, Clone, Copy, Serialize)]
pub struct Organization {
    pub name: &'static str,
    pub shape: &'static str,
    pub sink: AgentId,
    pub nodes: &'static [AgentId],
    pub edges: &'static [Edge],
}

const EDGES: [Edge; 9] = [
    Edge::new(AgentId::Bytes, AgentId::Decide),
    Edge::new(AgentId::Grammar, AgentId::Decide),
    Edge::new(AgentId::Identity, AgentId::Decide),
    Edge::new(AgentId::Relation, AgentId::Decide),
    Edge::new(AgentId::Oracle, AgentId::Decide),
    Edge::new(AgentId::Document, AgentId::Decide),
    Edge::new(AgentId::Trace, AgentId::Decide),
    Edge::new(AgentId::Decide, AgentId::Literals),
    Edge::new(AgentId::Document, AgentId::Literals),
];

pub const AGENT_SWARM: Organization = Organization {
    name: "agent_swarm",
    shape: "dag",
    sink: AgentId::Literals,
    nodes: &AgentId::ALL,
    edges: &EDGES,
};

pub const DESCRIPTORS: [AgentDescriptor; 9] = [
    workers::bytes::DEFINITION.descriptor(),
    workers::grammar::DEFINITION.descriptor(),
    workers::identity::DEFINITION.descriptor(),
    workers::relation::DEFINITION.descriptor(),
    workers::oracle::DEFINITION.descriptor(),
    workers::document::DEFINITION.descriptor(),
    workers::trace::DEFINITION.descriptor(),
    decision::decide::DEFINITION.descriptor(),
    sink::literals::DEFINITION.descriptor(),
];

pub fn descriptor(id: AgentId) -> &'static AgentDescriptor {
    DESCRIPTORS
        .iter()
        .find(|definition| definition.id == id)
        .expect("every public AgentId has one descriptor")
}

impl Organization {
    pub fn validate(self) -> Result<(), OrganizationError> {
        let nodes = self.nodes.iter().copied().collect::<BTreeSet<_>>();
        if nodes.len() != self.nodes.len() {
            return Err(OrganizationError::DuplicateNode);
        }
        if !nodes.contains(&self.sink) {
            return Err(OrganizationError::UnknownSink(self.sink));
        }

        let mut edges = BTreeSet::new();
        let mut indegree = nodes
            .iter()
            .copied()
            .map(|node| (node, 0_usize))
            .collect::<BTreeMap<_, _>>();
        let mut successors = BTreeMap::<AgentId, Vec<AgentId>>::new();

        for edge in self.edges {
            if !nodes.contains(&edge.from) {
                return Err(OrganizationError::UnknownEndpoint(edge.from));
            }
            if !nodes.contains(&edge.to) {
                return Err(OrganizationError::UnknownEndpoint(edge.to));
            }
            if edge.from == edge.to {
                return Err(OrganizationError::SelfEdge(edge.from));
            }
            if !edges.insert(*edge) {
                return Err(OrganizationError::DuplicateEdge(*edge));
            }

            let source = descriptor(edge.from);
            let target = descriptor(edge.to);
            if !source
                .publishes
                .iter()
                .any(|capability| target.consumes.contains(capability))
            {
                return Err(OrganizationError::IncompatibleEdge(*edge));
            }

            *indegree
                .get_mut(&edge.to)
                .expect("edge endpoint was checked") += 1;
            successors.entry(edge.from).or_default().push(edge.to);
        }

        let mut queue = indegree
            .iter()
            .filter_map(|(node, degree)| (*degree == 0).then_some(*node))
            .collect::<VecDeque<_>>();
        let mut visited = 0_usize;

        while let Some(node) = queue.pop_front() {
            visited += 1;
            if let Some(next) = successors.get(&node) {
                for successor in next {
                    let degree = indegree
                        .get_mut(successor)
                        .expect("successor belongs to the organization");
                    *degree -= 1;
                    if *degree == 0 {
                        queue.push_back(*successor);
                    }
                }
            }
        }

        if visited != nodes.len() {
            return Err(OrganizationError::Cycle);
        }

        for node in nodes {
            if !reaches_sink(node, self.sink, &successors) {
                return Err(OrganizationError::CannotReachSink(node));
            }
        }

        Ok(())
    }

    pub fn topological_order(self) -> Result<Vec<AgentId>, OrganizationError> {
        self.validate()?;
        let mut indegree = self
            .nodes
            .iter()
            .copied()
            .map(|node| (node, 0_usize))
            .collect::<BTreeMap<_, _>>();
        let mut successors = BTreeMap::<AgentId, Vec<AgentId>>::new();
        for edge in self.edges {
            *indegree.get_mut(&edge.to).expect("validated edge endpoint") += 1;
            successors.entry(edge.from).or_default().push(edge.to);
        }
        for next in successors.values_mut() {
            next.sort_unstable();
        }

        let mut ready = indegree
            .iter()
            .filter_map(|(node, degree)| (*degree == 0).then_some(*node))
            .collect::<BTreeSet<_>>();
        let mut order = Vec::with_capacity(self.nodes.len());

        while let Some(node) = ready.pop_first() {
            order.push(node);
            if let Some(next) = successors.get(&node) {
                for successor in next {
                    let degree = indegree.get_mut(successor).expect("validated successor");
                    *degree -= 1;
                    if *degree == 0 {
                        ready.insert(*successor);
                    }
                }
            }
        }
        Ok(order)
    }
}

fn reaches_sink(
    start: AgentId,
    sink: AgentId,
    successors: &BTreeMap<AgentId, Vec<AgentId>>,
) -> bool {
    let mut queue = VecDeque::from([start]);
    let mut visited = BTreeSet::new();
    while let Some(node) = queue.pop_front() {
        if node == sink {
            return true;
        }
        if visited.insert(node) {
            queue.extend(successors.get(&node).into_iter().flatten().copied());
        }
    }
    false
}

#[derive(Debug, Clone, Copy, Error, PartialEq, Eq)]
pub enum OrganizationError {
    #[error("organization contains a duplicate node")]
    DuplicateNode,
    #[error("organization contains duplicate edge {0:?}")]
    DuplicateEdge(Edge),
    #[error("organization references unknown endpoint {0}")]
    UnknownEndpoint(AgentId),
    #[error("organization references unknown sink {0}")]
    UnknownSink(AgentId),
    #[error("organization contains self edge on {0}")]
    SelfEdge(AgentId),
    #[error("organization edge {0:?} has no published/consumed capability in common")]
    IncompatibleEdge(Edge),
    #[error("organization contains a cycle")]
    Cycle,
    #[error("agent {0} cannot reach the organization sink")]
    CannotReachSink(AgentId),
}

#[cfg(test)]
mod tests {
    use super::{AgentId, AGENT_SWARM, DESCRIPTORS};
    use std::collections::BTreeSet;

    #[test]
    fn published_organization_is_a_valid_dag() {
        let order = AGENT_SWARM.topological_order().unwrap();
        assert_eq!(order, AgentId::ALL.to_vec());
        let position = |agent| order.iter().position(|item| *item == agent).unwrap();
        assert!(position(AgentId::Decide) < position(AgentId::Literals));
        assert!(position(AgentId::Document) < position(AgentId::Literals));
    }

    #[test]
    fn every_agent_has_one_typed_definition_and_module() {
        assert_eq!(DESCRIPTORS.len(), AgentId::ALL.len());
        assert_eq!(
            DESCRIPTORS
                .iter()
                .map(|definition| definition.id)
                .collect::<BTreeSet<_>>(),
            AgentId::ALL.into_iter().collect()
        );
        assert!(DESCRIPTORS.iter().all(|definition| {
            definition.module.starts_with("organization::")
                && !definition.consumes.is_empty()
                && !definition.publishes.is_empty()
        }));
    }
}
