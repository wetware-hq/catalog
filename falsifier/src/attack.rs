//! Independent workers. They share no verdict and do not vote.
//!
//! Each attack names a premise and the observation that premise forbids, then asks the
//! committed verifier. `agent.swarm` is not a spec of this run. A header that says so is
//! one of the attacks.

use std::collections::BTreeMap;
use std::fs;
use std::path::Path;

use crate::canon::{binders, canonical_bytes, catalogue, empty_binder, Value};
use crate::report::{self, Expect};
use crate::run::{self, TempDir};

pub const WORKERS: &[&str] = &[
    "bytes", "grammar", "identity", "relation", "oracle", "document", "trace",
];

const BANNER: &str =
    "\u{26a0}\u{fe0f} ACADEMIC RESEARCH PURPOSES ONLY; NOT FOR MEDICAL USE WITHOUT LICENSED OVERSIGHT";

const COMPACT: &[u8] = b"{\"version\":2,\"pair\":{},\"preclinical\":{}}\n";
const SWAPPED: &[u8] = b"{\n  \"version\": 2,\n  \"preclinical\": {},\n  \"pair\": {}\n}\n";
const DUP_VERSION: &[u8] =
    b"{\n  \"version\": 2,\n  \"version\": 2,\n  \"pair\": {},\n  \"preclinical\": {}\n}\n";
const NULL_PAIR: &[u8] = b"{\n  \"version\": 2,\n  \"pair\": null,\n  \"preclinical\": {}\n}\n";

#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub enum Verdict {
    Corroborated,
    Falsified,
    Error,
}

pub struct AttackResult {
    pub worker: &'static str,
    pub id: &'static str,
    pub premise: &'static str,
    pub prediction: &'static str,
    pub verdict: Verdict,
    pub detail: String,
}

pub fn campaign(root: &Path, only: Option<&str>) -> Vec<AttackResult> {
    let specs: &[(&str, fn(&Path) -> Vec<AttackResult>)] = &[
        ("bytes", bytes),
        ("grammar", grammar),
        ("identity", identity),
        ("relation", relation),
        ("oracle", oracle),
        ("document", document),
        ("trace", trace),
    ];
    if let Some(name) = only {
        if !specs.iter().any(|(worker, _)| *worker == name) {
            return vec![finish(
                "harness",
                "worker",
                "the worker name is one of the seven",
                "an unknown name is a harness error",
                Err(format!("harness: unknown worker {name}")),
            )];
        }
    }
    let mut handles = Vec::new();
    for &(name, func) in specs {
        if let Some(wanted) = only {
            if wanted != name {
                continue;
            }
        }
        let root = root.to_path_buf();
        handles.push(std::thread::spawn(move || func(&root)));
    }
    let mut out = Vec::new();
    for handle in handles {
        match handle.join() {
            Ok(mut rows) => out.append(&mut rows),
            Err(_) => out.push(finish(
                "harness",
                "panic",
                "a worker returns its attacks",
                "the worker does not panic",
                Err("harness: worker panicked".to_string()),
            )),
        }
    }
    out.sort_by(|left, right| (&left.worker, &left.id).cmp(&(&right.worker, &right.id)));
    out
}

fn bytes(root: &Path) -> Vec<AttackResult> {
    let worker = "bytes";
    let empty = empty_catalogue();
    let base = base_catalogue();
    vec![
        graph(
            root,
            worker,
            "empty-holds",
            "the five-line empty catalogue is valid",
            "predicates 1-15, 17, and 18 pass",
            &empty,
            None,
            &[Expect::pass("6"), Expect::pass("18")],
            &[],
            Some(true),
        ),
        graph(
            root,
            worker,
            "base-holds",
            "one canonical aa row is a valid catalogue",
            "the pure predicates pass and 16 stays open",
            &base,
            None,
            &[Expect::pass("4"), Expect::pass("6")],
            &[],
            Some(true),
        ),
        graph(
            root,
            worker,
            "utf8-rejected",
            "invalid UTF-8 is not repaired",
            "predicate 1 fails and parsing does not continue",
            &bad_utf8(&empty),
            None,
            &[Expect::fail("1")],
            &["3", "6"],
            Some(false),
        ),
        graph(
            root,
            worker,
            "overlong-utf8",
            "an overlong UTF-8 sequence is not a character",
            "predicate 1 fails",
            &overlong(&empty),
            None,
            &[Expect::fail("1")],
            &["6"],
            Some(false),
        ),
        graph(
            root,
            worker,
            "nul-is-utf8",
            "NUL is a UTF-8 code unit and is still not JSON",
            "predicate 1 passes and predicate 3 fails",
            &with_nul(&empty),
            None,
            &[Expect::pass("1"), Expect::fail("3")],
            &["6"],
            Some(false),
        ),
        graph(
            root,
            worker,
            "bom",
            "a UTF-8 BOM is not part of the catalogue",
            "predicate 1 passes and predicate 3 fails",
            &bom(&empty),
            None,
            &[Expect::pass("1"), Expect::fail("3")],
            &["6"],
            Some(false),
        ),
        graph(
            root,
            worker,
            "missing-newline",
            "exactly one final newline is required",
            "predicate 2 fails",
            &empty[..empty.len() - 1],
            None,
            &[Expect::fail("2")],
            &[],
            Some(false),
        ),
        graph(
            root,
            worker,
            "extra-newline",
            "a second trailing newline is not canonical",
            "predicate 2 fails",
            &extra_newline(&empty),
            None,
            &[Expect::fail("2")],
            &[],
            Some(false),
        ),
        graph(
            root,
            worker,
            "crlf",
            "CRLF is not the default byte convention",
            "predicate 2 fails",
            &crlf(&empty),
            None,
            &[Expect::fail("2")],
            &[],
            Some(false),
        ),
        graph(
            root,
            worker,
            "compact-empty",
            "a compact empty catalogue is not the empty catalogue",
            "predicates 6 and 18 fail",
            COMPACT,
            None,
            &[Expect::fail("6"), Expect::fail("18")],
            &[],
            Some(false),
        ),
        graph(
            root,
            worker,
            "swapped-root-keys",
            "reordering root keys does not change the members",
            "predicate 3 passes; predicates 6 and 18 fail",
            SWAPPED,
            None,
            &[Expect::pass("3"), Expect::fail("6"), Expect::fail("18")],
            &[],
            Some(false),
        ),
        graph(
            root,
            worker,
            "duplicate-version-key",
            "a repeated JSON key is not a second version",
            "predicate 3 sees one version and predicate 6 fails",
            DUP_VERSION,
            None,
            &[Expect::pass("3"), Expect::fail("6")],
            &[],
            Some(false),
        ),
        version_attack(
            root,
            "version-string",
            "\"2\"",
            "version is the number 2, not the string 2",
            "predicate 4 fails and the bytes can still be canonical for that string",
        ),
        version_attack(
            root,
            "version-float",
            "2.0",
            "version is the integer 2, not 2.0",
            "predicate 4 fails and predicate 6 still passes",
        ),
        version_attack(
            root,
            "version-bool",
            "true",
            "version is not a boolean",
            "predicate 4 fails and predicate 6 still passes",
        ),
        graph(
            root,
            worker,
            "rank-root",
            "a stored rank is a forbidden write and an extra root key",
            "predicates 3 and 17 fail; predicate 6 passes on the sorted object",
            &extra_root("rank", Value::Int(1)),
            None,
            &[Expect::fail("3"), Expect::fail("17"), Expect::pass("6")],
            &[],
            Some(false),
        ),
        graph(
            root,
            worker,
            "note-root",
            "predicate 17 is the named denylist; predicate 3 rejects any other root key",
            "predicate 3 fails, predicate 17 passes, and predicate 6 passes",
            &extra_root("note", Value::Str("x".to_string())),
            None,
            &[Expect::fail("3"), Expect::pass("17"), Expect::pass("6")],
            &[],
            Some(false),
        ),
        graph(
            root,
            worker,
            "null-dictionary",
            "a null dictionary is not an object",
            "predicate 5 fails; canonical bytes of null can still match",
            NULL_PAIR,
            None,
            &[Expect::fail("5"), Expect::pass("6")],
            &[],
            Some(false),
        ),
        committed_holds(root),
        committed_one_space(root),
    ]
}

fn grammar(root: &Path) -> Vec<AttackResult> {
    let worker = "grammar";
    vec![
        row(
            root,
            worker,
            "decreasing-segments",
            "aa segments out of byte order are invalid, not a sorting task",
            "predicate 7 fails and predicate 6 still passes",
            &[("aa:KK/ACD", "uniprot:P12345", &["pmid:1"][..])],
            &[Expect::fail("7"), Expect::pass("6")],
            Some(false),
        ),
        row(
            root,
            worker,
            "repeated-segments-hold",
            "a repeated segment is a multiset member",
            "aa:ACD/ACD passes predicate 7",
            &[("aa:ACD/ACD", "uniprot:P12345", &["pmid:1"])],
            &[Expect::pass("7")],
            Some(true),
        ),
        row(
            root,
            worker,
            "cyrillic-residue",
            "a lookalike letter is not the residue alphabet",
            "predicate 7 fails",
            &[("aa:\u{0410}CD", "uniprot:P12345", &["pmid:1"])],
            &[Expect::fail("7")],
            Some(false),
        ),
        row(
            root,
            worker,
            "pmid-zero-holds",
            "pmid:0 is the grammar's zero, not a padded identifier",
            "predicate 10 passes",
            &[("aa:ACD", "uniprot:P12345", &["pmid:0"])],
            &[Expect::pass("10")],
            Some(true),
        ),
        row(
            root,
            worker,
            "pmid-leading-zero",
            "pmid:01 is not pmid:1",
            "predicate 10 fails",
            &[("aa:ACD", "uniprot:P12345", &["pmid:01"])],
            &[Expect::fail("10")],
            Some(false),
        ),
        row(
            root,
            worker,
            "isoform-holds",
            "uniprot:P12345-1 is a distinct well-formed target",
            "predicate 9 passes",
            &[("aa:ACD", "uniprot:P12345-1", &["pmid:1"])],
            &[Expect::pass("9")],
            Some(true),
        ),
        row(
            root,
            worker,
            "isoform-leading-zero",
            "an isoform suffix does not take a leading zero",
            "predicates 9 and 12 fail",
            &[("aa:ACD", "uniprot:P12345-01", &["pmid:1"])],
            &[Expect::fail("9"), Expect::fail("12")],
            Some(false),
        ),
        row(
            root,
            worker,
            "chem-scope",
            "a CHEM block is out of scope and is not a monomer error",
            "8-scope fails; predicate 8 and 8-monomer pass",
            &[("helm:CHEM1{CCO}$$$$", "uniprot:P12345", &["pmid:1"])],
            &[
                Expect::pass("8"),
                Expect::fail("8-scope"),
                Expect::pass("8-monomer"),
            ],
            Some(false),
        ),
        row(
            root,
            worker,
            "rna-scope",
            "an RNA block is the same scope refusal",
            "8-scope fails and 8-monomer passes",
            &[("helm:RNA1{R(A)}$$$$", "uniprot:P12345", &["pmid:1"])],
            &[Expect::fail("8-scope"), Expect::pass("8-monomer")],
            Some(false),
        ),
        row(
            root,
            worker,
            "smiles-monomer",
            "[CCO] inside PEPTIDE is a monomer refusal, not a scope refusal",
            "8-monomer fails; predicate 8 and 8-scope pass",
            &[("helm:PEPTIDE1{[CCO]}$$$$", "uniprot:P12345", &["pmid:1"])],
            &[
                Expect::pass("8"),
                Expect::pass("8-scope"),
                Expect::fail("8-monomer"),
            ],
            Some(false),
        ),
        row(
            root,
            worker,
            "empty-monomers",
            "an empty monomer list is not a peptide",
            "8-monomer fails",
            &[("helm:PEPTIDE1{}$$$$", "uniprot:P12345", &["pmid:1"])],
            &[Expect::fail("8-monomer")],
            Some(false),
        ),
        row(
            root,
            worker,
            "control-character",
            "a control character in HELM is ill-formed, not a scope or monomer class",
            "predicate 8 fails; 8-scope and 8-monomer pass",
            &[(&control_helm(), "uniprot:P12345", &["pmid:1"])],
            &[
                Expect::fail("8"),
                Expect::pass("8-scope"),
                Expect::pass("8-monomer"),
            ],
            Some(false),
        ),
        row(
            root,
            worker,
            "leading-zero-index",
            "a polymer index has no leading zero",
            "predicate 8 fails; scope and monomer stay passing",
            &[("helm:PEPTIDE01{A}$$$$", "uniprot:P12345", &["pmid:1"])],
            &[
                Expect::fail("8"),
                Expect::pass("8-scope"),
                Expect::pass("8-monomer"),
            ],
            Some(false),
        ),
        row(
            root,
            worker,
            "doi-citation",
            "a citation is bare pmid digits",
            "predicate 10 fails",
            &[("aa:ACD", "uniprot:P12345", &["doi:10.1/x"])],
            &[Expect::fail("10")],
            Some(false),
        ),
        row(
            root,
            worker,
            "binder-uses-target-prefix",
            "prefixes do not cross roles",
            "predicate 14 fails",
            &[("uniprot:P12345", "uniprot:P99999", &["pmid:1"])],
            &[Expect::fail("14")],
            Some(false),
        ),
        row(
            root,
            worker,
            "target-uses-citation-prefix",
            "a pmid is not a target",
            "predicates 9, 12, and 14 fail",
            &[("aa:ACD", "pmid:1", &["pmid:1"])],
            &[Expect::fail("9"), Expect::fail("12"), Expect::fail("14")],
            Some(false),
        ),
    ]
}

fn identity(root: &Path) -> Vec<AttackResult> {
    let worker = "identity";
    vec![
        row(
            root,
            worker,
            "helm-index-alias",
            "polymer index digits do not make a second molecule",
            "predicate 13 fails and predicate 8 passes",
            &[
                ("helm:PEPTIDE1{A.C.D}$$$$", "uniprot:P12345", &["pmid:1"]),
                ("helm:PEPTIDE2{A.C.D}$$$$", "uniprot:P99999", &["pmid:2"]),
            ],
            &[Expect::fail("13"), Expect::pass("8")],
            Some(false),
        ),
        row(
            root,
            worker,
            "aa-helm-same-chain",
            "a plain L-chain HELM is the same molecule as aa:, and only aa: is valid",
            "predicate 13 fails",
            &[
                ("aa:ACD", "uniprot:P12345", &["pmid:1"]),
                ("helm:PEPTIDE1{A.C.D}$$$$", "uniprot:P99999", &["pmid:2"]),
            ],
            &[Expect::fail("13")],
            Some(false),
        ),
        row(
            root,
            worker,
            "unsorted-multiset",
            "two aa strings with one sorted multiset are one molecule",
            "predicates 7 and 13 fail",
            &[
                ("aa:ACD/KK", "uniprot:P12345", &["pmid:1"]),
                ("aa:KK/ACD", "uniprot:P99999", &["pmid:2"]),
            ],
            &[Expect::fail("7"), Expect::fail("13")],
            Some(false),
        ),
        both(
            root,
            worker,
            "duplicate-triple",
            "one triple cannot occupy both dictionaries",
            "predicate 15 fails",
            &[("aa:ACD", "uniprot:P12345", &["pmid:1"][..])],
            &[("aa:ACD", "uniprot:P12345", &["pmid:1"][..])],
            &[Expect::fail("15"), Expect::pass("6")],
            Some(false),
        ),
        row(
            root,
            worker,
            "unsorted-citations",
            "citation order is canonical, not decorative",
            "predicates 6 and 12 fail",
            &[("aa:ACD", "uniprot:P12345", &["pmid:2", "pmid:1"])],
            &[Expect::fail("6"), Expect::fail("12")],
            Some(false),
        ),
        row(
            root,
            worker,
            "duplicate-citations",
            "a repeated citation is not two papers",
            "predicates 6 and 12 fail",
            &[("aa:ACD", "uniprot:P12345", &["pmid:1", "pmid:1"])],
            &[Expect::fail("6"), Expect::fail("12")],
            Some(false),
        ),
        row(
            root,
            worker,
            "empty-citations",
            "a target with no citations is not a row",
            "predicate 12 fails and the empty array can still be canonical",
            &[("aa:ACD", "uniprot:P12345", &[])],
            &[Expect::fail("12"), Expect::pass("6")],
            Some(false),
        ),
        finish(
            worker,
            "empty-binder-row",
            "a binder that maps to nothing is not a row",
            "predicate 11 fails and predicate 6 passes",
            run::judge_graph(
                root,
                &catalogue(2, empty_binder("aa:ACD"), BTreeMap::new()),
                None,
                &[Expect::fail("11"), Expect::pass("6")],
                &[],
                Some(false),
            ),
        ),
    ]
}

fn relation(root: &Path) -> Vec<AttackResult> {
    let worker = "relation";
    let one = base_catalogue();
    let two = catalogue(
        2,
        binders(&[("aa:ACD", "uniprot:P12345", &["pmid:1", "pmid:2"])]),
        BTreeMap::new(),
    );
    let moved = catalogue(
        2,
        BTreeMap::new(),
        binders(&[("aa:ACD", "uniprot:P12345", &["pmid:1"])]),
    );
    let bumped = catalogue(
        3,
        binders(&[("aa:ACD", "uniprot:P12345", &["pmid:1"])]),
        BTreeMap::new(),
    );
    vec![
        graph(
            root,
            worker,
            "delete-citation",
            "add-only forbids removing a citation",
            "predicate 19 fails and the successor's pure bytes still pass",
            &one,
            Some(&two),
            &[Expect::fail("19"), Expect::pass("6"), Expect::pass("15")],
            &[],
            Some(false),
        ),
        graph(
            root,
            worker,
            "move-between-dictionaries",
            "moving a triple is removal from the dictionary that had it",
            "predicate 19 fails and predicate 15 does not, because it is not in both",
            &moved,
            Some(&one),
            &[Expect::fail("19"), Expect::pass("15")],
            &[],
            Some(false),
        ),
        graph(
            root,
            worker,
            "add-citation-holds",
            "adding a citation keeps every predecessor row",
            "predicate 19 passes",
            &two,
            Some(&one),
            &[Expect::pass("19"), Expect::pass("6")],
            &[],
            Some(true),
        ),
        graph(
            root,
            worker,
            "identical-successor-holds",
            "an unchanged successor is add-only",
            "predicate 19 passes",
            &one,
            Some(&one),
            &[Expect::pass("19")],
            &[],
            Some(true),
        ),
        graph(
            root,
            worker,
            "version-bump-add-only-holds",
            "predicate 19 checks rows, not the schema version",
            "predicate 4 fails and predicate 19 passes",
            &bumped,
            Some(&one),
            &[Expect::fail("4"), Expect::pass("19")],
            &[],
            Some(false),
        ),
        finish(
            worker,
            "merge-commutes",
            "merge is commutative",
            "merge(A,B) and merge(B,A) are the same bytes",
            merge_commutes(root),
        ),
        finish(
            worker,
            "merge-idempotent",
            "merge is idempotent",
            "merge(A,A) equals A",
            merge_idempotent(root),
        ),
        finish(
            worker,
            "merge-refuses-version",
            "different versions are not coerced",
            "merge exits non-zero and names the version refusal",
            merge_refuses_version(root),
        ),
    ]
}

fn oracle(root: &Path) -> Vec<AttackResult> {
    let worker = "oracle";
    vec![
        graph(
            root,
            worker,
            "base-oracle-open",
            "a passing pure run does not read the papers",
            "the oracle line stays NOT DISCHARGED",
            &base_catalogue(),
            None,
            &[Expect::pass("6")],
            &["16"],
            Some(true),
        ),
        graph(
            root,
            worker,
            "broken-file-oracle-open",
            "a failing file does not discharge predicate 16 either",
            "the oracle line stays NOT DISCHARGED while predicates 6 and 18 fail",
            COMPACT,
            None,
            &[Expect::fail("6"), Expect::fail("18")],
            &["16"],
            Some(false),
        ),
        finish(
            worker,
            "no-reliability-predicate",
            "one re-run is not evidence of reliability",
            "no predicate id is 16 or a reliability claim",
            no_reliability(root),
        ),
    ]
}

fn document(root: &Path) -> Vec<AttackResult> {
    let worker = "document";
    vec![
        finish(
            worker,
            "committed-tree-holds",
            "the committed tree meets the pure predicates and E1, E2, E4, E5, E6, and E7",
            "those predicates pass and E3 is not consulted",
            committed_tree(root),
        ),
        finish(
            worker,
            "swarm-spec-refused",
            "agent.swarm is not a spec and not a type",
            "E5 names that refusal",
            repo_edit(
                root,
                "swarm",
                |repo| {
                    write_rel(
                        repo,
                        "docs/swarm-attack.md",
                        &spec_header("agent.system", "agent.swarm"),
                    )
                },
                &[Expect::fail_row(
                    "E5",
                    "agent.swarm is not a spec and not a type",
                )],
                &[],
            ),
        ),
        finish(
            worker,
            "fleet-spec-refused",
            "agent.fleet is not a spec and not a type",
            "E5 names that refusal",
            repo_edit(
                root,
                "fleet",
                |repo| {
                    write_rel(
                        repo,
                        "docs/fleet-attack.md",
                        &spec_header("agent.system", "agent.fleet"),
                    )
                },
                &[Expect::fail_row(
                    "E5",
                    "agent.fleet is not a spec and not a type",
                )],
                &[],
            ),
        ),
        finish(
            worker,
            "unregistered-skill",
            "a skill file outside section 10 is not a procedure of this contract",
            "E2 reports it missing and E5 still accepts the skill header",
            repo_edit(
                root,
                "skill",
                |repo| {
                    write_rel(
                        repo,
                        "skills/break-system.md",
                        &spec_header("resource.procedure", "agent.skill"),
                    )
                },
                &[
                    Expect::fail_row("E2", "break-system.md: skill file present but not listed"),
                    Expect::pass("E5"),
                ],
                &[],
            ),
        ),
        finish(
            worker,
            "unregistered-system",
            "a system file outside section 11 is not a run of this contract",
            "E4 reports it missing and E5 still accepts the campaign header",
            repo_edit(
                root,
                "system",
                |repo| {
                    write_rel(
                        repo,
                        "systems/break-campaign.md",
                        &spec_header("agent.system", "fleet.campaign"),
                    )
                },
                &[
                    Expect::fail_row(
                        "E4",
                        "break-campaign.md: system file present but not listed",
                    ),
                    Expect::pass("E5"),
                ],
                &[],
            ),
        ),
        finish(
            worker,
            "one-sided-edge",
            "every Markdown edge is declared at both ends",
            "E6 fails on the falsify edge",
            repo_edit(
                root,
                "edge",
                |repo| {
                    let path = repo.join("docs/follow-agent-contract.md");
                    let text =
                        fs::read_to_string(&path).map_err(|err| format!("harness: {err}"))?;
                    let line = "- → [falsify.md](falsify.md)\n";
                    if !text.contains(line) {
                        return Err("harness: falsify edge missing from the contract".to_string());
                    }
                    fs::write(path, text.replacen(line, "", 1))
                        .map_err(|err| format!("harness: {err}"))
                },
                &[Expect::fail_row("E6", "docs/falsify.md")],
                &[],
            ),
        ),
        finish(
            worker,
            "banner-removed",
            "the banner is byte-identical on every Markdown file",
            "E1 fails",
            repo_edit(
                root,
                "banner",
                |repo| {
                    let path = repo.join("docs/read-repository.md");
                    let text =
                        fs::read_to_string(&path).map_err(|err| format!("harness: {err}"))?;
                    if !text.contains(BANNER) {
                        return Err("harness: banner missing".to_string());
                    }
                    fs::write(path, text.replacen(BANNER, "WARNING", 1))
                        .map_err(|err| format!("harness: {err}"))
                },
                &[Expect::fail_row("E1", "read-repository.md")],
                &[],
            ),
        ),
        finish(
            worker,
            "html-in-body",
            "raw HTML is not a language escape, and a late HTML line is not an H2",
            "E7 fails and E6 still passes",
            repo_edit(
                root,
                "html",
                |repo| {
                    let path = repo.join("docs/falsify.md");
                    let text =
                        fs::read_to_string(&path).map_err(|err| format!("harness: {err}"))?;
                    let from = "## Indications\n";
                    if !text.contains(from) {
                        return Err("harness: Indications heading missing".to_string());
                    }
                    let next = text.replacen(from, "## Indications\n\n<div>break</div>\n", 1);
                    fs::write(path, next).map_err(|err| format!("harness: {err}"))
                },
                &[Expect::fail_row("E7", "raw HTML"), Expect::pass("E6")],
                &[],
            ),
        ),
    ]
}

fn trace(root: &Path) -> Vec<AttackResult> {
    let worker = "trace";
    vec![
        finish(
            worker,
            "valid-trace-holds",
            "a resolve-key call and one halt is a result",
            "the trace code is result",
            trace_mode(root, "valid", true, "result", None),
        ),
        finish(
            worker,
            "oracle-discharged",
            "a trace cannot discharge the paper oracle",
            "admit refuses value:oracle",
            trace_mode(root, "oracle", false, "admit", Some("value:oracle")),
        ),
        finish(
            worker,
            "stale-hash",
            "changing oracle without recomputing the id breaks the hash first",
            "admit refuses hash",
            trace_mode(root, "stale", false, "admit", Some("hash:")),
        ),
        finish(
            worker,
            "score-field",
            "a score has no production in the act grammar",
            "admit refuses fields",
            trace_mode(root, "score", false, "admit", Some("fields:")),
        ),
        finish(
            worker,
            "two-pins",
            "one run has at most one pin",
            "R5 reports the pin count",
            trace_mode(root, "two-pins", false, "R5", Some("pin count")),
        ),
        finish(
            worker,
            "repeated-halt-collapses",
            "a repeated halt line is the same content-addressed act",
            "the trace remains result",
            trace_mode(root, "repeat-halt", true, "result", None),
        ),
        finish(
            worker,
            "emit-without-control",
            "an emission without a passing control is not a result",
            "R10 reports the missing control",
            trace_mode(root, "emit-bare", false, "R10", Some("control absent")),
        ),
    ]
}

fn version_attack(
    root: &Path,
    id: &'static str,
    token: &str,
    premise: &'static str,
    prediction: &'static str,
) -> AttackResult {
    let bytes = match replace_version(&base_catalogue(), token) {
        Ok(bytes) => bytes,
        Err(err) => return finish("bytes", id, premise, prediction, Err(err)),
    };
    graph(
        root,
        "bytes",
        id,
        premise,
        prediction,
        &bytes,
        None,
        &[Expect::fail("4"), Expect::pass("6")],
        &[],
        Some(false),
    )
}

fn committed_holds(root: &Path) -> AttackResult {
    let premise = "the committed catalogue satisfies the pure predicates";
    let prediction = "predicate 6 passes and the oracle stays open";
    let bytes = match fs::read(root.join("graph.json")) {
        Ok(bytes) => bytes,
        Err(err) => {
            return finish(
                "bytes",
                "committed-catalogue-holds",
                premise,
                prediction,
                Err(format!("harness: {err}")),
            )
        }
    };
    graph(
        root,
        "bytes",
        "committed-catalogue-holds",
        premise,
        prediction,
        &bytes,
        None,
        &[Expect::pass("4"), Expect::pass("6")],
        &["16"],
        Some(true),
    )
}

fn committed_one_space(root: &Path) -> AttackResult {
    let premise = "one changed canonical byte of the committed catalogue is a different file";
    let prediction = "predicate 6 fails and predicate 4 still passes";
    let bytes = match one_space(root) {
        Ok(bytes) => bytes,
        Err(err) => {
            return finish(
                "bytes",
                "committed-one-space",
                premise,
                prediction,
                Err(err),
            )
        }
    };
    graph(
        root,
        "bytes",
        "committed-one-space",
        premise,
        prediction,
        &bytes,
        None,
        &[Expect::pass("3"), Expect::pass("4"), Expect::fail("6")],
        &[],
        Some(false),
    )
}

fn no_reliability(root: &Path) -> Result<(), String> {
    let report = run::verify_graph(root, &base_catalogue(), None)?;
    let unknown: Vec<_> = report
        .findings
        .iter()
        .filter(|finding| !run::known_predicate(&finding.id))
        .map(|finding| finding.id.clone())
        .collect();
    if !unknown.is_empty() {
        return Err(format!("unexpected predicate ids {unknown:?}"));
    }
    report::judge(&report, &[Expect::pass("6")], &["16"], Some(true), true)
}

fn committed_tree(root: &Path) -> Result<(), String> {
    let report = run::verify_repo(root, root, true)?;
    report::judge(
        &report,
        &[
            Expect::pass("6"),
            Expect::pass("E1"),
            Expect::pass("E2"),
            Expect::pass("E4"),
            Expect::pass("E5"),
            Expect::pass("E6"),
            Expect::pass("E7"),
        ],
        &["E3", "16"],
        Some(true),
        true,
    )
}

fn repo_edit(
    root: &Path,
    label: &str,
    edit: impl FnOnce(&Path) -> Result<(), String>,
    expects: &[Expect],
    absent: &[&str],
) -> Result<(), String> {
    let dir = TempDir::new(label)?;
    run::copy_repo(root, dir.path())?;
    edit(dir.path())?;
    let report = run::verify_repo(root, dir.path(), false)?;
    report::judge(&report, expects, absent, Some(false), false)
}

fn merge_commutes(root: &Path) -> Result<(), String> {
    let left = base_catalogue();
    let right = catalogue(
        2,
        binders(&[("aa:ACD", "uniprot:P12345", &["pmid:2"])]),
        BTreeMap::new(),
    );
    let forward = run::merge(root, &left, &right)?;
    let backward = run::merge(root, &right, &left)?;
    if forward.code != 0 || backward.code != 0 {
        return Err(format!(
            "harness: merge exit {} {}",
            forward.code, forward.stderr
        ));
    }
    if forward.stdout != backward.stdout {
        return Err(format!(
            "merge orders differed\n{}\n{}",
            forward.stdout, backward.stdout
        ));
    }
    Ok(())
}

fn merge_idempotent(root: &Path) -> Result<(), String> {
    let catalogue = base_catalogue();
    let merged = run::merge(root, &catalogue, &catalogue)?;
    if merged.code != 0 {
        return Err(format!(
            "harness: merge exit {} {}",
            merged.code, merged.stderr
        ));
    }
    if merged.stdout.as_bytes() != catalogue.as_slice() {
        return Err(format!("merge(A,A) differed\n{}", merged.stdout));
    }
    Ok(())
}

fn merge_refuses_version(root: &Path) -> Result<(), String> {
    let left = base_catalogue();
    let right = catalogue(
        3,
        binders(&[("aa:ACD", "uniprot:P12345", &["pmid:1"])]),
        BTreeMap::new(),
    );
    let merged = run::merge(root, &left, &right)?;
    if merged.code == 0 {
        return Err("merge accepted unequal versions".to_string());
    }
    if !merged.stderr.contains("versions differ") {
        return Err(format!(
            "merge refusal did not name versions: {}",
            merged.stderr
        ));
    }
    Ok(())
}

fn trace_mode(
    root: &Path,
    mode: &str,
    pass: bool,
    code: &str,
    row: Option<&str>,
) -> Result<(), String> {
    let dir = TempDir::new(mode)?;
    let core = dir.path().join("core.trace");
    let worker = dir.path().join("a1.trace");
    let built = run::python_args(&[
        "-c".to_string(),
        TRACE_PY.to_string(),
        root.join("verifier").to_string_lossy().into_owned(),
        mode.to_string(),
        core.to_string_lossy().into_owned(),
        worker.to_string_lossy().into_owned(),
    ])?;
    if built.code != 0 {
        return Err(format!(
            "harness: trace builder exit {}\n{}{}",
            built.code, built.stdout, built.stderr
        ));
    }
    let report = run::verify_trace(root, &core, &worker)?;
    report::judge_trace(&report, pass, code, row)
}

fn graph(
    root: &Path,
    worker: &'static str,
    id: &'static str,
    premise: &'static str,
    prediction: &'static str,
    bytes: &[u8],
    prev: Option<&[u8]>,
    expects: &[Expect],
    absent: &[&str],
    result_pass: Option<bool>,
) -> AttackResult {
    finish(
        worker,
        id,
        premise,
        prediction,
        run::judge_graph(root, bytes, prev, expects, absent, result_pass),
    )
}

fn row(
    root: &Path,
    worker: &'static str,
    id: &'static str,
    premise: &'static str,
    prediction: &'static str,
    rows: &[(&str, &str, &[&str])],
    expects: &[Expect],
    result_pass: Option<bool>,
) -> AttackResult {
    let bytes = catalogue(2, binders(rows), BTreeMap::new());
    graph(
        root,
        worker,
        id,
        premise,
        prediction,
        &bytes,
        None,
        expects,
        &[],
        result_pass,
    )
}

fn both(
    root: &Path,
    worker: &'static str,
    id: &'static str,
    premise: &'static str,
    prediction: &'static str,
    pair_rows: &[(&str, &str, &[&str])],
    pre_rows: &[(&str, &str, &[&str])],
    expects: &[Expect],
    result_pass: Option<bool>,
) -> AttackResult {
    let bytes = catalogue(2, binders(pair_rows), binders(pre_rows));
    graph(
        root,
        worker,
        id,
        premise,
        prediction,
        &bytes,
        None,
        expects,
        &[],
        result_pass,
    )
}

fn finish(
    worker: &'static str,
    id: &'static str,
    premise: &'static str,
    prediction: &'static str,
    result: Result<(), String>,
) -> AttackResult {
    let (verdict, detail) = match result {
        Ok(()) => (Verdict::Corroborated, String::new()),
        Err(detail) if detail.starts_with("harness:") => (Verdict::Error, detail),
        Err(detail) => (Verdict::Falsified, detail),
    };
    AttackResult {
        worker,
        id,
        premise,
        prediction,
        verdict,
        detail,
    }
}

fn empty_catalogue() -> Vec<u8> {
    catalogue(2, BTreeMap::new(), BTreeMap::new())
}

fn base_catalogue() -> Vec<u8> {
    catalogue(
        2,
        binders(&[("aa:ACD", "uniprot:P12345", &["pmid:1"])]),
        BTreeMap::new(),
    )
}

fn extra_root(key: &str, value: Value) -> Vec<u8> {
    let mut map = BTreeMap::new();
    map.insert("version".to_string(), Value::Int(2));
    map.insert("pair".to_string(), Value::Obj(BTreeMap::new()));
    map.insert("preclinical".to_string(), Value::Obj(BTreeMap::new()));
    map.insert(key.to_string(), value);
    canonical_bytes(&Value::Obj(map))
}

fn control_helm() -> String {
    format!("helm:PEPTIDE1{{A.{c}}}$$$$", c = '\u{0001}')
}

fn replace_version(bytes: &[u8], token: &str) -> Result<Vec<u8>, String> {
    let text = String::from_utf8(bytes.to_vec()).map_err(|err| format!("harness: {err}"))?;
    let from = "\"version\": 2";
    let to = format!("\"version\": {token}");
    if !text.contains(from) {
        return Err("harness: version token missing".to_string());
    }
    Ok(text.replacen(from, &to, 1).into_bytes())
}

fn one_space(root: &Path) -> Result<Vec<u8>, String> {
    let text =
        fs::read_to_string(root.join("graph.json")).map_err(|err| format!("harness: {err}"))?;
    let from = "\n  \"version\":";
    if !text.contains(from) {
        return Err("harness: version indent missing".to_string());
    }
    Ok(text.replacen(from, "\n \"version\":", 1).into_bytes())
}

fn bad_utf8(bytes: &[u8]) -> Vec<u8> {
    let mut raw = bytes.to_vec();
    let end = raw.len() - 1;
    raw.insert(end, 0xff);
    raw
}

fn overlong(bytes: &[u8]) -> Vec<u8> {
    let mut raw = vec![0xc0, 0x80];
    raw.extend_from_slice(bytes);
    raw
}

fn with_nul(bytes: &[u8]) -> Vec<u8> {
    let mut raw = bytes.to_vec();
    raw.insert(1, 0);
    raw
}

fn bom(bytes: &[u8]) -> Vec<u8> {
    let mut raw = vec![0xef, 0xbb, 0xbf];
    raw.extend_from_slice(bytes);
    raw
}

fn extra_newline(bytes: &[u8]) -> Vec<u8> {
    let mut raw = bytes.to_vec();
    raw.push(b'\n');
    raw
}

fn crlf(bytes: &[u8]) -> Vec<u8> {
    let mut raw = Vec::with_capacity(bytes.len() * 2);
    for byte in bytes {
        if *byte == b'\n' {
            raw.push(b'\r');
        }
        raw.push(*byte);
    }
    raw
}

fn spec_header(type_name: &str, spec: &str) -> String {
    format!(
        "{BANNER}\n\n# attack\n\n`type: {type_name}` · `spec: {spec}`\n\nThis header is the attack.\n\n## Specification\n\nnot a card\n"
    )
}

fn write_rel(repo: &Path, rel: &str, body: &str) -> Result<(), String> {
    let path = repo.join(rel);
    if let Some(parent) = path.parent() {
        fs::create_dir_all(parent).map_err(|err| format!("harness: {err}"))?;
    }
    fs::write(path, body).map_err(|err| format!("harness: {err}"))
}

const TRACE_PY: &str = r#"
import hashlib, sys
sys.path.insert(0, sys.argv[1])
import verify as V

mode, core_path, worker_path = sys.argv[2], sys.argv[3], sys.argv[4]
SPEC = "a" * 40

def core_for(skill):
    text = (
        "%%trace-core/1\n"
        'bound-n:"1"\n'
        'bound-tok:"1"\n'
        'skill:"%s"\n'
        'spec:"%s"\n'
    ) % (skill, SPEC)
    return text, hashlib.sha256(text.encode("utf-8")).hexdigest()

def write(core, run, lines):
    header = "%%trace/1 core=%s spec=%s\n" % (run, SPEC)
    open(core_path, "w", encoding="utf-8").write(core)
    open(worker_path, "w", encoding="utf-8").write(header + "\n".join(lines) + "\n")

def halt_line(run, skill, parent, oracle):
    return V.trace_emit("halt", run, skill, parent, {
        "bound-n": "1", "bound-tok": "1", "oracle": oracle,
    })

if mode in ("valid", "oracle", "stale", "repeat-halt"):
    skill = "resolve-key"
    core, run = core_for(skill)
    call = V.trace_emit("call", run, skill, "^0", {})
    parent = "^" + V.trace_call_id(run, skill)
    oracle = "discharged" if mode == "oracle" else "not-discharged"
    halt = halt_line(run, skill, parent, oracle)
    if mode == "stale":
        halt = halt_line(run, skill, parent, "not-discharged").replace("not-discharged", "discharged", 1)
    lines = [call, halt, halt] if mode == "repeat-halt" else [call, halt]
    write(core, run, lines)
elif mode == "score":
    skill = "propose-pairs"
    core, run = core_for(skill)
    call = V.trace_emit("call", run, skill, "^0", {})
    pin = V.trace_emit("pin", run, skill, "^" + V.trace_call_id(run, skill), {"path": "graph.json", "rev": "b" * 40})
    parent = "^" + pin.split(" ")[1]
    scored = V.trace_emit("propose", run, skill, parent, {
        "binder": "aa:ACD", "pmid": "pmid:1", "score": "0.9", "target": "uniprot:P12345",
    })
    write(core, run, [call, pin, scored])
elif mode == "two-pins":
    skill = "propose-pairs"
    core, run = core_for(skill)
    call = V.trace_emit("call", run, skill, "^0", {})
    call_parent = "^" + V.trace_call_id(run, skill)
    pin_a = V.trace_emit("pin", run, skill, call_parent, {"path": "graph.json", "rev": "a" * 40})
    pin_b = V.trace_emit("pin", run, skill, call_parent, {"path": "graph.json", "rev": "b" * 40})
    parent = "^" + pin_a.split(" ")[1]
    write(core, run, [call, pin_a, pin_b, halt_line(run, skill, parent, "not-discharged")])
elif mode == "emit-bare":
    skill = "design-binder"
    core, run = core_for(skill)
    call = V.trace_emit("call", run, skill, "^0", {})
    pin = V.trace_emit("pin", run, skill, "^" + V.trace_call_id(run, skill), {"path": "graph.json", "rev": "b" * 40})
    parent = "^" + pin.split(" ")[1]
    context = V.trace_emit("context", run, skill, parent, {
        "gloss": "not-a-negative", "target": "uniprot:P12345", "verdict": "absent",
    })
    emitted = V.trace_emit("emit", run, skill, parent, {
        "binder": "aa:ACD", "disclaimer": V.BANNER, "kind": "hypothesis", "target": "uniprot:P12345",
    })
    write(core, run, [call, pin, context, emitted, halt_line(run, skill, parent, "not-discharged")])
else:
    sys.stderr.write("unknown mode %s\n" % mode)
    sys.exit(2)
"#;
