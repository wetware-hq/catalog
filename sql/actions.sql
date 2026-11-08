PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS agent_actions (
  action_id TEXT PRIMARY KEY,
  trace_id TEXT NOT NULL,
  parent_action_id TEXT,
  organization TEXT NOT NULL,
  agent TEXT NOT NULL CHECK (
    agent IN (
      'bytes',
      'grammar',
      'identity',
      'relation',
      'oracle',
      'document',
      'trace',
      'decide',
      'literals'
    )
  ),
  kind TEXT NOT NULL CHECK (
    kind IN (
      'started',
      'ready',
      'heartbeat',
      'accepted',
      'completed',
      'refused',
      'error',
      'stopped'
    )
  ),
  sequence INTEGER NOT NULL CHECK (sequence >= 0),
  observed_at_unix_ms INTEGER NOT NULL CHECK (observed_at_unix_ms >= 0),
  payload_json TEXT NOT NULL CHECK (json_valid(payload_json))
);

CREATE INDEX IF NOT EXISTS agent_actions_trace_sequence
  ON agent_actions (trace_id, sequence);

CREATE INDEX IF NOT EXISTS agent_actions_parent
  ON agent_actions (parent_action_id);
