#!/usr/bin/env python3
"""Verifier for wetware-hq/catalog `graph.json`, implemented from follow-agent-contract.md (sections 2, 3, 5, 6, 8) only.

Usage:
    verify.py GRAPH.json                 # pure predicates (8.1-8.15, 8.17, 8.18)
    verify.py --prev OLD.json NEW.json   # the above on NEW, plus relational 8.19 (add-only)
    verify.py --merge A.json B.json      # section 6 merge; writes canonical bytes to stdout
    verify.py GRAPH.json --repo DIR      # + extension predicates E1 (banner), E2 (skill registry), E4 (system registry), E5 (identity line); these gate
    verify.py GRAPH.json --online        # + E3 pmid resolution via NCBI E-utilities; NON-BLOCKING, never gates
    verify.py --trace CORE.trace W.trace # TRACES judgements (tracer/record-fleet-traces.md); hard-coded carrier sets
    verify.py --json ...                 # machine-readable report on stdout

Exit status: 0 = every evaluated pure/relational predicate passed; 1 = a violation/refusal; 2 = usage/IO error.
A passing run proves ONLY the pure (and, with --prev, relational) conditions. 8.16 (oracle) is never discharged.
Standard library only; Python >= 3.9.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import sys
from dataclasses import dataclass, field
from datetime import date

DICTS = ("pair", "preclinical")
ROOT_KEYS = ("version", "pair", "preclinical")
EMPTY_CATALOGUE = b'{\n  "version": 2,\n  "pair": {},\n  "preclinical": {}\n}\n'

# Predicate registry (follow-agent-contract.md section 8). The two HELM refusals are kept as distinct sub-predicates (8.8).
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

# Extension predicates: documentation/repository invariants BEYOND follow-agent-contract.md section 8's nineteen.
# They are NOT part of the normative predicate list and never renumber it; ids are prefixed "E".
EXTENSIONS = {
    "E1": ("pure-ext", "Disclaimer banner (every .md first non-blank line)"),
    "E2": ("pure-ext", "Skill registry (skills <-> follow-agent-contract.md section 10)"),
    "E3": ("online-ext", "pmid: resolves via NCBI E-utilities (non-blocking)"),
    "E4": ("pure-ext", "System registry (systems/*.md and tracer/*.md <-> follow-agent-contract.md section 11)"),
    "E5": ("pure-ext", "Identity line (follow-agent-contract.md section 0c)"),
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
# TRACES judgements (tracer/record-fleet-traces.md). Carrier sets are literals. They are not read from the markdown.
# decide() is total: the first failure in the order R1, R3, admit, R2, R4..R10, else result.
# ---------------------------------------------------------------------------------------------------------------
TRACE_SKILLS = ("resolve-key", "propose-pairs", "design-binder")
TRACE_ACTS = {
    "resolve-key": frozenset({"call", "refuse", "unresolved", "unavailable", "halt"}),
    "propose-pairs": frozenset({"call", "pin", "refuse", "unresolved", "unavailable", "propose", "halt"}),
    "design-binder": frozenset({"call", "pin", "context", "refuse", "unresolved", "unavailable", "emit", "halt"}),
}
TRACE_GATES = {
    "resolve-key": frozenset({"grammar", "scope", "ascii"}),
    "propose-pairs": frozenset({"out-of-scope", "illegal-payload", "duplicate-triple", "duplicate-molecule"}),
    "design-binder": frozenset({
        "grammar", "species", "not-protein", "indication-absent",
        "selectivity", "immunogenicity", "developability", "no-assay",
    }),
}
TRACE_PRE_PIN = frozenset({"grammar", "species", "not-protein", "indication-absent"})
TRACE_STEPS = {
    "resolve-key": frozenset({"resolve"}),
    "propose-pairs": frozenset({"3", "4"}),
    "design-binder": frozenset({"catalogue", "generator", "model"}),
}
# Sorted key order. context is TRACE_CONTEXT, not this table.
TRACE_FIELDS = {
    "call": (),
    "pin": ("path", "rev"),
    "refuse": ("gate", "subject"),
    "unresolved": ("key", "release", "retrieved", "source", "step"),
    "unavailable": ("key", "release", "retrieved", "source", "step"),
    "propose": ("binder", "pmid", "target"),
    "emit": ("binder", "disclaimer", "kind", "target"),
    "halt": ("bound-n", "bound-tok", "oracle"),
}
TRACE_CONTEXT = {
    "hit-same-indication": ("stop", ("binder", "gloss", "pmid", "target", "verdict")),
    "hit-other-indication": ("transfers-not", ("binder", "gloss", "pmid", "target", "verdict")),
    "absent": ("not-a-negative", ("gloss", "target", "verdict")),
}
TRACE_VALUE_MAX = 4096
TRACE_SUBJECT_MAX = 1024
# Field names with no production. Pinned by test_trace_carrier_sets_exclude_scores.
TRACE_FORBIDDEN_FIELDS = frozenset({
    "auc", "auroc", "dict", "dictionary", "grade", "kd", "pair", "pose",
    "preclinical", "rank", "score", "scores", "tier", "utility",
})
_TRACE_CORE_RE = re.compile(
    r"%trace-core/1\n"
    r'bound-n:"([1-9][0-9]*)"\n'
    r'bound-tok:"([1-9][0-9]*)"\n'
    r'skill:"(resolve-key|propose-pairs|design-binder)"\n'
    r'spec:"([0-9a-f]{40})"\n\Z')
_TRACE_HEADER_RE = re.compile(r"%trace/1 core=([0-9a-f]{64}) spec=([0-9a-f]{40})\Z")
_TRACE_WORKER_RE = re.compile(r"^[a-z][a-z0-9-]{0,31}\.trace\Z")
_TRACE_HEX64 = re.compile(r"^[0-9a-f]{64}\Z")
_TRACE_TOKEN64 = re.compile(r"^[A-Za-z0-9._:/-]{1,64}\Z")
_TRACE_DAY = re.compile(r"^[0-9]{4}-[0-9]{2}-[0-9]{2}\Z")
_TRACE_PARENT = re.compile(r"^\^[0-9a-f]{64}\Z")


def trace_emit(act, run, skill, parent, fields):
    """Wire line. fields maps key -> raw value. Key order is sorted. Id is H(preimage)."""
    body = " ".join(f'{k}:"{v}"' for k, v in sorted(fields.items()))
    tail = f"run={run} skill={skill}" if not body else f"run={run} skill={skill} {body}"
    pre = f"{act} {parent} {tail}"
    ident = hashlib.sha256(pre.encode("utf-8")).hexdigest()
    return f"{act} {ident} {parent} {tail}"


def trace_call_id(run, skill):
    return hashlib.sha256(f"call ^0 run={run} skill={skill}".encode("utf-8")).hexdigest()


def _trace_binder_ok(value):
    if value.startswith("aa:"):
        if not AA_RE.match(value):
            return False
        segs = value[len("aa:"):].split("/")
        return segs == sorted(segs)
    if value.startswith("helm:"):
        ok, scope, mono, _msg = parse_helm(value[len("helm:"):])
        return bool(ok and scope and mono)
    return False


def _trace_target_ok(value):
    return UNIPROT_RE.match(value) is not None


def _trace_pmid_ok(value):
    return PMID_RE.match(value) is not None


def _trace_day_ok(value):
    if not _TRACE_DAY.match(value):
        return False
    year, month, day = (int(part) for part in value.split("-"))
    try:
        date(year, month, day)
    except ValueError:
        return False
    return True


def _trace_parse_fields(text):
    """Return ('ok', keys, dict) or ('syntax', None, None). Unsorted keys are syntax."""
    if text == "":
        return "ok", [], {}
    fields = {}
    order = []
    i, n = 0, len(text)
    while i < n:
        if order:
            if text[i] != " ":
                return "syntax", None, None
            i += 1
            if i >= n:
                return "syntax", None, None
        j = i
        if j >= n or not text[j].islower():
            return "syntax", None, None
        j += 1
        while j < n and (text[j].islower() or text[j].isdigit() or text[j] == "-"):
            j += 1
        if j >= n or text[j] != ":":
            return "syntax", None, None
        key = text[i:j]
        j += 1
        if j >= n or text[j] != '"':
            return "syntax", None, None
        j += 1
        end = text.find('"', j)
        if end < 0:
            return "syntax", None, None
        value = text[j:end]
        if value == "" or key in fields or len(value.encode("utf-8")) > TRACE_VALUE_MAX:
            return "syntax", None, None
        fields[key] = value
        order.append(key)
        i = end + 1
    if order != sorted(order):
        return "syntax", None, None
    return "ok", order, fields


def _trace_value_code(skill, act, fields, bound_n, bound_tok):
    if act == "pin":
        if fields.get("path") != "graph.json":
            return "value:path"
        if not re.fullmatch(r"[0-9a-f]{40}", fields.get("rev", "")):
            return "value:rev"
        return None
    if act == "refuse":
        if fields.get("gate") not in TRACE_GATES[skill]:
            return "value:gate"
        subject = fields.get("subject", "")
        if subject in ("unencodable", "unquotable"):
            return None
        raw = subject.encode("utf-8")
        if not raw or len(raw) > TRACE_SUBJECT_MAX or any(c < 32 or c == 127 for c in raw):
            return "value:subject"
        return None
    if act in ("unresolved", "unavailable"):
        step = fields.get("step")
        if step not in TRACE_STEPS[skill]:
            return "value:step"
        if not _TRACE_TOKEN64.match(fields.get("source", "")):
            return "value:source"
        if not _TRACE_TOKEN64.match(fields.get("release", "")):
            return "value:release"
        if not _trace_day_ok(fields.get("retrieved", "")):
            return "value:retrieved"
        key = fields.get("key", "")
        if skill == "propose-pairs" and step == "3" and not _trace_binder_ok(key):
            return "value:key"
        if skill == "propose-pairs" and step == "4" and not _trace_target_ok(key):
            return "value:key"
        if skill == "design-binder" and step == "catalogue" and not _trace_target_ok(key):
            return "value:key"
        if skill == "design-binder" and step == "generator" and not _trace_target_ok(key):
            return "value:key"
        if skill == "design-binder" and step == "model" and not _trace_binder_ok(key):
            return "value:key"
        if skill == "resolve-key" and not (_trace_binder_ok(key) or _trace_target_ok(key)):
            return "value:key"
        return None
    if act == "propose":
        if not _trace_binder_ok(fields["binder"]):
            return "value:binder"
        if not _trace_target_ok(fields["target"]):
            return "value:target"
        if not _trace_pmid_ok(fields["pmid"]):
            return "value:pmid"
        return None
    if act == "emit":
        if not _trace_binder_ok(fields["binder"]):
            return "value:binder"
        if not _trace_target_ok(fields["target"]):
            return "value:target"
        if fields.get("kind") != "hypothesis":
            return "value:kind"
        if fields.get("disclaimer") != BANNER:
            return "value:disclaimer"
        return None
    if act == "context":
        row = TRACE_CONTEXT.get(fields.get("verdict"))
        if row is None:
            return "value:verdict"
        if fields.get("gloss") != row[0]:
            return "value:gloss"
        if "target" in fields and not _trace_target_ok(fields["target"]):
            return "value:target"
        if "binder" in fields and not _trace_binder_ok(fields["binder"]):
            return "value:binder"
        if "pmid" in fields and not _trace_pmid_ok(fields["pmid"]):
            return "value:pmid"
        return None
    if act == "halt":
        if not re.fullmatch(r"[1-9][0-9]*", fields.get("bound-n", "")):
            return "value:bound-n"
        if not re.fullmatch(r"[1-9][0-9]*", fields.get("bound-tok", "")):
            return "value:bound-tok"
        if fields["bound-n"] != bound_n or fields["bound-tok"] != bound_tok:
            return "value:bound"
        if fields.get("oracle") != "not-discharged":
            return "value:oracle"
        return None
    if act == "call":
        return None
    return "value"


def _trace_parent_local(skill, act, fields, parent, call_id):
    if parent != "^0" and not _TRACE_PARENT.match(parent):
        return False
    call_parent = "^" + call_id
    if act == "call":
        return parent == "^0"
    if act == "pin":
        return parent == call_parent
    if skill == "resolve-key":
        return parent == call_parent
    if skill == "design-binder" and act == "refuse" and fields.get("gate") in TRACE_PRE_PIN:
        return parent == call_parent
    if skill == "design-binder" and act == "halt":
        return parent == call_parent or (parent != call_parent and _TRACE_PARENT.match(parent) is not None)
    return parent != "^0" and parent != call_parent and _TRACE_PARENT.match(parent) is not None


def _trace_parent_full(skill, node, call_id, pin_id):
    act = node["act"]
    call_parent = "^" + call_id
    if act == "call":
        return "^0"
    if act == "pin":
        return call_parent
    if skill == "resolve-key":
        return call_parent
    if skill == "design-binder" and act == "refuse" and node["fields"].get("gate") in TRACE_PRE_PIN:
        return call_parent
    if skill == "design-binder" and act == "halt" and pin_id is None:
        return call_parent
    if pin_id is None:
        return None
    return "^" + pin_id


def _trace_admit(line, core, call_id):
    parts = line.split(" ", 3)
    if len(parts) < 4:
        return "syntax", None
    act, ident, parent, rest = parts
    if not _TRACE_HEX64.match(ident):
        return "syntax", None
    matched = re.fullmatch(
        r"run=([0-9a-f]{64}) skill=(resolve-key|propose-pairs|design-binder)(?: (.*))?", rest)
    if not matched:
        return "syntax", None
    run, skill, field_text = matched.group(1), matched.group(2), matched.group(3) or ""
    kind, order, fields = _trace_parse_fields(field_text)
    if kind != "ok":
        return "syntax", None
    preimage = f"{act} {parent} {rest}"
    if hashlib.sha256(preimage.encode("utf-8")).hexdigest() != ident:
        return "hash", None
    if run != core["run"]:
        return "run", None
    if skill != core["skill"]:
        return "skill", None
    if act not in TRACE_ACTS[skill]:
        return "act", None
    if act == "context":
        row = TRACE_CONTEXT.get(fields.get("verdict"))
        if row is None or tuple(order) != row[1]:
            return "fields", None
    elif tuple(order) != TRACE_FIELDS[act]:
        return "fields", None
    value = _trace_value_code(skill, act, fields, core["bound_n"], core["bound_tok"])
    if value:
        return value, None
    if not _trace_parent_local(skill, act, fields, parent, call_id):
        return "parent", None
    return None, {"act": act, "id": ident, "parent": parent, "run": run, "skill": skill,
                  "fields": fields, "text": line}


def _trace_molecule(binder):
    if binder.startswith("aa:") and _trace_binder_ok(binder):
        return ("aa", aa_multiset(binder))
    if binder.startswith("helm:"):
        plain = is_plain_lchain_helm(binder[len("helm:"):])
        if plain is not None:
            return ("aa", (plain,))
        return ("helm", helm_identity(binder))
    return ("other", binder)


def _trace_fail(code, rows):
    return False, code, rows


def check_trace(core_path, worker_paths):
    """Decide tracer/record-fleet-traces.md over one core file and zero or more worker files.

    Returns (ok, code, rows). ok is True only for Result. code is 'result', 'R1'..'R10', or 'admit'.
    On result, rows is [run].
    """
    if os.path.basename(core_path) != "core.trace":
        return _trace_fail("R3", [f"core basename {os.path.basename(core_path)!r}"])
    try:
        with open(core_path, "rb") as stream:
            raw = stream.read()
    except OSError as exc:
        return _trace_fail("R1", [str(exc)])
    if b"\r" in raw or b"\x00" in raw or not raw.endswith(b"\n") or raw.endswith(b"\n\n"):
        return _trace_fail("R1", ["core bytes have no derivation"])
    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError:
        return _trace_fail("R1", ["core is not utf-8"])
    matched = _TRACE_CORE_RE.fullmatch(text)
    if not matched:
        return _trace_fail("R1", ["core syntax"])
    bound_n, bound_tok, skill, spec = matched.group(1), matched.group(2), matched.group(3), matched.group(4)
    run = hashlib.sha256(raw).hexdigest()
    core = {"run": run, "skill": skill, "spec": spec, "bound_n": bound_n, "bound_tok": bound_tok}
    call_id = trace_call_id(run, skill)
    nodes = {}
    for path in worker_paths:
        base = os.path.basename(path)
        if not _TRACE_WORKER_RE.match(base):
            return _trace_fail("R3", [f"worker basename {base!r}"])
        try:
            with open(path, "rb") as stream:
                wraw = stream.read()
        except OSError as exc:
            return _trace_fail("R3", [str(exc)])
        if b"\r" in wraw or b"\x00" in wraw or not wraw.endswith(b"\n") or wraw.endswith(b"\n\n"):
            return _trace_fail("R3", [f"{base}: newline"])
        try:
            wtext = wraw.decode("utf-8")
        except UnicodeDecodeError:
            return _trace_fail("R3", [f"{base}: utf-8"])
        lines = wtext[:-1].split("\n")
        header = _TRACE_HEADER_RE.fullmatch(lines[0] if lines else "")
        if header is None or header.group(1) != run or header.group(2) != spec:
            return _trace_fail("R3", [f"{base}: header"])
        for line in lines[1:]:
            code, node = _trace_admit(line, core, call_id)
            if code:
                return _trace_fail("admit", [f"{code}: {line[:160]}"])
            nodes[node["id"]] = node
    for node in nodes.values():
        if node["run"] != run or node["skill"] != skill:
            return _trace_fail("R2", [node["act"]])
    calls = [node for node in nodes.values() if node["act"] == "call"]
    canon = trace_emit("call", run, skill, "^0", {})
    if len(calls) != 1 or calls[0]["text"] != canon:
        return _trace_fail("R4", ["call"])
    halts = [node for node in nodes.values() if node["act"] == "halt"]
    pins = [node for node in nodes.values() if node["act"] == "pin"]
    if len(halts) != 1:
        return _trace_fail("R5", [f"halt count {len(halts)}"])
    halt = halts[0]
    if halt["fields"]["bound-n"] != bound_n or halt["fields"]["bound-tok"] != bound_tok:
        return _trace_fail("R5", ["bounds"])
    if halt["fields"]["oracle"] != "not-discharged":
        return _trace_fail("R5", ["oracle"])
    if len(pins) > 1:
        return _trace_fail("R5", [f"pin count {len(pins)}"])
    expect_halt = "^" + call_id if not pins else "^" + pins[0]["id"]
    if halt["parent"] != expect_halt:
        return _trace_fail("R5", ["halt parent"])
    ids = set(nodes)
    for node in nodes.values():
        if node["parent"] == "^0":
            if node["act"] != "call":
                return _trace_fail("R6", [node["act"]])
            continue
        if node["parent"][1:] not in ids:
            return _trace_fail("R6", [node["act"]])
    pin_id = pins[0]["id"] if pins else None
    for node in nodes.values():
        if node["act"] not in TRACE_ACTS[skill]:
            return _trace_fail("R7", [node["act"]])
        expected = _trace_parent_full(skill, node, call_id, pin_id)
        if expected is None or node["parent"] != expected:
            return _trace_fail("R7", [f"{node['act']} parent"])
    for node in nodes.values():
        value = _trace_value_code(skill, node["act"], node["fields"], bound_n, bound_tok)
        if value:
            return _trace_fail("R8", [f"{node['act']} {value}"])
    seen = {}
    for node in nodes.values():
        if node["act"] != "propose":
            continue
        binder = node["fields"]["binder"]
        key = _trace_molecule(binder)
        if key in seen and seen[key] != binder:
            return _trace_fail("R9", [f"{seen[key]} ~ {binder}"])
        seen[key] = binder
    by_act = {}
    for node in nodes.values():
        by_act.setdefault(node["act"], []).append(node)
    if skill == "propose-pairs":
        if len(pins) != 1 or pins[0]["parent"] != "^" + call_id:
            return _trace_fail("R10", ["pin"])
        pin_parent = "^" + pins[0]["id"]
        for node in nodes.values():
            if node["act"] not in ("call", "pin") and node["parent"] != pin_parent:
                return _trace_fail("R10", [node["act"]])
        if by_act.get("context") or by_act.get("emit"):
            return _trace_fail("R10", ["foreign act"])
    elif skill == "resolve-key":
        if pins or by_act.get("propose") or by_act.get("context") or by_act.get("emit"):
            return _trace_fail("R10", ["foreign act"])
        for node in nodes.values():
            if node["act"] != "call" and node["parent"] != "^" + call_id:
                return _trace_fail("R10", [node["act"]])
    else:
        if len(pins) == 0:
            refuses = by_act.get("refuse", [])
            if not any(item["fields"]["gate"] in TRACE_PRE_PIN for item in refuses):
                return _trace_fail("R10", ["pre-pin refuse"])
            if by_act.get("context") or by_act.get("emit"):
                return _trace_fail("R10", ["emit"])
            for node in nodes.values():
                if node["act"] != "call" and node["parent"] != "^" + call_id:
                    return _trace_fail("R10", [node["act"]])
        elif len(pins) == 1:
            contexts = by_act.get("context", [])
            if len(contexts) != 1 or contexts[0]["parent"] != "^" + pins[0]["id"]:
                return _trace_fail("R10", ["context"])
            if halt["parent"] != "^" + pins[0]["id"]:
                return _trace_fail("R10", ["halt"])
            for node in by_act.get("emit", []):
                if node["parent"] != "^" + pins[0]["id"]:
                    return _trace_fail("R10", ["emit parent"])
                if node["fields"].get("kind") != "hypothesis" or node["fields"].get("disclaimer") != BANNER:
                    return _trace_fail("R10", ["disclaimer"])
            for node in by_act.get("refuse", []):
                if node["fields"]["gate"] not in TRACE_PRE_PIN and node["parent"] != "^" + pins[0]["id"]:
                    return _trace_fail("R10", ["refuse parent"])
            if contexts[0]["fields"]["verdict"] == "hit-same-indication" and by_act.get("emit"):
                return _trace_fail("R10", ["emit on hit"])
        else:
            return _trace_fail("R10", ["pins"])
    return True, "result", [run]


# ---------------------------------------------------------------------------------------------------------------
# Extension predicates (documentation / repository invariants beyond follow-agent-contract.md section 8)
# ---------------------------------------------------------------------------------------------------------------

# --- E1 exclusions ---------------------------------------------------------------------------------------------
# THE RULE: an exclusion in a checker is only safe if the excluded thing is pinned by a test that fails when
# the exclusion is abused.
#
# E1 must skip something. `verifier/tests/fixtures/ext_disclaimer_fail/skip-disclaimer-banner.md` is a deliberately unbannered
# file and is how E1 itself is tested, so scanning it would make the verifier fail by doing its job. The first
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
    "verifier/tests/fixtures/ext_disclaimer_fail/skip-disclaimer-banner.md",
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


# A skill is "special" iff its header block (text before the first '## ') declares class/type/spec `special`.
# Every skill carries spec `agent.skill`; that is not the special marker.
_SPECIAL_RE = re.compile(r"(?:\b(?:class|type|spec)\b\s*[:=]\s*[`\"']?special\b)", re.I)


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
    """E2 [pure-ext]: skills/*.md <-> follow-agent-contract.md section 10 are in bijection; `special` skills declare write scope `none`."""
    import os
    problems = []
    disk = {os.path.relpath(p0, repo_dir).replace(os.sep, "/") for p0 in _md_files(repo_dir)
            if os.path.relpath(p0, repo_dir).replace(os.sep, "/").startswith("skills/")}
    agents_path = os.path.join(repo_dir, "follow-agent-contract.md")
    if not os.path.exists(agents_path):
        rep.add("E2", False, ["follow-agent-contract.md not found; cannot check the registry"]); return
    rows = _parse_section10(open(agents_path, encoding="utf-8").read())
    listed = {r[0] for r in rows}

    for f in sorted(disk):                         # every skill file must be registered
        if f not in listed:
            problems.append(f"{f}: skill file present but not listed in follow-agent-contract.md section 10")
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


def parse_section11(agents_text):
    """Paths in follow-agent-contract.md section 11 that point at systems/*.md or tracer/*.md, in order."""
    found = []
    in11 = False
    for ln in agents_text.splitlines():
        if ln.startswith("## "):
            in11 = ln.startswith("## 11.")
            continue
        if not in11:
            continue
        found.extend(re.findall(r"\(((?:systems|tracer)/[A-Za-z0-9._-]+\.md)\)", ln))
    return found


def check_system_registry(repo_dir, rep):
    """E4 [pure-ext]: systems/*.md and tracer/*.md <-> follow-agent-contract.md section 11 are in bijection.

    Directories are hard-coded. A file anywhere else is not a system, and a system path that is not one of
    those two directories is not a row this check accepts.
    """
    problems = []
    agents_path = os.path.join(repo_dir, "follow-agent-contract.md")
    if not os.path.exists(agents_path):
        rep.add("E4", False, ["follow-agent-contract.md not found; cannot check the system registry"])
        return
    found = parse_section11(open(agents_path, encoding="utf-8").read())
    if len(found) != len(set(found)):
        problems.append("section 11 lists a system path more than once")
    listed = set(found)
    disk = set()
    for folder in ("systems", "tracer"):
        directory = os.path.join(repo_dir, folder)
        if not os.path.isdir(directory):
            continue
        for fn in sorted(os.listdir(directory)):
            full = os.path.join(directory, fn)
            if fn.endswith(".md") and os.path.isfile(full):
                disk.add(folder + "/" + fn)
    for path in sorted(disk - listed):
        problems.append(f"{path}: system file present but not listed in follow-agent-contract.md section 11")
    for path in sorted(listed - disk):
        problems.append(f"{path}: listed in section 11 but no such file")
    rep.add("E4", not problems, problems)


# Header lines named in follow-agent-contract.md section 0c. agent.swarm is refused as a spec or a
# type. The markdown may use the word when it says that string is neither.
_IDENTITY_TYPE_RE = re.compile(r"`type:\s*([^`]+?)`")
_IDENTITY_SPEC_RE = re.compile(r"`spec:\s*([^`]+?)`")
_IDENTITY_CLASS_RE = re.compile(r"`class:\s*([^`]+?)`")
_REJECTED_RUN_UNIT = "agent.swarm"


def _identity_header(text):
    return text.split("\n## ", 1)[0]


def check_identity(repo_dir, rep):
    """E5 [pure-ext]: header lines match follow-agent-contract.md section 0c.

    skills/ are resource.procedure with spec agent.skill. systems/ and tracer/ are agent.system with
    spec fleet.campaign. fleet/*.md carries spec fleet.campaign and no type. agent.swarm is refused as a spec or a type.
    """
    problems = []

    def read(rel):
        path = os.path.join(repo_dir, rel)
        try:
            return open(path, encoding="utf-8").read()
        except OSError as exc:
            problems.append(f"{rel}: unreadable ({exc})")
            return ""

    def reject_run_unit(rel, types, specs):
        if _REJECTED_RUN_UNIT in types or _REJECTED_RUN_UNIT in specs:
            problems.append(f"{rel}: {_REJECTED_RUN_UNIT} is not a spec and not a type")

    for folder, expect_type, expect_spec in (("skills", "resource.procedure", "agent.skill"),
                                             ("systems", "agent.system", "fleet.campaign"),
                                             ("tracer", "agent.system", "fleet.campaign")):
        directory = os.path.join(repo_dir, folder)
        if not os.path.isdir(directory):
            continue
        for fn in sorted(os.listdir(directory)):
            if not fn.endswith(".md"):
                continue
            rel = folder + "/" + fn
            text = read(rel)
            if not text:
                continue
            header = _identity_header(text)
            types = [t.strip() for t in _IDENTITY_TYPE_RE.findall(header)]
            specs = [s.strip() for s in _IDENTITY_SPEC_RE.findall(header)]
            classes = [c.strip() for c in _IDENTITY_CLASS_RE.findall(header)]
            reject_run_unit(rel, types, specs)
            if types != [expect_type]:
                problems.append(f"{rel}: type {types!r}, expected {[expect_type]!r}")
            if specs != [expect_spec]:
                problems.append(f"{rel}: spec {specs!r}, expected {[expect_spec]!r}")
            if folder == "skills":
                declared = classes == ["special"]
                if classes not in ([], ["special"]):
                    problems.append(f"{rel}: class {classes!r}")
                elif declared != _skill_is_special(os.path.join(repo_dir, rel)):
                    problems.append(f"{rel}: class special and the special-skill marker disagree")
            elif classes:
                problems.append(f"{rel}: agent.system declares no class, found {classes!r}")

    fleet_dir = os.path.join(repo_dir, "fleet")
    if os.path.isdir(fleet_dir):
        for fn in sorted(os.listdir(fleet_dir)):
            if not fn.endswith(".md"):
                continue
            rel = "fleet/" + fn
            text = read(rel)
            if not text:
                continue
            header = _identity_header(text)
            types = [t.strip() for t in _IDENTITY_TYPE_RE.findall(header)]
            specs = [s.strip() for s in _IDENTITY_SPEC_RE.findall(header)]
            reject_run_unit(rel, types, specs)
            if types:
                problems.append(f"{rel}: the harness declares no type")
            if specs != ["fleet.campaign"]:
                problems.append(f"{rel}: spec {specs!r}, expected ['fleet.campaign']")

    rep.add("E5", not problems, problems)


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
        req = urllib.request.Request(url, headers={"User-Agent": "catalog-verifier/1.0 (academic)"})
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
    ap = argparse.ArgumentParser(description="Validate catalog graph.json against follow-agent-contract.md section 8, "
                                             "plus repository extension predicates.")
    ap.add_argument("graph", nargs="?", help="graph.json to validate")
    ap.add_argument("--prev", metavar="OLD", help="predecessor graph.json for relational 8.19 (add-only)")
    ap.add_argument("--merge", nargs=2, metavar=("A", "B"), help="merge two files per section 6 to stdout")
    ap.add_argument("--repo", metavar="DIR", help="run repository extension predicates (E1 banner, E2 skill registry, E4 system registry, E5 identity line) over DIR")
    ap.add_argument("--trace", nargs="+", metavar="FILE",
                    help="decide tracer/record-fleet-traces.md: CORE.trace followed by worker .trace files")
    ap.add_argument("--online", action="store_true",
                    help="also resolve every pmid via NCBI E-utilities (E3). NON-BLOCKING: network, never changes exit code")
    ap.add_argument("--json", action="store_true", help="machine-readable report")
    a = ap.parse_args(argv)

    if a.merge:
        do_merge(*a.merge)
        return 0
    if not a.graph and not a.repo and not a.trace:
        ap.error("GRAPH.json, --repo DIR, or --trace CORE required")

    trace_fail = False
    trace_payload = None
    if a.trace:
        ok, code, rows = check_trace(a.trace[0], a.trace[1:])
        trace_fail = not ok
        trace_payload = {"ok": ok, "code": code, "rows": rows}
        if not a.json:
            if ok:
                print(f"[PASS] trace result {rows[0]}")
            else:
                print(f"[FAIL] trace {code}")
                for row in rows:
                    print(f"      - {row}")
        if not a.graph and not a.repo:
            if a.json:
                print(json.dumps({"trace": trace_payload}, indent=2))
            elif not ok:
                print("\nRESULT: FAIL")
            else:
                print("\nRESULT: PASS (trace judgements only)")
            return 0 if ok else 1

    rep = Report()
    if a.graph:
        check_pure(a.graph, rep)
        if a.prev:
            check_add_only(a.prev, a.graph, rep)
    if a.repo:
        check_disclaimer(a.repo, rep)       # E1
        check_skill_registry(a.repo, rep)   # E2
        check_system_registry(a.repo, rep)  # E4
        check_identity(a.repo, rep)         # E5

    # 16 oracle: always reported as not discharged (only meaningful when a graph was checked)
    oracle_note = "8.16 (oracle) Inclusion and study type: NOT DISCHARGED - requires reading each paper (section 4, 9.3)."

    # E3 online pmid resolution: computed here, reported separately, NEVER folded into exit code.
    online = None
    if a.online and a.graph:
        online = check_online_pmids(a.graph)

    if a.json:
        out = {"file": a.graph, "repo": a.repo, "ok": rep.ok() and not trace_fail,
               "predicates": [{"id": f.predicate, "tag": _label_of(f.predicate)[0],
                               "name": _label_of(f.predicate)[1], "ok": f.ok, "rows": f.rows}
                              for f in rep.findings],
               "oracle_not_discharged": (["16"] if a.graph else [])}
        if trace_payload is not None:
            out["trace"] = trace_payload
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
        print("RESULT:", f"PASS ({'+'.join(scope)} conditions only)" if rep.ok() and not trace_fail else "FAIL")
    return 0 if rep.ok() and not trace_fail else 1


if __name__ == "__main__":
    sys.exit(main())
