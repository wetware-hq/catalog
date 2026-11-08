use std::{
    ffi::OsStr,
    fs::{File, OpenOptions},
    io::{self, BufWriter, Write},
    path::{Path, PathBuf},
};

use thiserror::Error;

use crate::action::{Action, ActionError};

const SQL_SCHEMA: &str = include_str!("../sql/actions.sql");

pub struct Archive {
    jsonl: Option<BufWriter<File>>,
    sql: Option<BufWriter<File>>,
}

impl Archive {
    pub fn open(jsonl_path: Option<&Path>, sql_path: Option<&Path>) -> Result<Self, ArchiveError> {
        if jsonl_path.is_none() && sql_path.is_none() {
            return Err(ArchiveError::NoSink);
        }

        let jsonl = match jsonl_path {
            Some(path) => {
                require_extension(path, "jsonl")?;
                Some(open_append(path)?)
            }
            None => None,
        };

        let sql = match sql_path {
            Some(path) => {
                require_extension(path, "sql")?;
                let is_empty = path.metadata().map(|meta| meta.len() == 0).unwrap_or(true);
                let mut writer = open_append(path)?;
                if is_empty {
                    writer.write_all(SQL_SCHEMA.as_bytes())?;
                    if !SQL_SCHEMA.ends_with('\n') {
                        writer.write_all(b"\n")?;
                    }
                }
                Some(writer)
            }
            None => None,
        };

        Ok(Self { jsonl, sql })
    }

    pub fn archive_line(&mut self, line: &str) -> Result<Action, ArchiveError> {
        let action = parse_kubernetes_log_line(line)?;
        self.write(&action)?;
        Ok(action)
    }

    pub fn write(&mut self, action: &Action) -> Result<(), ArchiveError> {
        action.validate()?;

        if let Some(jsonl) = &mut self.jsonl {
            serde_json::to_writer(&mut *jsonl, action)?;
            jsonl.write_all(b"\n")?;
        }

        if let Some(sql) = &mut self.sql {
            let payload = serde_json::to_string(&action.payload)?;
            writeln!(
                sql,
                "INSERT OR IGNORE INTO agent_actions \
                 (action_id, trace_id, parent_action_id, organization, agent, kind, sequence, observed_at_unix_ms, payload_json) \
                 VALUES ({}, {}, {}, {}, {}, {}, {}, {}, {});",
                sql_string(&action.action_id),
                sql_string(&action.trace_id),
                action
                    .parent_action_id
                    .as_deref()
                    .map(sql_string)
                    .unwrap_or_else(|| "NULL".to_owned()),
                sql_string(&action.organization),
                sql_string(action.agent.as_str()),
                sql_string(action.kind.as_str()),
                action.sequence,
                action.observed_at_unix_ms,
                sql_string(&payload),
            )?;
        }

        Ok(())
    }

    pub fn flush(&mut self) -> Result<(), ArchiveError> {
        if let Some(jsonl) = &mut self.jsonl {
            jsonl.flush()?;
        }
        if let Some(sql) = &mut self.sql {
            sql.flush()?;
        }
        Ok(())
    }
}

pub fn parse_kubernetes_log_line(line: &str) -> Result<Action, ArchiveError> {
    let start = line
        .find('{')
        .ok_or_else(|| ArchiveError::NotAction(line.to_owned()))?;
    let action = serde_json::from_str::<Action>(line[start..].trim())?;
    action.validate()?;
    Ok(action)
}

fn open_append(path: &Path) -> Result<BufWriter<File>, ArchiveError> {
    if let Some(parent) = path
        .parent()
        .filter(|parent| !parent.as_os_str().is_empty())
    {
        std::fs::create_dir_all(parent)?;
    }
    let file = OpenOptions::new().create(true).append(true).open(path)?;
    Ok(BufWriter::new(file))
}

fn require_extension(path: &Path, required: &'static str) -> Result<(), ArchiveError> {
    if path.extension() != Some(OsStr::new(required)) {
        return Err(ArchiveError::Extension {
            path: path.to_path_buf(),
            required,
        });
    }
    Ok(())
}

fn sql_string(value: &str) -> String {
    format!("'{}'", value.replace('\'', "''"))
}

#[derive(Debug, Error)]
pub enum ArchiveError {
    #[error("at least one archive sink is required")]
    NoSink,
    #[error("archive path {path:?} must use .{required}")]
    Extension {
        path: PathBuf,
        required: &'static str,
    },
    #[error("Kubernetes log line does not contain an agent action: {0}")]
    NotAction(String),
    #[error(transparent)]
    Action(#[from] ActionError),
    #[error(transparent)]
    Json(#[from] serde_json::Error),
    #[error(transparent)]
    Io(#[from] io::Error),
}

#[cfg(test)]
mod tests {
    use std::{fs, path::PathBuf, process};

    use serde_json::Map;

    use super::{parse_kubernetes_log_line, Archive};
    use crate::{
        action::{ActionFactory, ActionKind},
        definition::AgentId,
    };

    fn temp_path(extension: &str) -> PathBuf {
        std::env::temp_dir().join(format!(
            "catalog-agent-archive-{}-{}.{}",
            process::id(),
            extension,
            extension
        ))
    }

    #[test]
    fn parses_kubectl_prefix_and_archives_both_formats() {
        let jsonl_path = temp_path("jsonl");
        let sql_path = temp_path("sql");
        let _ = fs::remove_file(&jsonl_path);
        let _ = fs::remove_file(&sql_path);

        let mut factory = ActionFactory::new(AgentId::Trace, "trace-1").unwrap();
        let action = factory.next(ActionKind::Completed, None, Map::new());
        let line = format!(
            "[pod/catalog trace] 2026-11-08T20:15:00Z {}",
            serde_json::to_string(&action).unwrap()
        );
        assert_eq!(parse_kubernetes_log_line(&line).unwrap(), action);

        let mut archive = Archive::open(Some(&jsonl_path), Some(&sql_path)).unwrap();
        archive.archive_line(&line).unwrap();
        archive.flush().unwrap();

        let jsonl = fs::read_to_string(&jsonl_path).unwrap();
        let sql = fs::read_to_string(&sql_path).unwrap();
        assert_eq!(
            serde_json::from_str::<crate::action::Action>(jsonl.trim()).unwrap(),
            action
        );
        assert!(sql.contains("CREATE TABLE IF NOT EXISTS agent_actions"));
        assert!(sql.contains("INSERT OR IGNORE INTO agent_actions"));

        fs::remove_file(jsonl_path).unwrap();
        fs::remove_file(sql_path).unwrap();
    }
}
