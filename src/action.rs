use std::{
    fmt, process,
    str::FromStr,
    time::{SystemTime, UNIX_EPOCH},
};

use serde::{Deserialize, Serialize};
use serde_json::{Map, Value};
use thiserror::Error;

use crate::definition::AgentId;

pub const ACTION_SCHEMA: &str = "catalog.agent.action/v1";
pub const ORGANIZATION: &str = "agent_swarm";

#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "kebab-case")]
pub enum ActionKind {
    Started,
    Ready,
    Heartbeat,
    Accepted,
    Completed,
    Refused,
    Error,
    Stopped,
}

impl ActionKind {
    pub const ALL: [Self; 8] = [
        Self::Started,
        Self::Ready,
        Self::Heartbeat,
        Self::Accepted,
        Self::Completed,
        Self::Refused,
        Self::Error,
        Self::Stopped,
    ];

    pub const fn as_str(self) -> &'static str {
        match self {
            Self::Started => "started",
            Self::Ready => "ready",
            Self::Heartbeat => "heartbeat",
            Self::Accepted => "accepted",
            Self::Completed => "completed",
            Self::Refused => "refused",
            Self::Error => "error",
            Self::Stopped => "stopped",
        }
    }
}

impl fmt::Display for ActionKind {
    fn fmt(&self, formatter: &mut fmt::Formatter<'_>) -> fmt::Result {
        formatter.write_str(self.as_str())
    }
}

impl FromStr for ActionKind {
    type Err = UnknownActionKind;

    fn from_str(value: &str) -> Result<Self, Self::Err> {
        Self::ALL
            .into_iter()
            .find(|kind| kind.as_str() == value)
            .ok_or_else(|| UnknownActionKind(value.to_owned()))
    }
}

#[derive(Debug, Clone, Error, PartialEq, Eq)]
#[error("unknown action kind `{0}`")]
pub struct UnknownActionKind(pub String);

#[derive(Debug, Clone, PartialEq, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct Action {
    pub schema: String,
    pub action_id: String,
    pub trace_id: String,
    pub parent_action_id: Option<String>,
    pub organization: String,
    pub agent: AgentId,
    pub kind: ActionKind,
    pub sequence: u64,
    pub observed_at_unix_ms: u64,
    pub payload: Value,
}

impl Action {
    pub fn validate(&self) -> Result<(), ActionError> {
        if self.schema != ACTION_SCHEMA {
            return Err(ActionError::Schema(self.schema.clone()));
        }
        if self.organization != ORGANIZATION {
            return Err(ActionError::Organization(self.organization.clone()));
        }
        validate_token("action_id", &self.action_id)?;
        validate_token("trace_id", &self.trace_id)?;
        if let Some(parent) = &self.parent_action_id {
            validate_token("parent_action_id", parent)?;
            if parent == &self.action_id {
                return Err(ActionError::SelfParent);
            }
        }
        if !self.payload.is_object() {
            return Err(ActionError::Payload);
        }
        if self.sequence > i64::MAX as u64 {
            return Err(ActionError::SqlInteger("sequence"));
        }
        if self.observed_at_unix_ms > i64::MAX as u64 {
            return Err(ActionError::SqlInteger("observed_at_unix_ms"));
        }
        Ok(())
    }
}

#[derive(Debug)]
pub struct ActionFactory {
    agent: AgentId,
    trace_id: String,
    next_sequence: u64,
}

impl ActionFactory {
    pub fn new(agent: AgentId, trace_id: impl Into<String>) -> Result<Self, ActionError> {
        let trace_id = trace_id.into();
        validate_token("trace_id", &trace_id)?;
        Ok(Self {
            agent,
            trace_id,
            next_sequence: 0,
        })
    }

    pub fn next(
        &mut self,
        kind: ActionKind,
        parent_action_id: Option<String>,
        payload: Map<String, Value>,
    ) -> Action {
        let sequence = self.next_sequence;
        self.next_sequence += 1;
        let observed_at_unix_ms = now_unix_ms();
        let action_id = format!(
            "{}-{}-{}-{}",
            self.agent,
            process::id(),
            observed_at_unix_ms,
            sequence
        );
        Action {
            schema: ACTION_SCHEMA.to_owned(),
            action_id,
            trace_id: self.trace_id.clone(),
            parent_action_id,
            organization: ORGANIZATION.to_owned(),
            agent: self.agent,
            kind,
            sequence,
            observed_at_unix_ms,
            payload: Value::Object(payload),
        }
    }
}

fn now_unix_ms() -> u64 {
    SystemTime::now()
        .duration_since(UNIX_EPOCH)
        .expect("system clock is before the Unix epoch")
        .as_millis()
        .try_into()
        .expect("Unix timestamp does not fit u64")
}

fn validate_token(field: &'static str, value: &str) -> Result<(), ActionError> {
    if value.is_empty()
        || value.len() > 128
        || !value
            .bytes()
            .all(|byte| byte.is_ascii_alphanumeric() || b"._:/-".contains(&byte))
    {
        return Err(ActionError::Token {
            field,
            value: value.to_owned(),
        });
    }
    Ok(())
}

#[derive(Debug, Clone, Error, PartialEq, Eq)]
pub enum ActionError {
    #[error("unsupported action schema `{0}`")]
    Schema(String),
    #[error("unsupported organization `{0}`")]
    Organization(String),
    #[error("{field} is not a 1..128 byte action token: `{value}`")]
    Token { field: &'static str, value: String },
    #[error("an action cannot parent itself")]
    SelfParent,
    #[error("action payload must be a JSON object")]
    Payload,
    #[error("{0} exceeds the SQL INTEGER range")]
    SqlInteger(&'static str),
}

#[cfg(test)]
mod tests {
    use super::{ActionError, ActionFactory, ActionKind};
    use crate::definition::AgentId;
    use serde_json::{Map, Value};

    #[test]
    fn factory_emits_valid_sequenced_actions() {
        let mut factory = ActionFactory::new(AgentId::Bytes, "trace-1").unwrap();
        let first = factory.next(ActionKind::Started, None, Map::new());
        let second = factory.next(ActionKind::Ready, Some(first.action_id.clone()), Map::new());
        first.validate().unwrap();
        second.validate().unwrap();
        assert_eq!(first.sequence, 0);
        assert_eq!(second.sequence, 1);
        assert_eq!(
            second.parent_action_id.as_deref(),
            Some(first.action_id.as_str())
        );
    }

    #[test]
    fn scalar_payload_is_refused() {
        let mut factory = ActionFactory::new(AgentId::Bytes, "trace-1").unwrap();
        let mut action = factory.next(ActionKind::Started, None, Map::new());
        action.payload = Value::Bool(true);
        assert_eq!(action.validate(), Err(ActionError::Payload));
    }
}
