#!/usr/bin/env python3
"""Validator for wetware-hq/catalog `graph.json`, implemented from AGENTS.md (sections 2, 3, 5, 6, 8) only.

Usage:
    validate.py GRAPH.json                 # pure predicates (8.1-8.15, 8.17, 8.18)
    validate.py --prev OLD.json NEW.json   # the above on NEW, plus relational 8.19 (add-only)
    validate.py --merge A.json B.json      # section 6 merge; writes canonical bytes to stdout
    validate.py --json ...                 # machine-readable report on stdout

Exit status: 0 = every evaluated pure/relational predicate passed; 1 = a violation/refusal; 2 = usage/IO error.
A passing run proves ONLY the pure (and, with --prev, relational) conditions. 8.16 (oracle) is never discharged.
Standard library only; Python >= 3.9.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from dataclasses import dataclass, field

DICTS = ("pair", "preclinical")
ROOT_KEYS = ("version", "pair", "preclinical")
EMPTY_CATALOGUE = b'{\n  "version": 2,\n  "pair": {},\n  "preclinical": {}\n}\n'

# Predicate registry (AGENTS.md section 8). The two HELM refusals are kept as distinct sub-predicates (8.8).
PREDICATES = {
    "1": ("pure", "UTF-8"),
    "2": ("pure", "Final newline"),
    "3": ("pure", "Root"),
    "4": ("pure", "version"),
    "5": ("pure", "Dictionary shape"),
    "6": ("pure", "Canonical bytes"),
    "7": ("pure", "aa: grammar and order"),
    "8": ("pure", "helm: well-formedness"),
    "8-scope": ("pure", "helm: block-type scope (PEPTIDE only)"),
    "8-monomer": ("pure", "helm: monomer"),
    "9": ("pure", "uniprot:"),
    "10": ("pure", "pmid:"),
    "11": ("pure", "Binder rows"),
    "12": ("pure", "Target rows"),
    "13": ("pure", "One molecule, one key"),
    "14": ("pure", "Cross-prefix hygiene"),
    "15": ("pure", "No duplicate triple"),
    "16": ("oracle", "Inclusion and study type"),
    "17": ("pure", "Forbidden writes"),
    "18": ("pure", "Empty catalogue"),
    "19": ("relational", "Add-only"),
}

# Extension predicates: documentation/repository invariants BEYOND AGENTS.md section 8's nineteen.
# They are NOT part of the normative predicate list and never renumber it; ids are prefixed "E".
EXTENSIONS = {
    "E1": ("pure-ext", "Disclaimer banner (every .md first non-blank line)"),
    "E2": ("pure-ext", "Skill registry (skills <-> AGENTS.md section 10)"),
    "E3": ("online-ext", "pmid: resolves via NCBI E-utilities (non-blocking)"),
}
BANNER = "\u26a0\ufe0f ACADEMIC RESEARCH PURPOSES ONLY; NOT FOR MEDICAL USE WITHOUT LICENSED OVERSIGHT"

# section 3 grammar
AA_RE = re.compile(r"^aa:[ACDEFGHIKLMNPQRSTVWY]+(/[ACDEFGHIKLMNPQRSTVWY]+)*$")
UNIPROT_RE = re.compile(
    r"^uniprot:((?:[OPQ][0-9][A-Z0-9]{3}[0-9])|(?:[A-NR-Z][0-9](?:[A-Z][A-Z0-9]{2}[0-9]){1,2}))(?:-[1-9]\d*)?$")
PMID_RE = re.compile(r"^pmid:(?:0|[1-9]\d*)$")
BINDER_PREFIXES = ("aa:", "helm:")
TARGET_PREFIXES = ("uniprot:",)
CITATION_PREFIXES = ("pmid:",)
STD_RESIDUES = set("ACDEFGHIKLMNPQRSTVWY")
# Keys the spec says are absent by design / forbidden (section 2, 8.17).
FORBIDDEN_ROOT_EXTRA = {"status", "ref", "rank", "ranks", "score", "scores", "grade", "grades"}


@dataclass
class Finding:
    predicate: str
    ok: bool
    rows: list = field(default_factory=list)   # offending rows / messages

    def line(self) -> str:
        if self.predicate in EXTENSIONS:
            tag, name = EXTENSIONS[self.predicate]
            label = f"ext {self.predicate}"
        else:
            tag, name = PREDICATES[self.predicate]
            label = f"8.{self.predicate}"
        head = f"[{'PASS' if self.ok else 'FAIL'}] {label} ({tag}) {name}"
        if self.ok or not self.rows:
            return head
        return head + "\n" + "\n".join(f"      - {r}" for r in self.rows)


class Report:
    def __init__(self):
        self.findings: list[Finding] = []
        self.notes: list[str] = []

    def add(self, predicate, ok, rows=None):
        self.findings.append(Finding(predicate, ok, rows or []))

    def ok(self) -> bool:
        return all(f.ok for f in self.findings)


# ---------------------------------------------------------------------------------------------------------------
# Canonical serialisation (section 5)
# ---------------------------------------------------------------------------------------------------------------
def canonical_bytes(obj) -> bytes:
    """Render per section 5: root key order version,pair,preclinical; every nested object sorted ascending;
    citation arrays sorted+deduped; two-space indent; one trailing \n."""
    def dump(o, indent):
        pad = "  " * indent
        pad2 = "  " * (indent + 1)
        if isinstance(o, dict):
            if not o:
                return "{}"
            keys = list(o.keys())
            if set(keys) == set(ROOT_KEYS) and indent == 0:
                keys = list(ROOT_KEYS)
            else:
                keys = sorted(keys)
            items = [f'{pad2}{json.dumps(k, ensure_ascii=False)}: {dump(o[k], indent + 1)}' for k in keys]
            return "{\n" + ",\n".join(items) + "\n" + pad + "}"
        if isinstance(o, list):
            if not o:
                return "[]"
            items = [f'{pad2}{dump(v, indent + 1)}' for v in o]
            return "[\n" + ",\n".join(items) + "\n" + pad + "]"
        return json.dumps(o, ensure_ascii=False)

    return (dump(obj, 0) + "\n").encode("utf-8")


def canonical_citation_arrays(obj):
    """Return a copy with citation arrays sorted+deduped, for the #6 re-render comparison."""
    if not isinstance(obj, dict):
        return obj
    out = {}
    for k, v in obj.items():
        if k in DICTS and isinstance(v, dict):
            d = {}
            for b, targets in v.items():
                if isinstance(targets, dict):
                    d[b] = {t: (sorted(set(c)) if isinstance(c, list) else c) for t, c in targets.items()}
                else:
                    d[b] = targets
            out[k] = d
        else:
            out[k] = v
    return out


# ---------------------------------------------------------------------------------------------------------------
# HELM parsing (section 8.8)
# ---------------------------------------------------------------------------------------------------------------
BLOCK_RE = re.compile(r"^([A-Z]+)([0-9]+)\{(.*)\}$")


def parse_helm(payload: str):
    """Return (ok, scope_ok, monomer_ok, msg). scope_ok/monomer_ok only meaningful when structure parses."""
    if any(ord(c) < 0x20 or ord(c) == 0x7f for c in payload):
        return False, True, True, "control character or NUL in HELM payload"
    # Split polymer section from the $connections$groupings$ext$[version] tail at the first '$'.
    if "$" not in payload:
        return False, True, True, "no '$' section separator (not HELM)"
    poly, _, rest = payload.partition("$")
    parts = rest.split("$")
    # rest must be conn$group$ext$ (-> 4 pieces, last empty) optionally followed by a version token.
    if len(parts) != 4:
        return False, True, True, "malformed $connections$groupings$ext$ section"
    if parts[3] != "" and not re.fullmatch(r"V[0-9]+\.[0-9]+", parts[3]):
        return False, True, True, f"bad trailing token after sections: {parts[3]!r}"
    if not poly:
        return False, True, True, "empty polymer section"
    scope_ok = True
    monomer_ok = True
    msgs = []
    for block in poly.split("|"):
        m = BLOCK_RE.match(block)
        if not m:
            return False, True, True, f"malformed polymer block: {block!r}"
        btype, index, mon = m.group(1), m.group(2), m.group(3)
        if re.match(r"0", index):
            return False, True, True, f"polymer index has leading zero: {block!r}"
        if btype != "PEPTIDE":
            scope_ok = False
            msgs.append(f"non-PEPTIDE block type {btype!r}")
            continue
        if mon == "":
            monomer_ok = False
            msgs.append("empty {} monomer list")
            continue
        for sym in mon.split("."):
            if len(sym) == 1 and sym in STD_RESIDUES:
                continue
            bm = re.fullmatch(r"\[(.+)\]", sym)
            if not bm:
                monomer_ok = False
                msgs.append(f"non-monomer token {sym!r}")
                continue
            inner = bm.group(1)
            if not valid_monomer_symbol(inner):
                monomer_ok = False
                msgs.append(f"non-monomer bracketed symbol [{inner}]")
    ok = scope_ok and monomer_ok
    return ok, scope_ok, monomer_ok, "; ".join(msgs)


def valid_monomer_symbol(inner: str) -> bool:
    """Heuristic separating a HELM monomer code (e.g. dF, Nle, ac, am, Thi, Hyp) from inline SMILES (e.g. CCO).
    Decidable from bytes; see README 'Spec ambiguities'. Rule: alphanumeric token that is NOT an all-uppercase
    multi-letter run (which is read as SMILES/non-monomer, per the [CCO] example in 8.8)."""
    if not re.fullmatch(r"[A-Za-z0-9]+", inner):
        return False
    if len(inner) > 1 and inner.isupper():
        return False
    return True


def is_plain_lchain_helm(payload: str):
    """If the HELM is a single PEPTIDE block of only standard residues with no connections, return the sequence."""
    ok, *_ = parse_helm(payload)
    if not ok:
        return None
    poly, _, rest = payload.partition("$")
    if rest.split("$")[:3] != ["", "", ""]:
        return None  # has connections/groupings/ext content
    if "|" in poly:
        return None
    m = BLOCK_RE.match(poly)
    if not m:
        return None
    mon = m.group(3)
    syms = mon.split(".")
    if all(len(s) == 1 and s in STD_RESIDUES for s in syms):
        return "".join(syms)
    return None


# ---------------------------------------------------------------------------------------------------------------
# Molecule identity (section 8.13)
# ---------------------------------------------------------------------------------------------------------------
def aa_multiset(key: str):
    return tuple(sorted(key[len("aa:"):].split("/")))


def helm_identity(key: str):
    # normalise polymer index digits only
    payload = key[len("helm:"):]
    return re.sub(r"([A-Za-z\]])([0-9]+)", lambda m: m.group(1) + "#", payload)


# ---------------------------------------------------------------------------------------------------------------
# Predicate checks
# ---------------------------------------------------------------------------------------------------------------
def check_pure(path: str, rep: Report):
    try:
        raw = open(path, "rb").read()
    except OSError as e:
        print(f"cannot read {path}: {e}", file=sys.stderr)
        sys.exit(2)

    # 1 UTF-8
    try:
        text = raw.decode("utf-8")
        rep.add("1", True)
    except UnicodeDecodeError as e:
        rep.add("1", False, [str(e)])
        return  # cannot go further

    # 2 Final newline: ends with exactly one \n, no other trailing whitespace
    if not raw.endswith(b"\n"):
        rep.add("2", False, ["missing final newline"])
    elif raw.endswith(b"\n\n") or re.search(rb"[ \t\r]\n\Z", raw):
        rep.add("2", False, ["extra trailing whitespace before EOF"])
    else:
        rep.add("2", True)

    # 3 Root
    try:
        obj = json.loads(text)
    except json.JSONDecodeError as e:
        rep.add("3", False, [f"not JSON: {e}"])
        return
    if isinstance(obj, list) or not isinstance(obj, dict):
        rep.add("3", False, ["root is not a non-array object"])
        return
    if set(obj.keys()) != set(ROOT_KEYS):
        rep.add("3", False, [f"root keys are {sorted(obj.keys())}, expected {sorted(ROOT_KEYS)}"])
    else:
        rep.add("3", True)

    # 4 version
    v = obj.get("version")
    rep.add("4", v == 2 and isinstance(v, int) and not isinstance(v, bool),
            [] if v == 2 else [f"version = {v!r} (want number 2)"])

    # 5 dictionary shape
    bad5 = [d for d in DICTS if not (d in obj and isinstance(obj[d], dict))]
    rep.add("5", not bad5, [f"{d} is not a non-null object" for d in bad5])

    # 6 canonical bytes
    try:
        rendered = canonical_bytes(canonical_citation_arrays(obj))
        if rendered == raw:
            rep.add("6", True)
        else:
            rows = ["re-serialised bytes differ from file"]
            a, b = rendered.split(b"\n"), raw.split(b"\n")
            for i in range(min(len(a), len(b))):
                if a[i] != b[i]:
                    rows.append(f"first diff at line {i+1}: file={b[i][:60]!r} canonical={a[i][:60]!r}")
                    break
            if len(a) != len(b):
                rows.append(f"line count file={len(b)} canonical={len(a)}")
            rep.add("6", False, rows)
    except Exception as e:
        rep.add("6", False, [f"re-serialise failed: {e}"])

    dicts = {d: obj[d] for d in DICTS if isinstance(obj.get(d), dict)}

    # 7 aa grammar + order
    bad7 = []
    for d, data in dicts.items():
        for b in data:
            if b.startswith("aa:"):
                if not AA_RE.match(b):
                    bad7.append(f"{d}: bad aa grammar: {b[:40]}...")
                    continue
                segs = b[len("aa:"):].split("/")
                if segs != sorted(segs):
                    bad7.append(f"{d}: aa segments not non-decreasing: {b[:40]}...")
    rep.add("7", not bad7, bad7)

    # 8 / 8-scope / 8-monomer
    bad8, bad8s, bad8m = [], [], []
    for d, data in dicts.items():
        for b in data:
            if b.startswith("helm:"):
                ok, sc, mo, msg = parse_helm(b[len("helm:"):])
                if not (sc) :
                    bad8s.append(f"{d}: {b[:50]}... : {msg}")
                if sc and not mo:
                    bad8m.append(f"{d}: {b[:50]}... : {msg}")
                if not ok and sc and mo:
                    bad8.append(f"{d}: {b[:50]}... : {msg}")
    rep.add("8", not bad8, bad8)
    rep.add("8-scope", not bad8s, bad8s)
    rep.add("8-monomer", not bad8m, bad8m)

    # 9 uniprot
    bad9 = []
    for d, data in dicts.items():
        for b, targets in data.items():
            if isinstance(targets, dict):
                for t in targets:
                    if not UNIPROT_RE.match(t):
                        bad9.append(f"{d}: {b[:20]}... -> bad target {t}")
    rep.add("9", not bad9, bad9)

    # 10 pmid
    bad10 = []
    for d, data in dicts.items():
        for b, targets in data.items():
            if isinstance(targets, dict):
                for t, cites in targets.items():
                    if isinstance(cites, list):
                        for c in cites:
                            if not (isinstance(c, str) and PMID_RE.match(c)):
                                bad10.append(f"{d}: {b[:20]}.../{t} bad citation {c!r}")
    rep.add("10", not bad10, bad10)

    # 11 binder rows
    bad11 = []
    for d, data in dicts.items():
        for b, targets in data.items():
            if not (isinstance(targets, dict) and len(targets) >= 1):
                bad11.append(f"{d}: binder {b[:30]}... maps to empty/non-object")
    rep.add("11", not bad11, bad11)

    # 12 target rows
    bad12 = []
    for d, data in dicts.items():
        for b, targets in data.items():
            if not isinstance(targets, dict):
                continue
            for t, cites in targets.items():
                if not UNIPROT_RE.match(t):
                    bad12.append(f"{d}: {b[:20]}... target key {t} bad")
                if not (isinstance(cites, list) and len(cites) >= 1):
                    bad12.append(f"{d}: {b[:20]}.../{t} citations empty/not array")
                    continue
                if cites != sorted(cites):
                    bad12.append(f"{d}: {b[:20]}.../{t} citations not sorted")
                if len(cites) != len(set(cites)):
                    bad12.append(f"{d}: {b[:20]}.../{t} citations have duplicates")
    rep.add("12", not bad12, bad12)

    # 13 one molecule one key
    bad13 = []
    aa_keys, helm_keys = {}, {}
    plain = {}
    for d, data in dicts.items():
        for b in data:
            if b.startswith("aa:") and AA_RE.match(b):
                ms = aa_multiset(b)
                if ms in aa_keys and aa_keys[ms] != b:
                    bad13.append(f"aa molecule shared by {aa_keys[ms][:30]}... and {b[:30]}...")
                aa_keys[ms] = b
            elif b.startswith("helm:"):
                ident = helm_identity(b)
                if ident in helm_keys and helm_keys[ident] != b:
                    bad13.append(f"helm molecule shared by {helm_keys[ident][:30]}... and {b[:30]}...")
                helm_keys[ident] = b
                seq = is_plain_lchain_helm(b[len("helm:"):])
                if seq is not None:
                    plain[(seq,)] = b
    # aa vs plain-L-chain helm
    for ms, aakey in aa_keys.items():
        if len(ms) == 1:
            if (ms[0],) in plain:
                bad13.append(f"helm plain L-chain {plain[(ms[0],)][:30]}... duplicates aa molecule {aakey[:30]}... (only aa form valid)")
    rep.add("13", not bad13, bad13)

    # 14 cross-prefix hygiene
    bad14 = []
    for d, data in dicts.items():
        for b, targets in data.items():
            if not b.startswith(BINDER_PREFIXES):
                bad14.append(f"{d}: binder key wrong prefix: {b[:30]}...")
            if b.startswith(TARGET_PREFIXES + CITATION_PREFIXES):
                bad14.append(f"{d}: binder has target/citation prefix: {b[:30]}...")
            if isinstance(targets, dict):
                for t in targets:
                    if not t.startswith(TARGET_PREFIXES):
                        bad14.append(f"{d}: target wrong prefix: {t}")
    rep.add("14", not bad14, bad14)

    # 15 no duplicate triple across dictionaries
    bad15 = []
    triples = {}
    for d, data in dicts.items():
        for b, targets in data.items():
            if isinstance(targets, dict):
                for t, cites in targets.items():
                    if isinstance(cites, list):
                        for c in cites:
                            triples.setdefault((b, t, c), set()).add(d)
    for (b, t, c), ds in triples.items():
        if len(ds) > 1:
            bad15.append(f"triple in both dictionaries: ({b[:20]}..., {t}, {c})")
    rep.add("15", not bad15, bad15)

    # 17 forbidden writes
    bad17 = [k for k in obj if k in FORBIDDEN_ROOT_EXTRA]
    # non-pmid citation forms already caught by 10; here flag any stored rank/score keys at root
    rep.add("17", not bad17, [f"forbidden root key {k!r}" for k in bad17])

    # 18 empty catalogue
    if dicts.get("pair") == {} and dicts.get("preclinical") == {}:
        rep.add("18", raw == EMPTY_CATALOGUE,
                [] if raw == EMPTY_CATALOGUE else ["empty catalogue not in the exact 5-line canonical form"])

    return obj


def check_add_only(prev_path: str, new_path: str, rep: Report):
    """8.19 relational add-only: every binder/target/citation in P present unchanged in S, same dictionary."""
    try:
        P = json.loads(open(prev_path, "rb").read().decode("utf-8"))
        S = json.loads(open(new_path, "rb").read().decode("utf-8"))
    except Exception as e:
        rep.add("19", False, [f"cannot load predecessor/successor: {e}"])
        return
    bad = []
    for d in DICTS:
        pd = P.get(d, {}) if isinstance(P.get(d), dict) else {}
        sd = S.get(d, {}) if isinstance(S.get(d), dict) else {}
        for b, targets in pd.items():
            if b not in sd:
                bad.append(f"{d}: binder removed: {b[:30]}...")
                continue
            for t, cites in (targets or {}).items():
                if t not in sd[b]:
                    bad.append(f"{d}: target removed: {b[:20]}.../{t}")
                    continue
                for c in cites:
                    if c not in sd[b][t]:
                        bad.append(f"{d}: citation removed: {b[:20]}.../{t}/{c}")
    rep.add("19", not bad, bad)


def do_merge(a_path: str, b_path: str):
    A = json.loads(open(a_path, "rb").read().decode("utf-8"))
    B = json.loads(open(b_path, "rb").read().decode("utf-8"))
    if A.get("version") != B.get("version"):
        print(f"refuse: versions differ ({A.get('version')} vs {B.get('version')})", file=sys.stderr)
        sys.exit(1)
    M = {"version": A["version"], "pair": {}, "preclinical": {}}
    for d in DICTS:
        out = M[d]
        for src in (A.get(d, {}), B.get(d, {})):
            for b, targets in (src or {}).items():
                for t, cites in targets.items():
                    out.setdefault(b, {}).setdefault(t, set()).update(cites)
        M[d] = {b: {t: sorted(c) for t, c in targets.items()} for b, targets in out.items()}
    sys.stdout.buffer.write(canonical_bytes(M))



# ---------------------------------------------------------------------------------------------------------------
# Extension predicates (documentation / repository invariants beyond AGENTS.md section 8)
# ---------------------------------------------------------------------------------------------------------------

# --- E1 exclusions ---------------------------------------------------------------------------------------------
# THE RULE: an exclusion in a checker is only safe if the excluded thing is pinned by a test that fails when
# the exclusion is abused.
#
# E1 must skip something. `validator/tests/fixtures/ext_disclaimer_fail/notes.md` is a deliberately unbannered
# file and is how E1 itself is tested, so scanning it would make the validator fail by doing its job. The first
# fix skipped the whole `tests/fixtures/` *directory*, which is the wrong shape of exclusion: nothing failed if a
# fixture quietly acquired the banner, nothing failed if a real document was parked under `tests/fixtures/`, and
# the blind spot grew with every file added. An exclusion nothing can falsify is not a fix, it is a hole.
#
# So the exclusion is an explicit allowlist of exact repo-relative paths. Each entry earns its place by
# `test_E1_every_allowlisted_path_fails_the_banner_check`, which asserts that every listed file FAILS the banner
# check: add the banner to a listed file, or delete the file, and that test breaks. The list is one entry long
# because exactly one fixture lacks the banner; the other eight `.md` files under `fixtures/` carry it and are
# scanned like any other file. The one blind spot that remains - a real document moved to exactly an allowlisted
# path is skipped - is itself pinned, by `test_E1_real_file_at_an_allowlisted_path_is_skipped`, so the hole is a
# passing test rather than a paragraph in a comment that someone can delete.
E1_ALLOWLIST = (
    "validator/tests/fixtures/ext_disclaimer_fail/notes.md",
)


def _relposix(path: str, repo_dir: str) -> str:
    """Repo-relative path with forward slashes, which is the form E1_ALLOWLIST is written in."""
    import os
    return os.path.relpath(path, repo_dir).replace(os.sep, "/")


# Directories git does not track at all: version-control internals and tool caches, generated by running the
# tools and absent from a fresh clone. They hold no repository documentation, so they are not repository content
# to exclude - the walk simply never descends into them. Every exclusion of actual repository content is in
# E1_ALLOWLIST above, where a test pins it.
_UNTRACKED_DIRS = (".git", ".pytest_cache", "__pycache__", ".mypy_cache", ".ruff_cache")


def _md_files(repo_dir: str):
    """Every .md under repo_dir, untracked tool directories aside. Exclusion is E1's business, by path."""
    import os
    out = []
    for root, dirs, files in os.walk(repo_dir):
        dirs[:] = [d for d in dirs if d not in _UNTRACKED_DIRS]
        for fn in sorted(files):
            if fn.endswith(".md"):
                out.append(os.path.join(root, fn))
    return sorted(out)


def banner_violation(path: str):
    """None if the first non-blank line of `path` is byte-identical to BANNER, else why not.

    Separated from check_disclaimer so a test can ask the question of one file, without a repo walk and
    without the allowlist in the way - which is what pins every allowlisted path to an actual failure.
    """
    try:
        raw = open(path, "rb").read()
    except OSError as e:
        return f"unreadable ({e})"
    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError:
        return "not valid UTF-8"
    first = next((ln for ln in text.splitlines() if ln.strip() != ""), "")
    if first != BANNER:
        return f"first non-blank line is {first!r}, expected the banner"
    return None


def check_disclaimer(repo_dir: str, rep: "Report"):
    """E1 [pure-ext]: first non-blank line of every .md is byte-identical to BANNER.

    Every .md under repo_dir is checked except the exact paths in E1_ALLOWLIST (see the rule above it).
    """
    bad = []
    for path in _md_files(repo_dir):
        rel = _relposix(path, repo_dir)
        if rel in E1_ALLOWLIST:
            continue
        why = banner_violation(path)
        if why is not None:
            bad.append(f"{rel}: {why}")
    rep.add("E1", not bad, bad)


# A skill is "special" (an agent.skill) iff its header block (text before the first '## ') declares it so:
# it contains the token `agent.skill`, or a class/type/spec declaration whose value is `special`.
_SPECIAL_RE = re.compile(r"(?:\bagent\.skill\b)|(?:\b(?:class|type|spec)\b\s*[:=]\s*[`\"']?special\b)", re.I)


def _skill_is_special(path: str) -> bool:
    try:
        text = open(path, encoding="utf-8").read()
    except OSError:
        return False
    header = text.split("\n## ", 1)[0]
    return bool(_SPECIAL_RE.search(header))


def _parse_section10(agents_text: str):
    """Return list of (skill_path, write_scope_cell) for every table row in section 10 referencing skills/*.md."""
    lines = agents_text.splitlines()
    rows, in10 = [], False
    for ln in lines:
        if ln.startswith("## "):
            in10 = ln.startswith("## 10.") or ln.lstrip("# ").lower().startswith("10. skills") or "10. skills" in ln.lower()
            continue
        if not in10:
            continue
        if not ln.lstrip().startswith("|"):
            continue
        m = re.search(r"\(skills/([A-Za-z0-9._\-]+\.md)\)", ln)
        if not m:
            continue
        cells = [c.strip() for c in ln.strip().strip("|").split("|")]
        write_scope = cells[-1] if cells else ""
        rows.append(("skills/" + m.group(1), write_scope))
    return rows


def check_skill_registry(repo_dir: str, rep: "Report"):
    """E2 [pure-ext]: skills/*.md <-> AGENTS.md section 10 are in bijection; `special` skills declare write scope `none`."""
    import os
    problems = []
    disk = {os.path.relpath(p0, repo_dir).replace(os.sep, "/") for p0 in _md_files(repo_dir)
            if os.path.relpath(p0, repo_dir).replace(os.sep, "/").startswith("skills/")}
    agents_path = os.path.join(repo_dir, "AGENTS.md")
    if not os.path.exists(agents_path):
        rep.add("E2", False, ["AGENTS.md not found; cannot check the registry"]); return
    rows = _parse_section10(open(agents_path, encoding="utf-8").read())
    listed = {r[0] for r in rows}

    for f in sorted(disk):                         # every skill file must be registered
        if f not in listed:
            problems.append(f"{f}: skill file present but not listed in AGENTS.md section 10")
    for path, scope in rows:                       # every row must point to a real file
        abspath = os.path.join(repo_dir, path)
        if not os.path.exists(abspath):
            problems.append(f"{path}: listed in section 10 but no such file")
            continue
        if _skill_is_special(abspath):             # special -> write scope must be none
            low = scope.lower()
            if "none" not in low or "graph.json" in low or "proposals.json" in low:
                problems.append(f"{path}: class `special` must declare write scope `none`, found {scope!r}")
    rep.add("E2", not problems, problems)


def check_online_pmids(graph_path: str):
    """E3 [online-ext]: every pmid in graph.json resolves via NCBI E-utilities. NON-BLOCKING: never affects exit code.
    Returns (checked, resolved, unresolved_list, unavailable_bool)."""
    import json as _json, time, urllib.request, urllib.error
    try:
        obj = _json.loads(open(graph_path, encoding="utf-8").read())
    except Exception as e:
        return (0, 0, [], f"could not read graph.json: {e}")
    pmids = set()
    for d in ("pair", "preclinical"):
        for _b, targets in (obj.get(d) or {}).items():
            for _t, cites in (targets or {}).items():
                for c in cites or []:
                    if isinstance(c, str) and c.startswith("pmid:"):
                        pmids.add(c[len("pmid:"):])
    ids = sorted(pmids, key=lambda x: int(x) if x.isdigit() else 0)
    if not ids:
        return (0, 0, [], None)
    resolved, unresolved = set(), []
    base = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esummary.fcgi"
    for i in range(0, len(ids), 200):
        batch = ids[i:i + 200]
        url = f"{base}?db=pubmed&retmode=json&id=" + ",".join(batch)
        req = urllib.request.Request(url, headers={"User-Agent": "catalog-validator/1.0 (academic)"})
        try:
            with urllib.request.urlopen(req, timeout=30) as resp:
                data = _json.loads(resp.read().decode("utf-8"))
        except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError, OSError, ValueError) as e:
            return (len(ids), len(resolved), unresolved, f"service unavailable: {e}")
        result = data.get("result", {})
        for uid in batch:
            rec = result.get(uid)
            # NCBI returns an `error` field (or omits the record) for a non-existent PMID.
            if isinstance(rec, dict) and not rec.get("error") and (rec.get("uid") == uid or rec.get("title")):
                resolved.add(uid)
            else:
                unresolved.append(uid)
        time.sleep(0.4)   # honour the ~3 req/s unauthenticated E-utilities limit
    return (len(ids), len(resolved), unresolved, None)


def _label_of(pid):
    reg = EXTENSIONS if pid in EXTENSIONS else PREDICATES
    return reg[pid]


def main(argv=None):
    ap = argparse.ArgumentParser(description="Validate catalog graph.json against AGENTS.md section 8, "
                                             "plus repository extension predicates.")
    ap.add_argument("graph", nargs="?", help="graph.json to validate")
    ap.add_argument("--prev", metavar="OLD", help="predecessor graph.json for relational 8.19 (add-only)")
    ap.add_argument("--merge", nargs=2, metavar=("A", "B"), help="merge two files per section 6 to stdout")
    ap.add_argument("--repo", metavar="DIR", help="run repository extension predicates (E1 banner, E2 skill registry) over DIR")
    ap.add_argument("--online", action="store_true",
                    help="also resolve every pmid via NCBI E-utilities (E3). NON-BLOCKING: network, never changes exit code")
    ap.add_argument("--json", action="store_true", help="machine-readable report")
    a = ap.parse_args(argv)

    if a.merge:
        do_merge(*a.merge)
        return 0
    if not a.graph and not a.repo:
        ap.error("GRAPH.json or --repo DIR required")

    rep = Report()
    if a.graph:
        check_pure(a.graph, rep)
        if a.prev:
            check_add_only(a.prev, a.graph, rep)
    if a.repo:
        check_disclaimer(a.repo, rep)       # E1
        check_skill_registry(a.repo, rep)   # E2

    # 16 oracle: always reported as not discharged (only meaningful when a graph was checked)
    oracle_note = "8.16 (oracle) Inclusion and study type: NOT DISCHARGED - requires reading each paper (section 4, 9.3)."

    # E3 online pmid resolution: computed here, reported separately, NEVER folded into exit code.
    online = None
    if a.online and a.graph:
        online = check_online_pmids(a.graph)

    if a.json:
        out = {"file": a.graph, "repo": a.repo, "ok": rep.ok(),
               "predicates": [{"id": f.predicate, "tag": _label_of(f.predicate)[0],
                               "name": _label_of(f.predicate)[1], "ok": f.ok, "rows": f.rows}
                              for f in rep.findings],
               "oracle_not_discharged": (["16"] if a.graph else [])}
        if online is not None:
            checked, resolved, unresolved, unavail = online
            out["online_pmids"] = {"non_blocking": True, "checked": checked, "resolved": resolved,
                                   "unresolved": unresolved, "unavailable": unavail}
        print(json.dumps(out, indent=2))
    else:
        for f in rep.findings:
            print(f.line())
        if a.graph:
            print(f"[----] {oracle_note}")
        if online is not None:
            checked, resolved, unresolved, unavail = online
            print()
            if unavail:
                print(f"[ONLINE] E3 pmid resolution (non-blocking): UNAVAILABLE - {unavail}")
            elif checked == 0:
                print("[ONLINE] E3 pmid resolution (non-blocking): no pmids to check")
            elif not unresolved:
                print(f"[ONLINE] E3 pmid resolution (non-blocking): all {resolved}/{checked} pmids resolved via NCBI E-utilities")
            else:
                print(f"[ONLINE] E3 pmid resolution (non-blocking): {resolved}/{checked} resolved; "
                      f"{len(unresolved)} did NOT resolve: " + ", ".join("pmid:" + u for u in unresolved[:20]))
        print()
        scope = []
        if a.graph:
            scope.append("pure" + ("/relational" if a.prev else ""))
        if a.repo:
            scope.append("extension")
        print("RESULT:", f"PASS ({'+'.join(scope)} conditions only)" if rep.ok() else "FAIL")
    return 0 if rep.ok() else 1


if __name__ == "__main__":
    sys.exit(main())
