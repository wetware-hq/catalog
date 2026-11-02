//! Canonical catalogue bytes, matched to `verifier/verify.py` `canonical_bytes`.
//!
//! Citation arrays keep the order they are given. Object keys are sorted, except a
//! root whose keys are exactly `version`, `pair`, and `preclinical`, which is emitted
//! in that order.

use std::collections::BTreeMap;

#[derive(Clone, Debug, PartialEq)]
pub enum Value {
    Int(i64),
    Str(String),
    Arr(Vec<Value>),
    Obj(BTreeMap<String, Value>),
}

pub fn canonical_bytes(value: &Value) -> Vec<u8> {
    let mut text = dump(value, 0);
    text.push('\n');
    text.into_bytes()
}

pub fn catalogue(
    version: i64,
    pair: BTreeMap<String, Value>,
    preclinical: BTreeMap<String, Value>,
) -> Vec<u8> {
    let mut root = BTreeMap::new();
    root.insert("version".to_string(), Value::Int(version));
    root.insert("pair".to_string(), Value::Obj(pair));
    root.insert("preclinical".to_string(), Value::Obj(preclinical));
    canonical_bytes(&Value::Obj(root))
}

pub fn binders(rows: &[(&str, &str, &[&str])]) -> BTreeMap<String, Value> {
    let mut pair = BTreeMap::new();
    for (binder, target, pmids) in rows {
        let mut targets = BTreeMap::new();
        let cites = pmids
            .iter()
            .map(|pmid| Value::Str((*pmid).to_string()))
            .collect();
        targets.insert((*target).to_string(), Value::Arr(cites));
        pair.insert((*binder).to_string(), Value::Obj(targets));
    }
    pair
}

pub fn empty_binder(binder: &str) -> BTreeMap<String, Value> {
    let mut pair = BTreeMap::new();
    pair.insert(binder.to_string(), Value::Obj(BTreeMap::new()));
    pair
}

fn dump(value: &Value, indent: usize) -> String {
    let pad = "  ".repeat(indent);
    let pad_in = "  ".repeat(indent + 1);
    match value {
        Value::Int(n) => n.to_string(),
        Value::Str(text) => escape_json(text),
        Value::Arr(items) => {
            if items.is_empty() {
                return "[]".to_string();
            }
            let body = items
                .iter()
                .map(|item| format!("{pad_in}{}", dump(item, indent + 1)))
                .collect::<Vec<_>>()
                .join(",\n");
            format!("[\n{body}\n{pad}]")
        }
        Value::Obj(map) => {
            if map.is_empty() {
                return "{}".to_string();
            }
            let keys: Vec<&String> = if indent == 0 && is_catalogue_root(map) {
                ["version", "pair", "preclinical"]
                    .into_iter()
                    .filter_map(|key| map.get_key_value(key).map(|(k, _)| k))
                    .collect()
            } else {
                map.keys().collect()
            };
            let body = keys
                .into_iter()
                .map(|key| {
                    format!(
                        "{pad_in}{}: {}",
                        escape_json(key),
                        dump(&map[key], indent + 1)
                    )
                })
                .collect::<Vec<_>>()
                .join(",\n");
            format!("{{\n{body}\n{pad}}}")
        }
    }
}

fn is_catalogue_root(map: &BTreeMap<String, Value>) -> bool {
    map.len() == 3
        && map.contains_key("version")
        && map.contains_key("pair")
        && map.contains_key("preclinical")
}

fn escape_json(text: &str) -> String {
    let mut out = String::from("\"");
    for ch in text.chars() {
        match ch {
            '"' => out.push_str("\\\""),
            '\\' => out.push_str("\\\\"),
            '\u{0008}' => out.push_str("\\b"),
            '\u{000c}' => out.push_str("\\f"),
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

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn empty_catalogue_matches_the_contract_literal() {
        let raw = catalogue(2, BTreeMap::new(), BTreeMap::new());
        assert_eq!(
            raw,
            b"{\n  \"version\": 2,\n  \"pair\": {},\n  \"preclinical\": {}\n}\n"
        );
    }

    #[test]
    fn one_row_and_rank_and_control_character_match_the_verifier_encoder() {
        let base = catalogue(
            2,
            binders(&[("aa:ACD", "uniprot:P12345", &["pmid:1"])]),
            BTreeMap::new(),
        );
        assert_eq!(
            String::from_utf8(base).unwrap(),
            "{\n  \"version\": 2,\n  \"pair\": {\n    \"aa:ACD\": {\n      \"uniprot:P12345\": [\n        \"pmid:1\"\n      ]\n    }\n  },\n  \"preclinical\": {}\n}\n"
        );

        let mut rank = BTreeMap::new();
        rank.insert("version".into(), Value::Int(2));
        rank.insert("pair".into(), Value::Obj(BTreeMap::new()));
        rank.insert("preclinical".into(), Value::Obj(BTreeMap::new()));
        rank.insert("rank".into(), Value::Int(1));
        assert_eq!(
            String::from_utf8(canonical_bytes(&Value::Obj(rank))).unwrap(),
            "{\n  \"pair\": {},\n  \"preclinical\": {},\n  \"rank\": 1,\n  \"version\": 2\n}\n"
        );

        let mut note = BTreeMap::new();
        note.insert("version".into(), Value::Int(2));
        note.insert("pair".into(), Value::Obj(BTreeMap::new()));
        note.insert("preclinical".into(), Value::Obj(BTreeMap::new()));
        note.insert("note".into(), Value::Str("x".into()));
        assert_eq!(
            String::from_utf8(canonical_bytes(&Value::Obj(note))).unwrap(),
            "{\n  \"note\": \"x\",\n  \"pair\": {},\n  \"preclinical\": {},\n  \"version\": 2\n}\n"
        );

        let helm = format!("helm:PEPTIDE1{{A.{c}}}$$$$", c = '\u{0001}');
        let ctrl = catalogue(
            2,
            binders(&[(&helm, "uniprot:P12345", &["pmid:1"])]),
            BTreeMap::new(),
        );
        let text = String::from_utf8(ctrl).unwrap();
        assert!(text.contains("helm:PEPTIDE1{A.\\u0001}$$$$"), "{text}");
        assert!(!text.as_bytes().contains(&0x01));
    }
}
