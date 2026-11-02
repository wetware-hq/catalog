//! Falsifier for the catalogue contract.
//!
//! The verifier asks whether the checked assertions hold. These workers invert that
//! question: each premise forbids an observation, and the committed verifier is the
//! instrument that either catches it or lets it survive.

mod attack;
mod canon;
mod report;
mod run;

pub use attack::{campaign, AttackResult, Verdict, WORKERS};

#[cfg(test)]
mod tests {
    use super::*;
    use std::collections::HashSet;
    use std::path::PathBuf;

    #[test]
    fn campaign_corroborates_every_attack() {
        let root = PathBuf::from(env!("CARGO_MANIFEST_DIR")).join("..");
        let root = root.canonicalize().expect("repo root");
        let results = campaign(&root, None);
        let mut ids = Vec::new();
        let mut seen = HashSet::new();
        let mut bad = String::new();
        for result in &results {
            let id = format!("{}/{}", result.worker, result.id);
            if !seen.insert(id.clone()) {
                bad.push_str(&format!("duplicate {id}\n"));
            }
            ids.push(id);
            if result.verdict != Verdict::Corroborated {
                bad.push_str(&format!(
                    "{}/{} {:?}\n{}\n",
                    result.worker, result.id, result.verdict, result.detail
                ));
            }
        }
        ids.sort();
        assert!(bad.is_empty(), "{bad}\nids: {ids:?}");
        assert_eq!(results.len(), 72, "{ids:?}");
    }
}
