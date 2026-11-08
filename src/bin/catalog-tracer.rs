use std::{
    fs::File,
    io::{self, BufRead, BufReader},
    path::{Path, PathBuf},
    process::{Command as ProcessCommand, Stdio},
};

use catalog_agent_organization::archive::{Archive, ArchiveError};
use clap::{Parser, Subcommand};
use thiserror::Error;

#[derive(Debug, Parser)]
#[command(
    name = "catalog-tracer",
    about = "Archive structured agent actions from Kubernetes logs"
)]
struct Cli {
    #[arg(long, global = true)]
    jsonl: Option<PathBuf>,

    #[arg(long, global = true)]
    sql: Option<PathBuf>,

    #[arg(long, global = true)]
    skip_invalid: bool,

    #[command(subcommand)]
    source: Source,
}

#[derive(Debug, Subcommand)]
enum Source {
    Stdin,
    File {
        path: PathBuf,
    },
    Kubernetes {
        #[arg(long)]
        namespace: String,
        #[arg(long, default_value = "catalog.agent/component=agent")]
        selector: String,
        #[arg(long)]
        follow: bool,
        #[arg(long)]
        since: Option<String>,
        #[arg(long, default_value = "kubectl")]
        kubectl: PathBuf,
    },
}

fn main() {
    if let Err(error) = run() {
        eprintln!("catalog-tracer: {error}");
        std::process::exit(1);
    }
}

fn run() -> Result<(), TracerError> {
    let cli = Cli::parse();
    let mut archive = Archive::open(cli.jsonl.as_deref(), cli.sql.as_deref())?;

    match cli.source {
        Source::Stdin => {
            let stdin = io::stdin();
            archive_reader(stdin.lock(), &mut archive, cli.skip_invalid)?;
        }
        Source::File { path } => {
            let input = BufReader::new(File::open(path)?);
            archive_reader(input, &mut archive, cli.skip_invalid)?;
        }
        Source::Kubernetes {
            namespace,
            selector,
            follow,
            since,
            kubectl,
        } => {
            archive_kubernetes(
                &kubectl,
                &namespace,
                &selector,
                follow,
                since.as_deref(),
                &mut archive,
                cli.skip_invalid,
            )?;
        }
    }

    archive.flush()?;
    Ok(())
}

fn archive_reader(
    reader: impl BufRead,
    archive: &mut Archive,
    skip_invalid: bool,
) -> Result<(), TracerError> {
    for line in reader.lines() {
        let line = line?;
        if line.trim().is_empty() {
            continue;
        }
        if let Err(error) = archive.archive_line(&line) {
            if skip_invalid && is_invalid_line(&error) {
                eprintln!("catalog-tracer: skipped: {error}");
                continue;
            }
            return Err(error.into());
        }
    }
    Ok(())
}

#[allow(clippy::too_many_arguments)]
fn archive_kubernetes(
    kubectl: &Path,
    namespace: &str,
    selector: &str,
    follow: bool,
    since: Option<&str>,
    archive: &mut Archive,
    skip_invalid: bool,
) -> Result<(), TracerError> {
    let mut command = ProcessCommand::new(kubectl);
    command
        .arg("logs")
        .arg("--namespace")
        .arg(namespace)
        .arg("--selector")
        .arg(selector)
        .arg("--all-containers=true")
        .arg("--prefix=true")
        .arg("--timestamps=true")
        .arg("--tail=-1")
        .arg("--max-log-requests=32")
        .stdout(Stdio::piped())
        .stderr(Stdio::inherit());
    if follow {
        command.arg("--follow=true");
    }
    if let Some(since) = since {
        command.arg("--since").arg(since);
    }

    let mut child = command.spawn()?;
    let stdout = child.stdout.take().ok_or(TracerError::MissingStdout)?;
    archive_reader(BufReader::new(stdout), archive, skip_invalid)?;
    let status = child.wait()?;
    if !status.success() {
        return Err(TracerError::Kubectl(status.code()));
    }
    Ok(())
}

fn is_invalid_line(error: &ArchiveError) -> bool {
    matches!(
        error,
        ArchiveError::NotAction(_) | ArchiveError::Action(_) | ArchiveError::Json(_)
    )
}

#[derive(Debug, Error)]
enum TracerError {
    #[error("kubectl stdout was not piped")]
    MissingStdout,
    #[error("kubectl logs failed with exit code {0:?}")]
    Kubectl(Option<i32>),
    #[error(transparent)]
    Archive(#[from] ArchiveError),
    #[error(transparent)]
    Io(#[from] io::Error),
}

#[cfg(test)]
mod tests {
    use std::io::Cursor;

    use catalog_agent_organization::{
        action::{ActionFactory, ActionKind},
        definition::AgentId,
    };
    use serde_json::Map;

    use super::archive_reader;

    #[test]
    fn strict_reader_rejects_non_actions_and_lenient_reader_skips_them() {
        let mut factory = ActionFactory::new(AgentId::Bytes, "trace-1").unwrap();
        let action = factory.next(ActionKind::Ready, None, Map::new());
        let input = format!(
            "ordinary log\npod/bytes {}\n",
            serde_json::to_string(&action).unwrap()
        );

        let jsonl = std::env::temp_dir().join(format!(
            "catalog-tracer-reader-{}.jsonl",
            std::process::id()
        ));
        let _ = std::fs::remove_file(&jsonl);
        let mut archive =
            catalog_agent_organization::archive::Archive::open(Some(&jsonl), None).unwrap();
        assert!(archive_reader(Cursor::new(&input), &mut archive, false).is_err());
        archive_reader(Cursor::new(&input), &mut archive, true).unwrap();
        archive.flush().unwrap();
        assert_eq!(std::fs::read_to_string(&jsonl).unwrap().lines().count(), 1);
        std::fs::remove_file(jsonl).unwrap();
    }
}
