pub mod bytes;
pub mod document;
pub mod grammar;
pub mod identity;
pub mod oracle;
pub mod relation;
pub mod trace;

use crate::definition::AgentDescriptor;

pub const DESCRIPTORS: [AgentDescriptor; 7] = [
    bytes::DEFINITION.descriptor(),
    grammar::DEFINITION.descriptor(),
    identity::DEFINITION.descriptor(),
    relation::DEFINITION.descriptor(),
    oracle::DEFINITION.descriptor(),
    document::DEFINITION.descriptor(),
    trace::DEFINITION.descriptor(),
];
