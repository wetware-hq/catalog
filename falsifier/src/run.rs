//! Invoke the committed verifier. Predictions are judged against its report, not a copy of it.

use std::fs;
use std::path::{Path, PathBuf};
use std::process::Command;
use std::sync::atomic::{AtomicU64, Ordering};

use crate::report::{self, Expect, Report};

static SEQ: AtomicU64 = AtomicU64::new(0);

pub struct TempDir(PathBuf);

impl TempDir {
    pub fn new(label: &str) -> Result<Self, String> {
        let n = SEQ.fetch_add(1, Ordering::Relaxed);
        let dir =
            std::env::temp_dir().join(format!("falsifier-{label}-{n}-{}", std::process::id()));
        fs::create_dir_all(&dir).map_err(|err| format!("harness: {err}"))?;
        Ok(TempDir(dir))
    }

    pub fn path(&self) -> &Path {
        &self.0
    }
}

impl Drop for TempDir {
    fn drop(&mut self) {
        let _ = fs::remove_dir_all(&self.0);
    }
}

pub struct CmdOut {
    pub code: i32,
    pub stdout: String,
    pub stderr: String,
}

pub fn python_args(args: &[String]) -> Result<CmdOut, String> {
    python(args)
}

fn python(args: &[String]) -> Result<CmdOut, String> {
    let output = Command::new("python3")
        .arg("-B")
        .args(args)
        .output()
        .map_err(|err| format!("harness: {err}"))?;
    Ok(CmdOut {
        code: output.status.code().unwrap_or(-1),
        stdout: String::from_utf8_lossy(&output.stdout).into_owned(),
        stderr: String::from_utf8_lossy(&output.stderr).into_owned(),
    })
}

fn verifier(root: &Path) -> PathBuf {
    root.join("verifier").join("verify.py")
}

fn report_from(cmd: CmdOut) -> Result<Report, String> {
    if !cmd.stdout.contains("RESULT:") {
        return Err(format!(
            "harness: verifier exit {} produced no RESULT\n{}{}",
            cmd.code, cmd.stdout, cmd.stderr
        ));
    }
    Ok(report::parse_report(&cmd.stdout))
}

pub fn verify_graph(root: &Path, bytes: &[u8], prev: Option<&[u8]>) -> Result<Report, String> {
    let dir = TempDir::new("graph")?;
    let graph = dir.path().join("graph.json");
    fs::write(&graph, bytes).map_err(|err| format!("harness: {err}"))?;
    let mut args = vec![verifier(root).to_string_lossy().into_owned()];
    if let Some(prev_bytes) = prev {
        let previous = dir.path().join("prev.json");
        fs::write(&previous, prev_bytes).map_err(|err| format!("harness: {err}"))?;
        args.push("--prev".to_string());
        args.push(previous.to_string_lossy().into_owned());
    }
    args.push(graph.to_string_lossy().into_owned());
    report_from(python(&args)?)
}

pub fn verify_repo(root: &Path, repo: &Path, graph: bool) -> Result<Report, String> {
    let mut args = vec![verifier(root).to_string_lossy().into_owned()];
    if graph {
        args.push(repo.join("graph.json").to_string_lossy().into_owned());
    }
    args.push("--repo".to_string());
    args.push(repo.to_string_lossy().into_owned());
    report_from(python(&args)?)
}

pub fn verify_trace(root: &Path, core: &Path, worker: &Path) -> Result<Report, String> {
    let args = vec![
        verifier(root).to_string_lossy().into_owned(),
        "--trace".to_string(),
        core.to_string_lossy().into_owned(),
        worker.to_string_lossy().into_owned(),
    ];
    report_from(python(&args)?)
}

pub fn merge(root: &Path, left: &[u8], right: &[u8]) -> Result<CmdOut, String> {
    let dir = TempDir::new("merge")?;
    let a = dir.path().join("a.json");
    let b = dir.path().join("b.json");
    fs::write(&a, left).map_err(|err| format!("harness: {err}"))?;
    fs::write(&b, right).map_err(|err| format!("harness: {err}"))?;
    let args = vec![
        verifier(root).to_string_lossy().into_owned(),
        "--merge".to_string(),
        a.to_string_lossy().into_owned(),
        b.to_string_lossy().into_owned(),
    ];
    python(&args)
}

pub fn judge_graph(
    root: &Path,
    bytes: &[u8],
    prev: Option<&[u8]>,
    expects: &[Expect],
    absent: &[&str],
    result_pass: Option<bool>,
) -> Result<(), String> {
    let report = verify_graph(root, bytes, prev)?;
    report::judge(&report, expects, absent, result_pass, true)
}

pub fn copy_repo(src: &Path, dst: &Path) -> Result<(), String> {
    fn walk(src: &Path, dst: &Path) -> Result<(), String> {
        fs::create_dir_all(dst).map_err(|err| format!("harness: {err}"))?;
        for entry in fs::read_dir(src).map_err(|err| format!("harness: {err}"))? {
            let entry = entry.map_err(|err| format!("harness: {err}"))?;
            let name = entry.file_name();
            let label = name.to_string_lossy();
            if matches!(
                label.as_ref(),
                ".git" | "target" | "__pycache__" | ".pytest_cache" | ".mypy_cache"
            ) {
                continue;
            }
            let kind = entry.file_type().map_err(|err| format!("harness: {err}"))?;
            let to = dst.join(&name);
            if kind.is_dir() {
                walk(&entry.path(), &to)?;
            } else if kind.is_file() {
                fs::copy(entry.path(), &to).map_err(|err| format!("harness: {err}"))?;
            }
        }
        Ok(())
    }
    walk(src, dst)
}

pub fn known_predicate(id: &str) -> bool {
    matches!(
        id,
        "1" | "2"
            | "3"
            | "4"
            | "5"
            | "6"
            | "7"
            | "8"
            | "8-scope"
            | "8-monomer"
            | "9"
            | "10"
            | "11"
            | "12"
            | "13"
            | "14"
            | "15"
            | "17"
            | "18"
            | "19"
            | "E1"
            | "E2"
            | "E4"
            | "E5"
            | "E6"
            | "E7"
    )
}
