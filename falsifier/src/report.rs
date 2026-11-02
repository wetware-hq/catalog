//! Text report from `verifier/verify.py`. The falsifier does not reimplement predicates.

#[derive(Clone, Debug)]
pub struct Finding {
    pub id: String,
    pub ok: bool,
    pub rows: Vec<String>,
}

#[derive(Clone, Debug)]
pub struct Report {
    pub findings: Vec<Finding>,
    pub oracle_not_discharged: bool,
    pub result_pass: bool,
    pub saw_result: bool,
    pub trace_pass: Option<bool>,
    pub trace_code: Option<String>,
    pub trace_rows: Vec<String>,
}

#[derive(Clone, Copy)]
pub struct Expect {
    pub id: &'static str,
    pub ok: bool,
    pub row_contains: Option<&'static str>,
}

impl Expect {
    pub fn pass(id: &'static str) -> Self {
        Self {
            id,
            ok: true,
            row_contains: None,
        }
    }

    pub fn fail(id: &'static str) -> Self {
        Self {
            id,
            ok: false,
            row_contains: None,
        }
    }

    pub fn fail_row(id: &'static str, row_contains: &'static str) -> Self {
        Self {
            id,
            ok: false,
            row_contains: Some(row_contains),
        }
    }
}

pub fn parse_report(text: &str) -> Report {
    let mut report = Report {
        findings: Vec::new(),
        oracle_not_discharged: false,
        result_pass: false,
        saw_result: false,
        trace_pass: None,
        trace_code: None,
        trace_rows: Vec::new(),
    };
    let mut on_trace = false;
    for line in text.lines() {
        if let Some(rest) = line.strip_prefix("RESULT:") {
            report.saw_result = true;
            report.result_pass = rest.trim_start().starts_with("PASS");
            on_trace = false;
            continue;
        }
        if line.starts_with("[----]") {
            report.oracle_not_discharged = line.contains("NOT DISCHARGED");
            on_trace = false;
            continue;
        }
        if line.starts_with("      - ") {
            let row = line["      - ".len()..].to_string();
            if on_trace {
                report.trace_rows.push(row);
            } else if let Some(finding) = report.findings.last_mut() {
                finding.rows.push(row);
            }
            continue;
        }
        if let Some(rest) = line
            .strip_prefix("[PASS] ")
            .or_else(|| line.strip_prefix("[FAIL] "))
        {
            let pass = line.starts_with("[PASS]");
            if let Some(rest) = rest.strip_prefix("trace ") {
                on_trace = true;
                report.trace_pass = Some(pass);
                report.trace_code = rest.split_whitespace().next().map(str::to_string);
                continue;
            }
            on_trace = false;
            if let Some(id) = predicate_id(rest) {
                report.findings.push(Finding {
                    id,
                    ok: pass,
                    rows: Vec::new(),
                });
            }
        }
    }
    report
}

fn predicate_id(rest: &str) -> Option<String> {
    let token = if let Some(rest) = rest.strip_prefix("8.") {
        rest.split_whitespace().next()?
    } else if let Some(rest) = rest.strip_prefix("ext ") {
        rest.split_whitespace().next()?
    } else {
        return None;
    };
    Some(token.to_string())
}

pub fn judge(
    report: &Report,
    expects: &[Expect],
    absent: &[&str],
    result_pass: Option<bool>,
    oracle: bool,
) -> Result<(), String> {
    if !report.saw_result {
        return Err("harness: verifier report had no RESULT line".to_string());
    }
    let mut problems = Vec::new();
    if oracle && !report.oracle_not_discharged {
        problems.push("oracle line was not NOT DISCHARGED".to_string());
    }
    if let Some(want) = result_pass {
        if report.result_pass != want {
            problems.push(format!("RESULT pass={}: want {want}", report.result_pass));
        }
    }
    for expect in expects {
        match report
            .findings
            .iter()
            .find(|finding| finding.id == expect.id)
        {
            None => problems.push(format!("predicate {} absent", expect.id)),
            Some(finding) if finding.ok != expect.ok => problems.push(format!(
                "predicate {} ok={} want {} rows={:?}",
                expect.id, finding.ok, expect.ok, finding.rows
            )),
            Some(finding) => {
                if let Some(needle) = expect.row_contains {
                    if !finding.rows.iter().any(|row| row.contains(needle)) {
                        problems.push(format!(
                            "predicate {} rows missing {needle:?}: {:?}",
                            expect.id, finding.rows
                        ));
                    }
                }
            }
        }
    }
    for id in absent {
        if report.findings.iter().any(|finding| finding.id == *id) {
            problems.push(format!(
                "predicate {id} was present and should have stopped earlier"
            ));
        }
    }
    if problems.is_empty() {
        Ok(())
    } else {
        problems.push(summary(report));
        Err(problems.join("; "))
    }
}

pub fn judge_trace(
    report: &Report,
    pass: bool,
    code: &str,
    row_contains: Option<&str>,
) -> Result<(), String> {
    if !report.saw_result {
        return Err("harness: verifier report had no RESULT line".to_string());
    }
    let mut problems = Vec::new();
    match report.trace_code.as_deref() {
        Some(actual) if actual == code => {}
        Some(actual) => problems.push(format!("trace code {actual} want {code}")),
        None => problems.push("trace line absent".to_string()),
    }
    if report.trace_pass != Some(pass) {
        problems.push(format!("trace pass={:?} want {pass}", report.trace_pass));
    }
    if let Some(needle) = row_contains {
        if !report.trace_rows.iter().any(|row| row.contains(needle)) {
            problems.push(format!(
                "trace rows missing {needle:?}: {:?}",
                report.trace_rows
            ));
        }
    }
    if problems.is_empty() {
        Ok(())
    } else {
        Err(problems.join("; "))
    }
}

fn summary(report: &Report) -> String {
    report
        .findings
        .iter()
        .map(|finding| format!("{}:{}", finding.id, if finding.ok { "P" } else { "F" }))
        .collect::<Vec<_>>()
        .join(" ")
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn parses_a_failed_predicate_the_oracle_line_and_a_trace() {
        let graph = parse_report(
            "[FAIL] 8.7 (pure) aa: grammar and order\n      - pair: bad\n[----] 8.16 (oracle) NOT DISCHARGED - paper\n\nRESULT: FAIL\n",
        );
        assert_eq!(graph.findings[0].id, "7");
        assert!(!graph.findings[0].ok);
        assert_eq!(graph.findings[0].rows, vec!["pair: bad".to_string()]);
        assert!(graph.oracle_not_discharged);
        assert!(!graph.result_pass);

        let trace =
            parse_report("[FAIL] trace admit\n      - value:oracle: halt\n\nRESULT: FAIL\n");
        assert_eq!(trace.trace_code.as_deref(), Some("admit"));
        assert_eq!(trace.trace_pass, Some(false));
        assert!(trace.trace_rows[0].starts_with("value:oracle"));

        let ext = parse_report(
            "[PASS] ext E5 (pure-ext) Identity line\n\nRESULT: PASS (extension conditions only)\n",
        );
        assert_eq!(ext.findings[0].id, "E5");
        assert!(ext.findings[0].ok);
        assert!(ext.result_pass);
    }
}
