use std::path::PathBuf;
use std::process::ExitCode;

use falsifier::{campaign, AttackResult, Verdict, WORKERS};

fn main() -> ExitCode {
    let mut json = false;
    let mut only = None;
    let mut args = std::env::args().skip(1);
    while let Some(arg) = args.next() {
        match arg.as_str() {
            "--json" => json = true,
            "--worker" => match args.next() {
                Some(name) => only = Some(name),
                None => {
                    eprintln!("falsifier: --worker needs a name");
                    return ExitCode::from(2);
                }
            },
            "--help" | "-h" => {
                println!("falsifier [--json] [--worker {}]", WORKERS.join("|"));
                println!("exit 0 corroborated, 1 survivor, 2 harness error");
                return ExitCode::SUCCESS;
            }
            other => {
                eprintln!("falsifier: unknown argument {other}");
                return ExitCode::from(2);
            }
        }
    }

    let root = PathBuf::from(env!("CARGO_MANIFEST_DIR")).join("..");
    let root = root.canonicalize().unwrap_or(root);
    let results = campaign(&root, only.as_deref());
    if json {
        println!("{}", render_json(&results));
    } else {
        println!("falsifier: {} workers, one run, no vote", WORKERS.len());
        for result in &results {
            println!(
                "{:<10} {:<28} {}",
                result.worker,
                result.id,
                verdict_name(result.verdict)
            );
            if !result.detail.is_empty() {
                println!(
                    "           {}",
                    result.detail.replace('\n', "\n           ")
                );
            }
        }
        let corroborated = results
            .iter()
            .filter(|result| result.verdict == Verdict::Corroborated)
            .count();
        let falsified = results
            .iter()
            .filter(|result| result.verdict == Verdict::Falsified)
            .count();
        let errors = results
            .iter()
            .filter(|result| result.verdict == Verdict::Error)
            .count();
        println!("{corroborated} corroborated, {falsified} falsified, {errors} error");
    }

    if results
        .iter()
        .any(|result| result.verdict == Verdict::Error)
    {
        ExitCode::from(2)
    } else if results
        .iter()
        .any(|result| result.verdict == Verdict::Falsified)
    {
        ExitCode::from(1)
    } else {
        ExitCode::SUCCESS
    }
}

fn verdict_name(verdict: Verdict) -> &'static str {
    match verdict {
        Verdict::Corroborated => "corroborated",
        Verdict::Falsified => "falsified",
        Verdict::Error => "error",
    }
}

fn render_json(results: &[AttackResult]) -> String {
    let mut out = String::from("[\n");
    for (index, result) in results.iter().enumerate() {
        if index > 0 {
            out.push_str(",\n");
        }
        out.push_str("  {\"worker\": ");
        out.push_str(&json_string(result.worker));
        out.push_str(", \"id\": ");
        out.push_str(&json_string(result.id));
        out.push_str(", \"verdict\": ");
        out.push_str(&json_string(verdict_name(result.verdict)));
        out.push_str(", \"premise\": ");
        out.push_str(&json_string(result.premise));
        out.push_str(", \"prediction\": ");
        out.push_str(&json_string(result.prediction));
        out.push_str(", \"detail\": ");
        out.push_str(&json_string(&result.detail));
        out.push('}');
    }
    out.push_str("\n]\n");
    out
}

fn json_string(text: &str) -> String {
    let mut out = String::from("\"");
    for ch in text.chars() {
        match ch {
            '"' => out.push_str("\\\""),
            '\\' => out.push_str("\\\\"),
            '\n' => out.push_str("\\n"),
            '\r' => out.push_str("\\r"),
            '\t' => out.push_str("\\t"),
            c if (c as u32) < 0x20 => out.push_str(&format!("\\u{:04x}", c as u32)),
            c => out.push(c),
        }
    }
    out.push('"');
    out
}
