use std::{
    env,
    io::{self, Write},
    process, thread,
    time::Duration,
};

use catalog_agent_organization::{
    descriptor, Action, ActionFactory, ActionKind, AgentId, AGENT_SWARM,
};
use clap::{Parser, Subcommand};
use serde_json::{json, Map, Value};
use thiserror::Error;

#[derive(Debug, Parser)]
#[command(name = "catalog-agent", about = "Run one published agent definition")]
struct Cli {
    #[arg(long, global = true)]
    agent: Option<AgentId>,

    #[command(subcommand)]
    command: Command,
}

#[derive(Debug, Subcommand)]
enum Command {
    Describe,
    Topology,
    Emit {
        #[arg(long)]
        kind: ActionKind,
        #[arg(long)]
        trace_id: Option<String>,
        #[arg(long)]
        parent_action_id: Option<String>,
        #[arg(long, default_value = "{}")]
        payload: String,
    },
    Serve {
        #[arg(long)]
        trace_id: Option<String>,
        #[arg(long, default_value_t = 60)]
        heartbeat_seconds: u64,
        #[arg(long)]
        max_heartbeats: Option<u64>,
    },
}

fn main() {
    if let Err(error) = run() {
        eprintln!("catalog-agent: {error}");
        process::exit(1);
    }
}

fn run() -> Result<(), CliError> {
    let cli = Cli::parse();
    AGENT_SWARM.validate()?;
    match cli.command {
        Command::Topology => {
            AGENT_SWARM.validate()?;
            write_json(&AGENT_SWARM)?;
        }
        Command::Describe => {
            let agent = resolve_agent(cli.agent)?;
            write_json(descriptor(agent))?;
        }
        Command::Emit {
            kind,
            trace_id,
            parent_action_id,
            payload,
        } => {
            let agent = resolve_agent(cli.agent)?;
            let mut factory = ActionFactory::new(agent, resolve_trace_id(agent, trace_id))?;
            let payload = parse_payload(&payload)?;
            let action = factory.next(kind, parent_action_id, payload);
            write_action(&action)?;
        }
        Command::Serve {
            trace_id,
            heartbeat_seconds,
            max_heartbeats,
        } => {
            if heartbeat_seconds == 0 {
                return Err(CliError::HeartbeatInterval);
            }
            let agent = resolve_agent(cli.agent)?;
            serve(
                agent,
                resolve_trace_id(agent, trace_id),
                Duration::from_secs(heartbeat_seconds),
                max_heartbeats,
            )?;
        }
    }
    Ok(())
}

fn serve(
    agent: AgentId,
    trace_id: String,
    interval: Duration,
    max_heartbeats: Option<u64>,
) -> Result<(), CliError> {
    let definition = descriptor(agent);
    let mut factory = ActionFactory::new(agent, trace_id)?;
    let started = factory.next(
        ActionKind::Started,
        None,
        object(json!({
            "image": definition.image,
            "module": definition.module,
            "pid": process::id(),
        })),
    );
    write_action(&started)?;

    let ready = factory.next(
        ActionKind::Ready,
        Some(started.action_id),
        object(json!({
            "consumes": definition.consumes,
            "publishes": definition.publishes,
            "role": definition.role,
        })),
    );
    write_action(&ready)?;

    let mut parent = ready.action_id;
    let mut emitted = 0_u64;
    loop {
        if max_heartbeats.is_some_and(|limit| emitted >= limit) {
            let stopped = factory.next(
                ActionKind::Stopped,
                Some(parent),
                object(json!({"reason": "heartbeat-limit"})),
            );
            write_action(&stopped)?;
            return Ok(());
        }
        thread::sleep(interval);
        let heartbeat = factory.next(
            ActionKind::Heartbeat,
            Some(parent),
            object(json!({"ordinal": emitted})),
        );
        parent = heartbeat.action_id.clone();
        write_action(&heartbeat)?;
        emitted += 1;
    }
}

fn resolve_agent(cli: Option<AgentId>) -> Result<AgentId, CliError> {
    if let Some(agent) = cli {
        return Ok(agent);
    }
    let value = env::var("AGENT_ID").map_err(|_| CliError::MissingAgent)?;
    value.parse().map_err(CliError::UnknownAgent)
}

fn resolve_trace_id(agent: AgentId, cli: Option<String>) -> String {
    cli.or_else(|| env::var("TRACE_ID").ok())
        .unwrap_or_else(|| format!("{}-{}", agent, process::id()))
}

fn parse_payload(raw: &str) -> Result<Map<String, Value>, CliError> {
    serde_json::from_str::<Value>(raw)?
        .as_object()
        .cloned()
        .ok_or(CliError::Payload)
}

fn object(value: Value) -> Map<String, Value> {
    value
        .as_object()
        .cloned()
        .expect("json! object literal is an object")
}

fn write_action(action: &Action) -> Result<(), CliError> {
    action.validate()?;
    write_json(action)
}

fn write_json(value: &impl serde::Serialize) -> Result<(), CliError> {
    let stdout = io::stdout();
    let mut output = stdout.lock();
    serde_json::to_writer(&mut output, value)?;
    output.write_all(b"\n")?;
    output.flush()?;
    Ok(())
}

#[derive(Debug, Error)]
enum CliError {
    #[error("agent is required through --agent or AGENT_ID")]
    MissingAgent,
    #[error(transparent)]
    UnknownAgent(#[from] catalog_agent_organization::definition::UnknownAgent),
    #[error("payload must be a JSON object")]
    Payload,
    #[error("heartbeat interval must be greater than zero")]
    HeartbeatInterval,
    #[error(transparent)]
    Organization(#[from] catalog_agent_organization::organization::OrganizationError),
    #[error(transparent)]
    Action(#[from] catalog_agent_organization::action::ActionError),
    #[error(transparent)]
    Json(#[from] serde_json::Error),
    #[error(transparent)]
    Io(#[from] io::Error),
}
