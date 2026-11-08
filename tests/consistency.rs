use std::{
    collections::{BTreeMap, BTreeSet},
    fs,
    io::Write,
    path::{Path, PathBuf},
    process::{Command, Stdio},
};

use catalog_agent_organization::{ActionKind, AgentId, AGENT_IMAGE, AGENT_SWARM, TRACER_IMAGE};
use serde::Deserialize;
use serde_json::Value;

const CELL: &str = " { type: notebook.cell }";
const PLAYGROUND: [&str; 4] = ["tla", "lisp", "lean", "bend"];
const PLAYGROUND_MARKER: &str = "Symbolic reasoning. `type: sandbox.playground`.";
const AFTER_PLAYGROUND: [&str; 9] = [
    "bash",
    "javascript",
    "prolog",
    "python",
    "r",
    "rust",
    "tex",
    "typescript",
    "wolfram",
];

#[test]
fn markdown_cells_are_definitive_and_parse() {
    let root = repo();
    let disclaimer = fs::read_to_string(root.join("DISCLAIMER")).unwrap();
    assert!(disclaimer.ends_with('\n'));
    let notice = disclaimer.trim_end_matches('\n');
    assert!(!notice.contains('\n'));
    assert!(!notice.contains('"'));
    assert!(notice.bytes().all(|byte| byte >= 0x20 && byte != 0x7f));
    for path in markdown_files(&root) {
        let text = fs::read_to_string(&path).unwrap();
        let relative = path.strip_prefix(&root).unwrap();
        let lines: Vec<_> = text.lines().collect();
        assert!(
            !text.contains(notice),
            "{relative:?} repeats the root DISCLAIMER"
        );
        assert!(
            !text.contains("ACADEMIC RESEARCH PURPOSES ONLY"),
            "{relative:?} repeats the retired header notice"
        );

        let description = functional_description(&lines);
        assert!(
            description.len() <= 384,
            "{relative:?} description is {} bytes",
            description.len()
        );
        if relative == Path::new("docs/read-repository.md") {
            assert!(
                text.len() <= 6144,
                "initialization file is {} bytes",
                text.len()
            );
        }

        assert_playground(&lines, relative);
        let fences = fences(&text, relative);
        let mut json_cards = 0;
        for fence in &fences {
            match fence.tag.as_str() {
                "json" => {
                    serde_json::from_str::<Value>(&fence.body)
                        .unwrap_or_else(|error| panic!("{relative:?} JSON: {error}"));
                    json_cards += 1;
                }
                "toml" => {
                    toml::from_str::<toml::Value>(&fence.body)
                        .unwrap_or_else(|error| panic!("{relative:?} TOML: {error}"));
                }
                "csv" => assert_process_csv(relative, &fence.body),
                "mermaid" => assert_mermaid(relative, &fence.body),
                "prolog" => assert_canonical_prolog(relative, &fence.body),
                "yaml" => assert!(
                    fence.body.contains("apiVersion:") && fence.body.contains("kind:"),
                    "{relative:?} YAML cell is not a Kubernetes manifest"
                ),
                _ => {}
            }
        }
        assert!(json_cards >= 1, "{relative:?} has no JSON card");
        assert_specification_card(relative, &fences[0]);
    }
}

#[test]
fn symbolic_graph_matches_rust_and_kubernetes_and_sql() {
    let root = repo();
    let falsify = fs::read_to_string(root.join("docs/falsify.md")).unwrap();
    let campaign = fs::read_to_string(root.join("systems/run-campaign.md")).unwrap();
    let contract = fs::read_to_string(root.join("docs/follow-agent-contract.md")).unwrap();
    let swarm = prolog_graph(fence_body(&falsify, "prolog"));
    let fleet = prolog_graph(fence_body(&campaign, "prolog"));
    let published = serde_json::to_value(AGENT_SWARM).unwrap();

    assert_eq!(swarm.image, "agent_swarm");
    assert_eq!(swarm.shape, "dag");
    assert_eq!(swarm.nodes, string_set(AgentId::ALL.map(AgentId::as_str)));
    assert_eq!(swarm.edges, edge_set(&published));
    assert_eq!(fleet.image, "agent_fleet");
    assert_eq!(fleet.shape, "dag");

    let literals =
        serde_json::from_str::<Value>(labeled_fence(&contract, "checker literals")).unwrap();
    let images = literals["e7"]["structure_images"].as_array().unwrap();
    assert_eq!(images.len(), 2);
    assert_eq!(images[0]["atom"], "agent_fleet");
    assert_eq!(images[1]["atom"], "agent_swarm");
    assert_eq!(fleet.nodes, json_strings(&images[0]["nodes"]));
    assert_eq!(fleet.edges, json_edges(&images[0]["edges"]));
    assert_eq!(swarm.nodes, swarm_nodes(&images[1]));
    assert_eq!(swarm.edges, swarm_edges(&images[1]));

    let attacks = serde_json::from_str::<Value>(labeled_fence(&falsify, "attacks")).unwrap();
    let attack_list = attacks["attacks"].as_array().unwrap();
    assert_eq!(attack_list.len(), 88);
    assert!(attack_list
        .iter()
        .any(|attack| attack["id"] == "kubernetes-graph-drift"));

    let manifest = fs::read_to_string(root.join("k8s/organization.yaml")).unwrap();
    let documents = serde_yaml::Deserializer::from_str(&manifest)
        .map(|document| serde_yaml::Value::deserialize(document).unwrap())
        .collect::<Vec<_>>();
    let config = documents
        .iter()
        .find(|document| document["kind"] == "ConfigMap")
        .unwrap();
    let config_json = config["data"]["organization.json"].as_str().unwrap();
    assert_eq!(
        serde_json::from_str::<Value>(config_json).unwrap(),
        published
    );

    let deployment = documents
        .iter()
        .find(|document| {
            document["kind"] == "Deployment"
                && document["metadata"]["name"] == "catalog-agent-organization"
        })
        .unwrap();
    let containers = deployment["spec"]["template"]["spec"]["containers"]
        .as_sequence()
        .unwrap();
    let mut names = BTreeSet::new();
    for container in containers {
        let name = container["name"].as_str().unwrap();
        names.insert(name.to_owned());
        assert_eq!(container["image"].as_str(), Some(AGENT_IMAGE));
        let agent_id = container["env"]
            .as_sequence()
            .unwrap()
            .iter()
            .find(|entry| entry["name"] == "AGENT_ID")
            .unwrap()["value"]
            .as_str()
            .unwrap();
        assert_eq!(agent_id, name);
    }
    assert_eq!(names, string_set(AgentId::ALL.map(AgentId::as_str)));

    let tracer = documents
        .iter()
        .find(|document| {
            document["kind"] == "Deployment" && document["metadata"]["name"] == "catalog-tracer"
        })
        .unwrap();
    let tracer_container = &tracer["spec"]["template"]["spec"]["containers"][0];
    assert_eq!(tracer_container["image"].as_str(), Some(TRACER_IMAGE));

    let sql = fs::read_to_string(root.join("sql/actions.sql")).unwrap();
    assert_eq!(
        sql_choices(&sql, "agent IN"),
        string_set(AgentId::ALL.map(AgentId::as_str))
    );
    assert_eq!(
        sql_choices(&sql, "kind IN"),
        string_set(ActionKind::ALL.map(ActionKind::as_str))
    );

    let agent_image = fs::read_to_string(root.join("agent.dockerfile")).unwrap();
    let tracer_image = fs::read_to_string(root.join("tracer.dockerfile")).unwrap();
    assert!(agent_image.contains("rust:1.85.0-bookworm"));
    assert!(agent_image.contains("--bin catalog-agent"));
    assert!(tracer_image.contains("--bin catalog-tracer"));
    assert!(
        tracer_image.contains("399e9d1995da80b64d2ef3606c1a239018660d8b35209fba3f7b0bc11c631c68")
    );
    assert!(tracer_image.contains("dl.k8s.io/release/${KUBECTL_VERSION}/bin/linux/amd64/kubectl"));
    assert_agent_modules(&root);
}

#[test]
fn binaries_archive_kubernetes_log_lines() {
    let directory =
        std::env::temp_dir().join(format!("catalog-agent-consistency-{}", std::process::id()));
    let _ = fs::remove_dir_all(&directory);
    fs::create_dir_all(&directory).unwrap();
    let jsonl = directory.join("actions.jsonl");
    let sql = directory.join("actions.sql");

    let emitted = Command::new(binary("catalog-agent"))
        .args([
            "--agent",
            "bytes",
            "emit",
            "--kind",
            "completed",
            "--trace-id",
            "consistency-1",
            "--payload",
            r#"{"note":"it's archived"}"#,
        ])
        .output()
        .unwrap();
    assert!(
        emitted.status.success(),
        "{}",
        String::from_utf8_lossy(&emitted.stderr)
    );
    let action = String::from_utf8(emitted.stdout).unwrap();
    let log_line = format!("pod/bytes {action}");

    let mut tracer = Command::new(binary("catalog-tracer"))
        .args([
            "--jsonl",
            jsonl.to_str().unwrap(),
            "--sql",
            sql.to_str().unwrap(),
            "stdin",
        ])
        .stdin(Stdio::piped())
        .stdout(Stdio::piped())
        .stderr(Stdio::piped())
        .spawn()
        .unwrap();
    tracer
        .stdin
        .take()
        .unwrap()
        .write_all(log_line.as_bytes())
        .unwrap();
    let traced = tracer.wait_with_output().unwrap();
    assert!(
        traced.status.success(),
        "{}",
        String::from_utf8_lossy(&traced.stderr)
    );
    assert_eq!(
        serde_json::from_str::<Value>(fs::read_to_string(&jsonl).unwrap().trim()).unwrap(),
        serde_json::from_str::<Value>(action.trim()).unwrap()
    );

    let database = directory.join("actions.db");
    let loaded = Command::new("python3")
        .arg("-c")
        .arg(
            "import sqlite3,sys; con=sqlite3.connect(sys.argv[1]); \
             con.executescript(open(sys.argv[2],encoding='utf-8').read()); \
             row=con.execute('select agent,kind,payload_json from agent_actions').fetchone(); \
             assert row==('bytes','completed','{\"note\":\"it\\'s archived\"}'), row",
        )
        .arg(&database)
        .arg(&sql)
        .output()
        .unwrap();
    assert!(
        loaded.status.success(),
        "{}",
        String::from_utf8_lossy(&loaded.stderr)
    );

    let mut invalid = serde_json::from_str::<Value>(action.trim()).unwrap();
    invalid["agent"] = Value::String("missing".to_owned());
    let mut rejected = Command::new(binary("catalog-tracer"))
        .args([
            "--jsonl",
            directory.join("rejected.jsonl").to_str().unwrap(),
            "stdin",
        ])
        .stdin(Stdio::piped())
        .stderr(Stdio::piped())
        .spawn()
        .unwrap();
    {
        let mut stdin = rejected.stdin.take().unwrap();
        stdin
            .write_all(&serde_json::to_vec(&invalid).unwrap())
            .unwrap();
        stdin.write_all(b"\n").unwrap();
    }
    let rejected = rejected.wait_with_output().unwrap();
    assert!(!rejected.status.success());

    let served = Command::new(binary("catalog-agent"))
        .args([
            "--agent",
            "literals",
            "serve",
            "--trace-id",
            "consistency-serve",
            "--heartbeat-seconds",
            "60",
            "--max-heartbeats",
            "0",
        ])
        .output()
        .unwrap();
    assert!(
        served.status.success(),
        "{}",
        String::from_utf8_lossy(&served.stderr)
    );
    let kinds: Vec<_> = String::from_utf8(served.stdout)
        .unwrap()
        .lines()
        .map(|line| {
            serde_json::from_str::<Value>(line).unwrap()["kind"]
                .as_str()
                .unwrap()
                .to_owned()
        })
        .collect();
    assert_eq!(kinds, ["started", "ready", "stopped"]);
    fs::remove_dir_all(directory).unwrap();
}

struct Fence {
    tag: String,
    body: String,
}

struct Graph {
    image: String,
    shape: String,
    nodes: BTreeSet<String>,
    edges: BTreeSet<(String, String)>,
}

fn repo() -> PathBuf {
    PathBuf::from(env!("CARGO_MANIFEST_DIR"))
}

fn binary(name: &str) -> PathBuf {
    let mut path = repo();
    path.push("target");
    path.push("debug");
    path.push(name);
    assert!(path.is_file(), "missing test binary {}", path.display());
    path
}

fn markdown_files(root: &Path) -> Vec<PathBuf> {
    let mut files = Vec::new();
    walk(root, &mut files);
    files.sort();
    files
        .into_iter()
        .filter(|path| path.extension().is_some_and(|extension| extension == "md"))
        .filter(|path| {
            !path.components().any(|component| {
                matches!(
                    component.as_os_str().to_str(),
                    Some(".git" | "target" | "archive")
                )
            })
        })
        .collect()
}

fn walk(directory: &Path, files: &mut Vec<PathBuf>) {
    for entry in fs::read_dir(directory).unwrap() {
        let path = entry.unwrap().path();
        if path.is_dir() {
            walk(&path, files);
        } else {
            files.push(path);
        }
    }
}

fn functional_description(lines: &[&str]) -> String {
    let heading = lines
        .iter()
        .position(|line| line.starts_with("# "))
        .unwrap();
    let mut index = heading + 1;
    while lines.get(index).is_some_and(|line| line.is_empty()) {
        index += 1;
    }
    if lines
        .get(index)
        .is_some_and(|line| line.starts_with("`type:"))
    {
        index += 1;
        while lines.get(index).is_some_and(|line| line.is_empty()) {
            index += 1;
        }
    }
    let mut paragraph = Vec::new();
    while lines
        .get(index)
        .is_some_and(|line| !line.is_empty() && !line.starts_with("## "))
    {
        paragraph.push(lines[index]);
        index += 1;
    }
    paragraph.join(" ")
}

fn fences(text: &str, path: &Path) -> Vec<Fence> {
    let mut parsed = Vec::new();
    let mut body = String::new();
    let mut tag = String::new();
    let mut inside = false;
    for (offset, line) in text.lines().enumerate() {
        let number = offset + 1;
        if inside {
            if line == "```" {
                parsed.push(Fence {
                    tag: tag.clone(),
                    body: body.clone(),
                });
                body.clear();
                inside = false;
            } else {
                body.push_str(line);
                body.push('\n');
            }
        } else if let Some(rest) = line.strip_prefix("```") {
            tag = if PLAYGROUND.contains(&rest) {
                rest.to_owned()
            } else if let Some(parsed) = rest.strip_suffix(CELL) {
                assert!(
                    !parsed.is_empty() && !parsed.contains(' '),
                    "{path:?}:{number} is not a definitive notebook cell"
                );
                parsed.to_owned()
            } else {
                panic!("{path:?}:{number} is not a playground fence or a notebook cell");
            };
            inside = true;
        }
    }
    assert!(!inside, "{path:?} has an unclosed notebook cell");
    parsed
}

fn assert_playground(lines: &[&str], path: &Path) {
    let markers: Vec<_> = lines
        .iter()
        .enumerate()
        .filter(|(_, line)| **line == PLAYGROUND_MARKER)
        .map(|(index, _)| index)
        .collect();
    assert_eq!(markers.len(), 1, "{path:?} playground count");
    let mut cursor = markers[0] + 1;
    let mut lean = String::new();
    let mut bend = String::new();
    for tag in PLAYGROUND {
        while lines.get(cursor).is_some_and(|line| line.is_empty()) {
            cursor += 1;
        }
        let expected = format!("```{tag}");
        assert_eq!(
            lines.get(cursor).copied(),
            Some(expected.as_str()),
            "{path:?} playground order"
        );
        cursor += 1;
        let start = cursor;
        while lines.get(cursor).copied().is_some_and(|line| line != "```") {
            cursor += 1;
        }
        let body = lines[start..cursor].join("\n");
        if tag == "lean" {
            lean = body;
        } else if tag == "bend" {
            bend = body;
        }
        cursor += 1;
    }
    assert!(lean.contains("Ti"), "{path:?} lean fence names Ti");
    assert!(
        bend.contains("breakpoint"),
        "{path:?} bend fence names breakpoint"
    );
    assert_eq!(
        lines
            .iter()
            .filter(|line| line.starts_with("```lisp"))
            .count(),
        1,
        "{path:?} lisp fence count"
    );
    for line in &lines[..markers[0]] {
        if let Some(rest) = line.strip_prefix("```") {
            let tag = rest.split_whitespace().next().unwrap_or("");
            assert!(
                !AFTER_PLAYGROUND.contains(&tag),
                "{path:?} has `{tag}` before the playground"
            );
        }
    }
}

fn assert_specification_card(path: &Path, fence: &Fence) {
    assert_eq!(fence.tag, "json", "{path:?} specification is not JSON");
    assert!(fence.body.len() <= 2048, "{path:?} card exceeds 2048 bytes");
    let keys: Vec<_> = fence
        .body
        .lines()
        .filter_map(|line| {
            line.strip_prefix("  \"")
                .and_then(|rest| rest.split('"').next())
        })
        .map(str::to_owned)
        .collect();
    assert_eq!(
        keys,
        ["id", "type", "role", "reads", "writes", "must", "check"]
            .map(str::to_owned)
            .to_vec(),
        "{path:?} card field order"
    );
    let card: Value = serde_json::from_str(&fence.body).unwrap();
    assert_eq!(card["id"], path.to_str().unwrap().replace('\\', "/"));
    check_value_lengths(path, &card);
}

fn check_value_lengths(path: &Path, value: &Value) {
    match value {
        Value::String(text) => assert!(
            (1..=128).contains(&text.len()),
            "{path:?} card value has {} bytes: {text}",
            text.len()
        ),
        Value::Array(items) => items
            .iter()
            .for_each(|item| check_value_lengths(path, item)),
        Value::Object(entries) => entries
            .values()
            .for_each(|item| check_value_lengths(path, item)),
        _ => {}
    }
}

fn assert_process_csv(path: &Path, body: &str) {
    let rows: Vec<_> = body.lines().filter(|line| !line.is_empty()).collect();
    assert_eq!(rows.first().copied(), Some("operator,law"), "{path:?}");
    assert_eq!(
        rows[1..],
        [
            "controls,",
            "design,",
            "transport,",
            "stopping,",
            "search,",
            "filters,",
            "recovery,"
        ]
        .map(|prefix| rows
            .iter()
            .find(|row| row.starts_with(prefix))
            .copied()
            .unwrap())
    );
}

fn assert_mermaid(path: &Path, body: &str) {
    let kind = body.lines().next().unwrap();
    assert!(
        kind.starts_with("stateDiagram-v2") || kind.starts_with("flowchart"),
        "{path:?} mermaid kind {kind}"
    );
}

fn assert_canonical_prolog(path: &Path, body: &str) {
    let graph = prolog_graph(body);
    let mut lines = vec![
        format!("image({}).", graph.image),
        format!("shape({}).", graph.shape),
    ];
    lines.extend(graph.nodes.iter().map(|node| format!("node({node}).")));
    lines.extend(
        graph
            .edges
            .iter()
            .map(|(from, to)| format!("edge({from}, {to}).")),
    );
    assert_eq!(
        body.lines().collect::<Vec<_>>(),
        lines,
        "{path:?} Prolog order"
    );
}

fn fence_body<'a>(text: &'a str, tag: &str) -> &'a str {
    let marker = format!("```{tag}{CELL}");
    let start = text.find(&marker).unwrap() + marker.len() + 1;
    let end = text[start..].find("\n```").unwrap() + start;
    &text[start..end]
}

fn labeled_fence<'a>(text: &'a str, label: &str) -> &'a str {
    let marker = format!("<summary>{label}</summary>");
    let start = text.find(&marker).unwrap();
    fence_body(&text[start..], "json")
}

fn prolog_graph(body: &str) -> Graph {
    let mut image = String::new();
    let mut shape = String::new();
    let mut nodes = BTreeSet::new();
    let mut edges = BTreeSet::new();
    for line in body.lines() {
        if let Some(value) = line
            .strip_prefix("image(")
            .and_then(|rest| rest.strip_suffix(")."))
        {
            image = value.to_owned();
        } else if let Some(value) = line
            .strip_prefix("shape(")
            .and_then(|rest| rest.strip_suffix(")."))
        {
            shape = value.to_owned();
        } else if let Some(value) = line
            .strip_prefix("node(")
            .and_then(|rest| rest.strip_suffix(")."))
        {
            nodes.insert(value.to_owned());
        } else if let Some(value) = line
            .strip_prefix("edge(")
            .and_then(|rest| rest.strip_suffix(")."))
        {
            let (from, to) = value.split_once(", ").unwrap();
            edges.insert((from.to_owned(), to.to_owned()));
        } else {
            panic!("unexpected Prolog fact {line}");
        }
    }
    Graph {
        image,
        shape,
        nodes,
        edges,
    }
}

fn edge_set(value: &Value) -> BTreeSet<(String, String)> {
    value["edges"]
        .as_array()
        .unwrap()
        .iter()
        .map(|edge| {
            (
                edge["from"].as_str().unwrap().to_owned(),
                edge["to"].as_str().unwrap().to_owned(),
            )
        })
        .collect()
}

fn json_strings(value: &Value) -> BTreeSet<String> {
    value
        .as_array()
        .unwrap()
        .iter()
        .map(|item| item.as_str().unwrap().to_owned())
        .collect()
}

fn json_edges(value: &Value) -> BTreeSet<(String, String)> {
    value
        .as_array()
        .unwrap()
        .iter()
        .map(|edge| {
            (
                edge[0].as_str().unwrap().to_owned(),
                edge[1].as_str().unwrap().to_owned(),
            )
        })
        .collect()
}

fn swarm_nodes(image: &Value) -> BTreeSet<String> {
    let mut nodes = json_strings(&image["workers"]);
    nodes.insert(image["join"].as_str().unwrap().to_owned());
    nodes.insert(image["sink"].as_str().unwrap().to_owned());
    nodes
}

fn swarm_edges(image: &Value) -> BTreeSet<(String, String)> {
    let join = image["join"].as_str().unwrap();
    let sink = image["sink"].as_str().unwrap();
    let mut edges = image["workers"]
        .as_array()
        .unwrap()
        .iter()
        .map(|worker| (worker.as_str().unwrap().to_owned(), join.to_owned()))
        .collect::<BTreeSet<_>>();
    edges.insert((join.to_owned(), sink.to_owned()));
    edges.insert((
        image["second_parent"].as_str().unwrap().to_owned(),
        sink.to_owned(),
    ));
    edges
}

fn sql_choices(sql: &str, marker: &str) -> BTreeSet<String> {
    let start = sql.find(marker).unwrap();
    let open = sql[start..].find('(').unwrap() + start;
    let close = sql[open..].find(')').unwrap() + open;
    sql[open + 1..close]
        .split(',')
        .map(|item| item.trim().trim_matches('\'').to_owned())
        .filter(|item| !item.is_empty())
        .collect()
}

fn string_set<const N: usize>(values: [&str; N]) -> BTreeSet<String> {
    values.into_iter().map(str::to_owned).collect()
}

fn assert_agent_modules(root: &Path) {
    let mut found = BTreeMap::new();
    let mut files = Vec::new();
    walk(&root.join("src/organization"), &mut files);
    for path in files {
        if path.extension().is_none_or(|extension| extension != "rs") {
            continue;
        }
        let text = fs::read_to_string(&path).unwrap();
        let definitions = text.matches("impl AgentDefinition").count();
        if path.file_name().unwrap() == "mod.rs" {
            assert_eq!(definitions, 0, "{path:?} is a hierarchy file");
            continue;
        }
        assert_eq!(definitions, 1, "{path:?} must define one agent");
        let variant = text
            .split_once("const ID: AgentId = AgentId::")
            .unwrap()
            .1
            .split(';')
            .next()
            .unwrap();
        let module = text
            .split_once("const MODULE: &'static str = \"")
            .unwrap()
            .1
            .split('"')
            .next()
            .unwrap();
        let expected = path
            .strip_prefix(root.join("src"))
            .unwrap()
            .with_extension("")
            .components()
            .map(|component| component.as_os_str().to_str().unwrap())
            .collect::<Vec<_>>()
            .join("::");
        assert_eq!(module, expected);
        let agent = AgentId::ALL
            .into_iter()
            .find(|agent| format!("{agent:?}") == variant)
            .unwrap();
        assert!(found.insert(agent, module.to_owned()).is_none());
    }
    assert_eq!(found.len(), AgentId::ALL.len());
}
