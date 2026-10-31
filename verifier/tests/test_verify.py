"""Unit tests: one minimal failing fixture per pure predicate, plus relational 8.19.
NOT covered: the --merge path (follow-agent-contract.md section 6). No test exercises it.
Run: python3 -m pytest tests/ -q   (or: python3 tests/test_verify.py)
Stdlib-only fallback runner at the bottom, so pytest is optional."""
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import verify as V

VALID = {
    "version": 2,
    "pair": {
        "aa:ACD/ACD": {"uniprot:P12345": ["pmid:1", "pmid:2"]},
        "helm:PEPTIDE1{A.[dF].C}$$$$": {"uniprot:P00533": ["pmid:10"]},
    },
    "preclinical": {},
}


def run_pure(obj=None, raw=None, path="/tmp/_t.json"):
    if raw is None:
        raw = V.canonical_bytes(V.canonical_citation_arrays(obj if obj is not None else VALID))
    open(path, "wb").write(raw)
    rep = V.Report()
    V.check_pure(path, rep)
    return {f.predicate: f.ok for f in rep.findings}


def failing(pred, **kw):
    res = run_pure(**kw)
    assert res.get(pred) is False, f"expected 8.{pred} to FAIL, got {res.get(pred)}"


def passing_all():
    res = run_pure()
    bad = [p for p, ok in res.items() if not ok]
    assert not bad, f"valid fixture should pass all, but failed: {bad}"


# ---- the known-good baseline -------------------------------------------------
def test_valid_passes_all():
    passing_all()


# ---- one minimal failing fixture per pure predicate --------------------------
def test_1_utf8():
    failing("1", raw=b'\xff\xfe not utf8\n')


def test_2_final_newline():
    raw = V.canonical_bytes(V.canonical_citation_arrays(VALID))
    failing("2", raw=raw.rstrip(b"\n"))           # missing newline
    failing("2", raw=raw + b"\n")                 # extra blank line


def test_3_root_extra_key():
    o = dict(VALID); o["extra"] = 1
    failing("3", obj=o)


def test_4_version():
    o = json.loads(json.dumps(VALID)); o["version"] = 1
    failing("4", obj=o)
    o["version"] = "2"
    failing("4", obj=o)


def test_5_dict_shape():
    o = json.loads(json.dumps(VALID)); o["pair"] = []
    failing("5", obj=o)


def test_6_canonical_bytes():
    # compact one-line form fails #6 (and is the 8.18 trap)
    failing("6", raw=b'{"version": 2, "pair": {}, "preclinical": {}}\n')


def test_7_aa_order_and_grammar():
    o = json.loads(json.dumps(VALID))
    o["pair"] = {"aa:DEF/ABC": {"uniprot:P12345": ["pmid:1"]}}  # segments decreasing
    failing("7", obj=o)
    o["pair"] = {"aa:BXZ": {"uniprot:P12345": ["pmid:1"]}}       # non-residue letters
    failing("7", obj=o)


def test_8_scope_vs_monomer():
    # scope: non-PEPTIDE block type  -> 8-scope fails, 8-monomer passes
    o = json.loads(json.dumps(VALID))
    o["pair"] = {"helm:RNA1{A.C.G}$$$$": {"uniprot:P12345": ["pmid:1"]}}
    res = run_pure(obj=o)
    assert res["8-scope"] is False and res["8-monomer"] is True, res
    # monomer: SMILES [CCO] inside a PEPTIDE block -> 8-monomer fails, 8-scope passes
    o["pair"] = {"helm:PEPTIDE1{A.[CCO].C}$$$$": {"uniprot:P12345": ["pmid:1"]}}
    res = run_pure(obj=o)
    assert res["8-monomer"] is False and res["8-scope"] is True, res
    # empty monomer list {} -> monomer fail
    o["pair"] = {"helm:PEPTIDE1{}$$$$": {"uniprot:P12345": ["pmid:1"]}}
    assert run_pure(obj=o)["8-monomer"] is False


def test_8_wellformed():
    o = json.loads(json.dumps(VALID))
    o["pair"] = {"helm:not-helm-at-all": {"uniprot:P12345": ["pmid:1"]}}
    failing("8", obj=o)


def test_9_uniprot():
    o = json.loads(json.dumps(VALID))
    o["pair"] = {"aa:ACD": {"uniprot:p12345": ["pmid:1"]}}  # lowercase accession
    failing("9", obj=o)
    o["pair"] = {"aa:ACD": {"uniprot:P12345-0": ["pmid:1"]}}  # isoform leading zero
    failing("9", obj=o)


def test_10_pmid():
    o = json.loads(json.dumps(VALID))
    o["pair"] = {"aa:ACD": {"uniprot:P12345": ["doi:10.1/x"]}}
    failing("10", obj=o)
    o["pair"] = {"aa:ACD": {"uniprot:P12345": ["pmid:01"]}}  # leading zero
    failing("10", obj=o)


def test_11_binder_rows():
    o = json.loads(json.dumps(VALID))
    o["pair"] = {"aa:ACD": {}}
    failing("11", obj=o)


def test_12_target_rows():
    o = json.loads(json.dumps(VALID))
    o["pair"] = {"aa:ACD": {"uniprot:P12345": []}}  # empty citation array
    failing("12", obj=o)


def test_13_one_molecule_one_key():
    o = json.loads(json.dumps(VALID))
    # same aa multiset, two distinct keys (across dictionaries)
    o["pair"] = {"aa:ACD/ACE": {"uniprot:P12345": ["pmid:1"]}}
    o["preclinical"] = {"aa:ACE/ACD": {"uniprot:P12345": ["pmid:2"]}}
    failing("13", obj=o)
    # plain-L-chain helm duplicating an aa molecule
    o = json.loads(json.dumps(VALID))
    o["pair"] = {"aa:ACD": {"uniprot:P12345": ["pmid:1"]},
                 "helm:PEPTIDE1{A.C.D}$$$$": {"uniprot:P12345": ["pmid:2"]}}
    o["preclinical"] = {}
    failing("13", obj=o)


def test_14_cross_prefix():
    o = json.loads(json.dumps(VALID))
    o["pair"] = {"uniprot:P12345": {"uniprot:P00533": ["pmid:1"]}}  # target prefix on binder
    failing("14", obj=o)


def test_15_duplicate_triple():
    o = json.loads(json.dumps(VALID))
    o["pair"] = {"aa:ACD": {"uniprot:P12345": ["pmid:1"]}}
    o["preclinical"] = {"aa:ACD": {"uniprot:P12345": ["pmid:1"]}}
    failing("15", obj=o)


def test_17_forbidden():
    o = json.loads(json.dumps(VALID)); o["status"] = {}
    # extra root key fails both 3 and 17
    res = run_pure(obj=o)
    assert res["17"] is False


def test_18_empty_catalogue():
    assert run_pure(raw=V.EMPTY_CATALOGUE).get("18") is True
    # compact empty fails 18 (and 6)
    assert run_pure(raw=b'{"version":2,"pair":{},"preclinical":{}}\n').get("18") is False


# ---- relational 8.19 (the --merge path has no test; see the module docstring) -----------------
def test_19_add_only():
    prev = "/tmp/_prev.json"; nxt = "/tmp/_next.json"
    open(prev, "wb").write(V.canonical_bytes(VALID))
    dropped = json.loads(json.dumps(VALID)); dropped["pair"].pop("aa:ACD/ACD")
    open(nxt, "wb").write(V.canonical_bytes(dropped))
    rep = V.Report(); V.check_add_only(prev, nxt, rep)
    assert rep.findings[0].ok is False
    # growing is fine
    grown = json.loads(json.dumps(VALID)); grown["pair"]["aa:ACD/ACD"]["uniprot:P12345"].append("pmid:3")
    open(nxt, "wb").write(V.canonical_bytes(grown))
    rep = V.Report(); V.check_add_only(prev, nxt, rep)
    assert rep.findings[0].ok is True


# --- Extension predicates (beyond follow-agent-contract.md section 8): one failing fixture + test each -------------------------

FIX = os.path.join(os.path.dirname(os.path.abspath(__file__)), "fixtures")


def _ext(repo):
    rep = V.Report()
    V.check_disclaimer(repo, rep)
    V.check_skill_registry(repo, rep)
    return {f.predicate: f for f in rep.findings}


def test_E1_disclaimer_fails_on_missing_banner():
    res = _ext(os.path.join(FIX, "ext_disclaimer_fail"))
    assert res["E1"].ok is False
    assert any("skip-disclaimer-banner.md" in r for r in res["E1"].rows)


def test_E1_disclaimer_passes_when_every_md_is_bannered():
    rep = V.Report(); V.check_disclaimer(os.path.join(FIX, "ext_disclaimer_ok"), rep)
    assert rep.findings[0].ok is True, rep.findings[0].rows


def test_E2_registry_fails_on_orphan_and_bad_special_scope():
    res = _ext(os.path.join(FIX, "ext_registry_fail"))
    rows = res["E2"].rows
    assert res["E2"].ok is False
    assert any("leave-unregistered.md" in r for r in rows)          # on disk, not in section 10
    assert any("exercise-special-scope.md" in r and "none" in r for r in rows)  # special must declare write scope none


def test_E2_registry_passes_on_bijection_with_none_scope():
    res = _ext(os.path.join(FIX, "ext_registry_ok"))
    assert res["E2"].ok is True, res["E2"].rows


# --- E1's exclusion allowlist: every entry pinned, and the remaining blind spot pinned too ------------------
#
# validate.E1_ALLOWLIST is the only thing E1 skips. The rule the three tests below enforce: an exclusion in a
# checker is only safe if the excluded thing is pinned by a test that fails when the exclusion is abused.

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def _tmp_repo(name, files):
    """Write {relpath: text} under /tmp/<name> and return the directory. Fresh every call."""
    import shutil
    root = os.path.join("/tmp", name)
    shutil.rmtree(root, ignore_errors=True)
    for rel, text in files.items():
        full = os.path.join(root, rel)
        os.makedirs(os.path.dirname(full), exist_ok=True)
        open(full, "w", encoding="utf-8").write(text)
    return root


def test_E1_every_allowlisted_path_fails_the_banner_check():
    """Each allowlisted path must exist and must FAIL the banner check it is excluded from.

    This is what stops the allowlist becoming a blind spot: a listed file that quietly acquires the banner, or
    is deleted, no longer needs excluding, and this test fails until the entry is removed.
    """
    assert V.E1_ALLOWLIST, "an empty allowlist means check_disclaimer skips nothing; drop the mechanism instead"
    for rel in V.E1_ALLOWLIST:
        path = os.path.join(REPO_ROOT, rel)
        assert os.path.exists(path), f"{rel}: allowlisted but no such file; remove the entry"
        why = V.banner_violation(path)
        assert why is not None, (
            f"{rel}: allowlisted from E1 but it PASSES the banner check. Either it no longer needs the "
            f"exclusion, or the fixture it serves has been broken.")


def test_E1_fixture_named_file_outside_the_fixtures_tree_still_fails():
    """The exclusion is by exact path, never by name or by directory.

    A file called notes.md sitting in a directory called ext_disclaimer_fail/ - the fixture's own name - still
    fails E1 when it lives anywhere other than the allowlisted path.
    """
    repo = _tmp_repo("e1_lookalike", {
        "start/follow-agent-contract.md": V.BANNER + "\n\n# agents\n",
        "docs/ext_disclaimer_fail/notes.md": "# notes\n\nNo banner, and not at the allowlisted path.\n",
        "tests/fixtures/ext_disclaimer_fail/notes.md": "# notes\n\nNot the allowlisted path either.\n",
    })
    rep = V.Report(); V.check_disclaimer(repo, rep)
    f = rep.findings[0]
    assert f.ok is False, f.rows
    assert any("docs/ext_disclaimer_fail/notes.md" in r for r in f.rows), f.rows
    assert any("tests/fixtures/ext_disclaimer_fail/notes.md" in r for r in f.rows), f.rows


def test_E1_real_file_at_an_allowlisted_path_is_skipped():
    """The blind spot the allowlist still has, written down as a passing test rather than as prose.

    A real, unbannered document placed at exactly an allowlisted path is NOT reported. That is the whole
    residual cost of the exclusion, it is one path wide, and this test is what makes it visible: delete the
    exclusion and this test fails, which is the point.
    """
    rel = V.E1_ALLOWLIST[0]
    repo = _tmp_repo("e1_blindspot", {
        "start/follow-agent-contract.md": V.BANNER + "\n\n# agents\n",
        rel: "# a real document, no banner, parked at an allowlisted path\n",
    })
    assert V.banner_violation(os.path.join(repo, rel)) is not None   # it does violate E1 ...
    rep = V.Report(); V.check_disclaimer(repo, rep)
    assert rep.findings[0].ok is True, rep.findings[0].rows          # ... and E1 still passes: the blind spot


def test_E1_repo_root_passes_with_the_fixtures_scanned():
    """The repository itself passes E1 with every fixture scanned except the allowlist - no directory skipped."""
    rep = V.Report(); V.check_disclaimer(REPO_ROOT, rep)
    assert rep.findings[0].ok is True, rep.findings[0].rows


def test_E3_online_no_pmids_is_noop_without_network():
    # Deterministic, offline: empty catalogue -> nothing to resolve, no HTTP call.
    path = "/tmp/_empty_online.json"
    open(path, "wb").write(V.EMPTY_CATALOGUE)
    checked, resolved, unresolved, unavail = V.check_online_pmids(path)
    assert (checked, resolved, unresolved, unavail) == (0, 0, [], None)


# --- E4 system registry and the TRACES judgements -------------------------------------------------------------

_E4_AGENTS = V.BANNER + """

## 11. Systems

| [`systems/use-bench.md`](systems/use-bench.md) | substrate | .bench only |
| [`systems/record-traces.md`](systems/record-traces.md) | act log | .trace only |
"""


def test_E4_repo_lists_exactly_the_systems():
    text = open(os.path.join(REPO_ROOT, "start", "follow-agent-contract.md"), encoding="utf-8").read()
    assert V.parse_section11(text) == [
        "systems/use-bench.md",
        "systems/record-traces.md",
        "systems/run-campaign.md",
    ]
    rep = V.Report(); V.check_system_registry(REPO_ROOT, rep)
    assert rep.findings[0].ok is True, rep.findings[0].rows


def test_E4_orphan_file_fails():
    repo = _tmp_repo("e4_orphan", {
        "start/follow-agent-contract.md": _E4_AGENTS,
        "systems/use-bench.md": V.BANNER + "\n",
        "systems/record-traces.md": V.BANNER + "\n",
        "systems/extra.md": V.BANNER + "\n",
    })
    rep = V.Report(); V.check_system_registry(repo, rep)
    assert rep.findings[0].ok is False
    assert any("systems/extra.md" in row for row in rep.findings[0].rows), rep.findings[0].rows


def test_E4_dangling_row_fails():
    repo = _tmp_repo("e4_dangling", {
        "start/follow-agent-contract.md": _E4_AGENTS,
        "systems/use-bench.md": V.BANNER + "\n",
    })
    rep = V.Report(); V.check_system_registry(repo, rep)
    assert rep.findings[0].ok is False
    assert any("systems/record-traces.md" in row for row in rep.findings[0].rows), rep.findings[0].rows


def test_E4_path_outside_systems_is_not_a_row():
    agents = V.BANNER + """

## 11. Systems

| [`tracer/record-fleet-traces.md`](tracer/record-fleet-traces.md) | act log | .trace only |
| [`systems/use-bench.md`](systems/use-bench.md) | substrate | .bench only |
"""
    repo = _tmp_repo("e4_outside", {
        "start/follow-agent-contract.md": agents,
        "systems/use-bench.md": V.BANNER + "\n",
        "tracer/record-fleet-traces.md": V.BANNER + "\n",
    })
    rep = V.Report(); V.check_system_registry(repo, rep)
    assert rep.findings[0].ok is False
    assert any("tracer/record-fleet-traces.md" in row and "not under systems/" in row for row in rep.findings[0].rows), rep.findings[0].rows


def test_E6_repo_root_has_no_markdown():
    rep = V.Report(); V.check_root_markdown(REPO_ROOT, rep)
    assert rep.findings[0].ok is True, rep.findings[0].rows


def test_E6_root_markdown_fails():
    repo = _tmp_repo("e6_root_md", {
        "notes.md": V.BANNER + "\n",
        "start/read-repository.md": V.BANNER + "\n",
    })
    rep = V.Report(); V.check_root_markdown(repo, rep)
    assert rep.findings[0].ok is False
    assert any(row.startswith("notes.md:") for row in rep.findings[0].rows), rep.findings[0].rows
    assert not any("read-repository.md" in row for row in rep.findings[0].rows), rep.findings[0].rows


def test_E5_repo_identity_lines_match():
    rep = V.Report(); V.check_identity(REPO_ROOT, rep)
    assert rep.findings[0].ok is True, rep.findings[0].rows


def test_E5_rejects_agent_swarm_as_a_spec():
    line = "`type: resource.procedure` · `spec: agent.swarm` · subordinate.\n"
    repo = _tmp_repo("e5_run_unit", {
        "start/follow-agent-contract.md": V.BANNER + "\n\nfleet.campaign is the run. agent.swarm is not a spec.\n",
        "skills/propose-pairs.md": V.BANNER + "\n\n# `propose-pairs`\n\n" + line + "\n## 0\n\n",
    })
    rep = V.Report(); V.check_identity(repo, rep)
    assert rep.findings[0].ok is False
    assert any("agent.swarm is not a spec and not a type" in row for row in rep.findings[0].rows), rep.findings[0].rows


def test_E5_rejects_agent_fleet_as_a_spec():
    line = "`type: resource.procedure` · `spec: agent.fleet` · subordinate.\n"
    repo = _tmp_repo("e5_retired_fleet", {
        "start/follow-agent-contract.md": V.BANNER + "\n\nfleet.campaign is the run. agent.fleet is not a spec.\n",
        "skills/propose-pairs.md": V.BANNER + "\n\n# `propose-pairs`\n\n" + line + "\n## 0\n\n",
    })
    rep = V.Report(); V.check_identity(repo, rep)
    assert rep.findings[0].ok is False
    assert any("agent.fleet is not a spec and not a type" in row for row in rep.findings[0].rows), rep.findings[0].rows


def test_E5_spec_outside_skills_and_systems_is_an_orphan():
    line = "`type: agent.system` · `spec: fleet.campaign` · subordinate.\n"
    repo = _tmp_repo("e5_orphan_spec", {
        "start/follow-agent-contract.md": V.BANNER + "\n\n# contract\n\n`type: resource.reference`\n\n## 0\n\n",
        "fleet/read-fleet.md": V.BANNER + "\n\n# run\n\n" + line + "\n## 0\n\n",
    })
    rep = V.Report(); V.check_identity(repo, rep)
    assert rep.findings[0].ok is False
    assert any("orphan spec 'fleet.campaign'" in row and "systems/" in row for row in rep.findings[0].rows), rep.findings[0].rows


def test_E5_spec_allowlist_is_the_only_outside_specs():
    """The allowlist is exact: each entry declares a live spec, and no other file outside the two folders does."""
    assert V.E5_SPEC_ALLOWLIST, "an empty allowlist means every outside spec is an orphan; drop the mechanism instead"
    outside = []
    for path in V._md_files(REPO_ROOT):
        rel = V._relposix(path, REPO_ROOT)
        if rel.startswith("skills/") or rel.startswith("systems/"):
            continue
        text = open(path, encoding="utf-8").read()
        specs = [s.strip() for s in V._IDENTITY_SPEC_RE.findall(V._identity_header(text))]
        live = [s for s in specs if s in V._SPEC_FOLDER]
        if live:
            outside.append(rel)
            assert rel in V.E5_SPEC_ALLOWLIST, f"{rel}: live spec {live} is an orphan"
    assert sorted(outside) == sorted(V.E5_SPEC_ALLOWLIST)
    for rel in V.E5_SPEC_ALLOWLIST:
        text = open(os.path.join(REPO_ROOT, rel), encoding="utf-8").read()
        repo = _tmp_repo("e5_allow_" + rel.replace("/", "_"), {
            "start/follow-agent-contract.md": V.BANNER + "\n",
            "notes/copied.md": text,
        })
        rep = V.Report(); V.check_identity(repo, rep)
        assert rep.findings[0].ok is False, rel
        assert any("orphan spec" in row for row in rep.findings[0].rows), rep.findings[0].rows


def test_E5_rejects_a_system_that_is_not_agent_system():
    line = "`type: resource.system` · `spec: fleet.campaign` · subordinate.\n"
    repo = _tmp_repo("e5_type", {
        "start/follow-agent-contract.md": V.BANNER + "\n\nfleet.campaign is the run machinery spec.\n",
        "systems/use-bench.md": V.BANNER + "\n\n# `BENCH`\n\n" + line + "\n## 0\n\n",
    })
    rep = V.Report(); V.check_identity(repo, rep)
    assert rep.findings[0].ok is False
    assert any("agent.system" in row for row in rep.findings[0].rows), rep.findings[0].rows


def _fence_after(label):
    text = open(os.path.join(REPO_ROOT, "systems", "record-traces.md"), encoding="utf-8").read()
    start = text.index("```\n", text.index(label)) + 4
    end = text.index("\n```", start)
    return text[start:end] + "\n"


def _write_trace(name, core, workers):
    root = _tmp_repo(name, {"core.trace": core})
    paths = []
    for base, body in workers:
        path = os.path.join(root, base)
        open(path, "w", encoding="utf-8").write(body)
        paths.append(path)
    return os.path.join(root, "core.trace"), paths


def test_trace_carrier_sets_exclude_scores():
    names = set()
    for keys in V.TRACE_FIELDS.values():
        names.update(keys)
    for _gloss, keys in V.TRACE_CONTEXT.values():
        names.update(keys)
    assert not (names & V.TRACE_FORBIDDEN_FIELDS)
    assert set(V.TRACE_SKILLS) == {"resolve-key", "propose-pairs", "design-binder"}
    assert V.TRACE_FIELDS["halt"] == ("bound-n", "bound-tok", "oracle")
    assert V.TRACE_STEPS["design-binder"] == {"catalogue", "generator", "model"}
    assert V._trace_value_code(
        "design-binder", "unavailable",
        {"key": "uniprot:P12345", "release": "unspecified", "retrieved": "2026-10-31",
         "source": "openrouter", "step": "generator"},
        "1", "1",
    ) is None
    assert "pair" not in V.TRACE_ACTS["propose-pairs"]
    assert "preclinical" not in V.TRACE_ACTS["propose-pairs"]


def test_trace_witness_is_result_and_matches_emit():
    import hashlib
    core = _fence_after("`core.trace`:")
    worker = _fence_after("`a1.trace`:")
    run = hashlib.sha256(core.encode("utf-8")).hexdigest()
    skill = "propose-pairs"
    call_id = V.trace_call_id(run, skill)
    pin_parent = "^" + call_id
    call = V.trace_emit("call", run, skill, "^0", {})
    pin = V.trace_emit("pin", run, skill, pin_parent, {"path": "graph.json", "rev": "b" * 40})
    pin_id = pin.split(" ", 2)[1]
    refuse = V.trace_emit("refuse", run, skill, "^" + pin_id, {
        "gate": "illegal-payload", "subject": "helm:PEPTIDE1{[CCO]}$$$$",
    })
    propose = V.trace_emit("propose", run, skill, "^" + pin_id, {
        "binder": "aa:ACD", "pmid": "pmid:1", "target": "uniprot:P12345",
    })
    halt = V.trace_emit("halt", run, skill, "^" + pin_id, {
        "bound-n": "1", "bound-tok": "8000", "oracle": "not-discharged",
    })
    body = worker[:-1].split("\n")
    assert body[0].startswith("%trace/1 core=" + run)
    assert body[1:] == [call, pin, refuse, propose, halt]
    header = body[0] + "\n"
    core_path, paths = _write_trace("trace_witness", core, [("a1.trace", worker), ("b2.trace", header + "\n".join(body[1:]) + "\n")])
    ok, code, rows = V.check_trace(core_path, paths)
    assert ok and code == "result" and rows == [run], (ok, code, rows)


def test_trace_bad_oracle_and_extra_field_are_admit():
    import hashlib
    core = (
        "%trace-core/1\n"
        'bound-n:"1"\n'
        'bound-tok:"8000"\n'
        'skill:"propose-pairs"\n'
        'spec:"aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"\n'
    )
    run = hashlib.sha256(core.encode("utf-8")).hexdigest()
    skill = "propose-pairs"
    call = V.trace_emit("call", run, skill, "^0", {})
    pin = V.trace_emit("pin", run, skill, "^" + V.trace_call_id(run, skill),
                       {"path": "graph.json", "rev": "b" * 40})
    pin_id = pin.split(" ", 2)[1]
    parent = "^" + pin_id
    halt = V.trace_emit("halt", run, skill, parent, {
        "bound-n": "1", "bound-tok": "8000", "oracle": "discharged",
    })
    header = f"%trace/1 core={run} spec={'a' * 40}\n"
    core_path, paths = _write_trace("trace_oracle", core, [("a1.trace", header + "\n".join([call, pin, halt]) + "\n")])
    ok, code, rows = V.check_trace(core_path, paths)
    assert ok is False and code == "admit" and any(row.startswith("value:oracle") for row in rows), (code, rows)

    scored = V.trace_emit("propose", run, skill, parent, {
        "binder": "aa:ACD", "pmid": "pmid:1", "score": "0.9", "target": "uniprot:P12345",
    })
    core_path, paths = _write_trace("trace_score", core, [("a1.trace", header + "\n".join([call, pin, scored]) + "\n")])
    ok, code, rows = V.check_trace(core_path, paths)
    assert ok is False and code == "admit" and any(row.startswith("fields") for row in rows), (code, rows)


def test_trace_same_molecule_is_R9_and_hit_emit_is_R10():
    import hashlib
    core = (
        "%trace-core/1\n"
        'bound-n:"1"\n'
        'bound-tok:"8000"\n'
        'skill:"propose-pairs"\n'
        'spec:"aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"\n'
    )
    run = hashlib.sha256(core.encode("utf-8")).hexdigest()
    skill = "propose-pairs"
    call = V.trace_emit("call", run, skill, "^0", {})
    pin = V.trace_emit("pin", run, skill, "^" + V.trace_call_id(run, skill),
                       {"path": "graph.json", "rev": "c" * 40})
    parent = "^" + pin.split(" ", 2)[1]
    first = V.trace_emit("propose", run, skill, parent, {
        "binder": "aa:ACD", "pmid": "pmid:1", "target": "uniprot:P12345",
    })
    second = V.trace_emit("propose", run, skill, parent, {
        "binder": "helm:PEPTIDE1{A.C.D}$$$$", "pmid": "pmid:2", "target": "uniprot:P12345",
    })
    halt = V.trace_emit("halt", run, skill, parent, {
        "bound-n": "1", "bound-tok": "8000", "oracle": "not-discharged",
    })
    header = f"%trace/1 core={run} spec={'a' * 40}\n"
    body = header + "\n".join([call, pin, first, second, halt]) + "\n"
    core_path, paths = _write_trace("trace_r9", core, [("a1.trace", body)])
    ok, code, rows = V.check_trace(core_path, paths)
    assert ok is False and code == "R9", (code, rows)

    dcore = core.replace('skill:"propose-pairs"', 'skill:"design-binder"')
    drun = hashlib.sha256(dcore.encode("utf-8")).hexdigest()
    dskill = "design-binder"
    dcall = V.trace_emit("call", drun, dskill, "^0", {})
    dpin = V.trace_emit("pin", drun, dskill, "^" + V.trace_call_id(drun, dskill),
                        {"path": "graph.json", "rev": "d" * 40})
    dparent = "^" + dpin.split(" ", 2)[1]
    ctx = V.trace_emit("context", drun, dskill, dparent, {
        "binder": "aa:ACD", "gloss": "stop", "pmid": "pmid:1",
        "target": "uniprot:P12345", "verdict": "hit-same-indication",
    })
    emitted = V.trace_emit("emit", drun, dskill, dparent, {
        "binder": "aa:ACDE", "disclaimer": V.BANNER, "kind": "hypothesis", "target": "uniprot:P12345",
    })
    dhalt = V.trace_emit("halt", drun, dskill, dparent, {
        "bound-n": "1", "bound-tok": "8000", "oracle": "not-discharged",
    })
    dheader = f"%trace/1 core={drun} spec={'a' * 40}\n"
    dbody = dheader + "\n".join([dcall, dpin, ctx, emitted, dhalt]) + "\n"
    core_path, paths = _write_trace("trace_r10", dcore, [("a1.trace", dbody)])
    ok, code, rows = V.check_trace(core_path, paths)
    assert ok is False and code == "R10", (code, rows)
    # the same head without the emit is a result: the catalogue hit stops the design
    dbody = dheader + "\n".join([dcall, dpin, ctx, dhalt]) + "\n"
    core_path, paths = _write_trace("trace_hit", dcore, [("a1.trace", dbody)])
    ok, code, rows = V.check_trace(core_path, paths)
    assert ok and code == "result", (code, rows)
    # admission refuse, no catalogue pin: halt parents the call
    call_parent = "^" + V.trace_call_id(drun, dskill)
    refused = V.trace_emit("refuse", drun, dskill, call_parent, {"gate": "species", "subject": "Mus"})
    stopped = V.trace_emit("halt", drun, dskill, call_parent, {
        "bound-n": "1", "bound-tok": "8000", "oracle": "not-discharged",
    })
    nobody = dheader + "\n".join([dcall, refused, stopped]) + "\n"
    core_path, paths = _write_trace("trace_nopin", dcore, [("a1.trace", nobody)])
    ok, code, rows = V.check_trace(core_path, paths)
    assert ok and code == "result", (code, rows)



if __name__ == "__main__":
    fns = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    failed = 0
    for fn in fns:
        try:
            fn(); print(f"PASS {fn.__name__}")
        except AssertionError as e:
            failed += 1; print(f"FAIL {fn.__name__}: {e}")
    print(f"\n{len(fns)-failed}/{len(fns)} passed")
    sys.exit(1 if failed else 0)
