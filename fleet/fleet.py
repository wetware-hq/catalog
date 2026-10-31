#!/usr/bin/env python3
"""Harness that runs one `agent.fleet` fleet and records it as BENCH and TRACES artifacts.

Usage:
    fleet.py preflight --budget-usd 2.00            # price and probe every live service; spend nothing
    fleet.py run --target uniprot:P01111 --indication "..." --out DIR [--live]
    fleet.py verify DIR                             # hand the run directory to verifier/verify.py --trace

`fleet.py run` executes `skills/design-binder.md` over a fleet of workers and writes, per worker, a
`.bench` scratchpad line set (systems/use-bench.md) and a `.trace` act log (traces/record-fleet-traces.md).
The run directory lives outside this repository, as both systems require.

The trace grammar is not restated here. Lines are emitted through `verifier/verify.py`'s own
`trace_emit`, so the harness and the checker share one definition of the preimage.

Standard library only, Python >= 3.9. `modal` is imported lazily and only by `--live`; without it the
Modal step records `unavailable` rather than failing the run.
"""
from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import os
import re
import ssl
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parent


def _load_verifier():
    """Import verifier/verify.py by path. The verifier is read-only to every agent; this reads it."""
    spec = importlib.util.spec_from_file_location("catalog_verify", REPO / "verifier" / "verify.py")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module  # dataclasses resolves annotations through sys.modules
    spec.loader.exec_module(module)
    return module


V = _load_verifier()
BANNER = V.BANNER
SKILL = "design-binder"

# ---- live services ---------------------------------------------------------------------------------

GITHUB_API = "https://api.github.com"
CATALOGUE_REPO = "wetware-hq/catalog"
UNIPROT_API = "https://rest.uniprot.org/uniprotkb"
BOLTZ_BASE = os.environ.get("BOLTZ_API_BASE", "https://api.boltz.bio/compute/v1")
OPENROUTER_API = "https://openrouter.ai/api/v1"
MODAL_APP = "wetware-bindi-fleet"
HUMAN_TAXON = 9606

#: One worker per model. Breadth over independent methods is the point (design-binder section 5), so the
#: panel spans vendors rather than sizes of one family.
DEFAULT_MODELS = (
    "anthropic/claude-haiku-4.5",
    "openai/gpt-4.1-mini",
    "google/gemini-2.5-flash",
    "deepseek/deepseek-v3.2",
    "qwen/qwen3-14b",
    "meta-llama/llama-3.3-70b-instruct",
)

#: Worker basenames are the one free parameter of a trace file (traces/record-fleet-traces.md, Freedom = 1).
_WORKER_RE = re.compile(r"^[a-z][a-z0-9-]{0,31}$")


class Unavailable(Exception):
    """A source did not answer. Retry, cache nothing (follow-agent-contract.md section 7)."""

    def __init__(self, source: str, detail: str):
        self.source = source
        self.detail = detail
        super().__init__(f"{source}: {detail}")


def _http(method, url, *, headers=None, body=None, timeout=60, source="http"):
    data = json.dumps(body).encode("utf-8") if body is not None else None
    head = dict(headers or {})
    if data is not None:
        head.setdefault("content-type", "application/json")
    head.setdefault("accept", "application/json")
    request = urllib.request.Request(url, data=data, headers=head, method=method)
    try:
        with urllib.request.urlopen(request, timeout=timeout, context=ssl.create_default_context()) as response:
            raw = response.read().decode("utf-8")
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")[:400]
        raise Unavailable(source, f"HTTP {exc.code}: {detail}") from None
    except (urllib.error.URLError, OSError, TimeoutError) as exc:
        raise Unavailable(source, f"{type(exc).__name__}: {exc}") from None
    return json.loads(raw) if raw.strip() else {}


def utc_day() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d")


# ---- BENCH ---------------------------------------------------------------------------------------
# systems/use-bench.md. H is SHA-256 over the canonical bytes: fields sorted by key, single spaces,
# the id elided. Every node names the run inside the bytes its own name covers (section 6.2), so `run`
# is written as a field on every line.

BENCH_ID_LEN = 12
_BENCH_TOKEN_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:/-]*$")


def bench_value(value) -> str:
    if isinstance(value, bool):
        raise ValueError("bench values have no boolean production")
    if isinstance(value, int):
        return str(value)
    if isinstance(value, float):
        return repr(float(value))
    if isinstance(value, (list, tuple)):
        return "[" + ",".join(bench_value(v) for v in value) + "]"
    text = str(value)
    if _BENCH_TOKEN_RE.match(text) and '"' not in text:
        return text
    return '"' + text.replace('"', "") + '"'


def bench_line(tier: int, parents, fields: dict) -> str:
    """One `.bench` node. `parents` is '^0' (the core alone) or '^id[,id...]'."""
    if tier not in (1, 2, 3):
        raise ValueError("a line that does not begin with 1, 2 or 3 is not a record")
    body = " ".join(f"{k}:{bench_value(v)}" for k, v in sorted(fields.items()))
    preimage = f"{tier} {parents}" + (f" {body}" if body else "")
    ident = hashlib.sha256(preimage.encode("utf-8")).hexdigest()[:BENCH_ID_LEN]
    return f"{tier} {ident} {parents}" + (f" {body}" if body else "")


def bench_id(line: str) -> str:
    return line.split(" ", 2)[1]


def bench_core_bytes(params: dict) -> bytes:
    """The immutable core. Its own hash is the run id, so it cannot carry a `core=` header (section 6.1)."""
    out = ["%bench-core/1"]
    out += [f'{k}:"{params[k]}"' for k in sorted(params)]
    return ("\n".join(out) + "\n").encode("utf-8")


# ---- live adapters -------------------------------------------------------------------------------


def pin_catalogue(ref="main"):
    """Pin the read to a commit SHA and return (sha, graph). Never a branch tip (section 7)."""
    head = _http("GET", f"{GITHUB_API}/repos/{CATALOGUE_REPO}/commits/{ref}",
                 headers=_gh_headers(), source="github")
    sha = head.get("sha")
    if not re.fullmatch(r"[0-9a-f]{40}", sha or ""):
        raise Unavailable("github", "no commit sha for the catalogue read")
    blob = _http("GET", f"{GITHUB_API}/repos/{CATALOGUE_REPO}/contents/graph.json?ref={sha}",
                 headers=_gh_headers(), source="github")
    import base64
    raw = base64.b64decode(blob["content"])
    return sha, json.loads(raw)


def _gh_headers():
    head = {"accept": "application/vnd.github+json", "user-agent": "catalog-fleet"}
    token = os.environ.get("GITHUB_TOKEN") or os.environ.get("GH_TOKEN")
    if token:
        head["authorization"] = f"Bearer {token}"
    return head


def reverse_index(graph: dict, target: str):
    """target -> binders, built by the reader at read time. Never stored (section 7)."""
    out = {}
    for dictionary in ("pair", "preclinical"):
        for binder, targets in (graph.get(dictionary) or {}).items():
            if target in targets:
                out.setdefault(dictionary, {})[binder] = list(targets[target])
    return out


def uniprot_record(accession: str):
    """Target admission needs the organism and the sequence; both come from the authority."""
    bare = accession.split(":", 1)[1].split("-", 1)[0]
    fields = "accession,organism_name,protein_name,sequence,ft_domain,cc_tissue_specificity"
    data = _http("GET", f"{UNIPROT_API}/{bare}.json?fields={fields}", source="uniprot")
    organism = data.get("organism") or {}
    return {
        "accession": data.get("primaryAccession"),
        "taxon": organism.get("taxonId"),
        "organism": organism.get("scientificName"),
        "sequence": ((data.get("sequence") or {}).get("value")) or "",
        "length": (data.get("sequence") or {}).get("length"),
        "type": data.get("entryType", ""),
    }


def boltz_auth():
    """GET /auth/me. Free and read-only; proves the key resolves to a workspace before anything is spent."""
    key = os.environ.get("BOLTZ_API_KEY") or os.environ.get("boltz_api_key") or ""
    if not key.strip():
        raise Unavailable("boltz", "BOLTZ_API_KEY is not set")
    return _http("GET", f"{BOLTZ_BASE}/auth/me", headers={"x-api-key": key.strip()}, source="boltz")


def boltz_estimate(body: dict):
    """POST /protein/design/estimate-cost. Free, read-only, submits nothing."""
    key = os.environ.get("BOLTZ_API_KEY") or os.environ.get("boltz_api_key") or ""
    if not key.strip():
        raise Unavailable("boltz", "BOLTZ_API_KEY is not set")
    return _http("POST", f"{BOLTZ_BASE}/protein/design/estimate-cost",
                 headers={"x-api-key": key.strip()}, body=body, source="boltz")


def boltz_submit(body: dict, *, idempotency_key: str):
    """Submit one paid design run. Call only after estimate <= the pre-registered cap."""
    key = os.environ.get("BOLTZ_API_KEY") or os.environ.get("boltz_api_key") or ""
    if not key.strip():
        raise Unavailable("boltz", "BOLTZ_API_KEY is not set")
    payload = dict(body, idempotency_key=idempotency_key)
    return _http("POST", f"{BOLTZ_BASE}/protein/design",
                 headers={"x-api-key": key.strip()}, body=payload, timeout=120, source="boltz")


def boltz_status(job_id: str):
    key = os.environ.get("BOLTZ_API_KEY") or os.environ.get("boltz_api_key") or ""
    if not key.strip():
        raise Unavailable("boltz", "BOLTZ_API_KEY is not set")
    return _http("GET", f"{BOLTZ_BASE}/protein/design/{job_id}",
                 headers={"x-api-key": key.strip()}, source="boltz")


def boltz_design_body(target_sequence: str, num_proteins: int):
    """The legacy-compatible binder request accepted by the hosted design API."""
    return {
        "num_proteins": int(num_proteins),
        "target": {
            "type": "no_template",
            "entities": [{"type": "protein", "chain_ids": ["A"], "value": target_sequence}],
        },
        "binder_specification": {
            "type": "no_template",
            "modality": "custom_protein",
            "entities": [{
                "type": "designed_protein", "chain_ids": ["B"],
                "value": f"{BRIEF_MIN_AA}..{BRIEF_MAX_AA}",
            }],
        },
    }


def openrouter_key():
    key = os.environ.get("OPENROUTER_API_KEY") or os.environ.get("openrouter_api_key") or ""
    if not key.strip():
        raise Unavailable("openrouter", "OPENROUTER_API_KEY is not set")
    return key.strip()


def openrouter_budget():
    data = _http("GET", f"{OPENROUTER_API}/key", headers={"authorization": f"Bearer {openrouter_key()}"},
                 source="openrouter")
    return data.get("data") or {}


def openrouter_prices(models):
    data = _http("GET", f"{OPENROUTER_API}/models", source="openrouter").get("data") or []
    by_id = {m["id"]: m for m in data}
    out = {}
    for model in models:
        entry = by_id.get(model)
        if entry is None:
            out[model] = None
            continue
        pricing = entry.get("pricing") or {}
        out[model] = (float(pricing.get("prompt") or 0.0), float(pricing.get("completion") or 0.0))
    return out


def openrouter_chat(model, prompt, *, max_tokens=2600, timeout=240):
    body = {
        "model": model,
        "messages": [{"role": "user", "content": prompt}],
        "max_tokens": max_tokens,
        "temperature": 0.7,
    }
    data = _http("POST", f"{OPENROUTER_API}/chat/completions",
                 headers={"authorization": f"Bearer {openrouter_key()}"},
                 body=body, timeout=timeout, source=f"openrouter/{model}")
    choices = data.get("choices") or []
    if not choices:
        raise Unavailable(f"openrouter/{model}", f"no choices: {json.dumps(data)[:200]}")
    usage = data.get("usage") or {}
    finish = choices[0].get("finish_reason") or choices[0].get("native_finish_reason")
    if finish == "length":
        # A reply cut off mid-object is not a short answer, it is no answer: the JSON never closes.
        # Recording it as zero candidates would file a service failure as an empty design space.
        raise Unavailable(f"openrouter-{_slug(model)}-truncated",
                          f"reply hit the {max_tokens}-token ceiling without closing its JSON")
    text = (choices[0].get("message") or {}).get("content") or ""
    return text, usage


def _slug(model: str) -> str:
    """A `source` value is [A-Za-z0-9._:/-]{1,64} (traces/record-fleet-traces.md section 1)."""
    return re.sub(r"[^A-Za-z0-9._:/-]", "-", model)[:40]


def modal_call(function: str, payload, *, timeout=900):
    """Invoke one deployed Modal function. The SDK is optional; absent, the step is `unavailable`."""
    try:
        import modal  # noqa: PLC0415 - optional, live-only dependency
    except ImportError:
        raise Unavailable("modal", "the modal SDK is not installed") from None
    os.environ.setdefault("MODAL_TOKEN_ID", os.environ.get("modal_token_id", ""))
    os.environ.setdefault("MODAL_TOKEN_SECRET", os.environ.get("modal_token_secret", ""))
    try:
        handle = modal.Function.from_name(MODAL_APP, function)
        return handle.remote(payload)
    except Exception as exc:  # the SDK raises its own hierarchy; any failure is the source not answering
        raise Unavailable(f"modal/{function}", f"{type(exc).__name__}: {exc}"[:300]) from None


# ---- stage-one screens (skills/design-binder.md section 6) ------------------------------------------
# They exclude; they never penalise. A candidate failing one is out and the report names the screen.

HYDROPHOBIC = set("AVILMFWYC")
#: Approved-antibody range for the window-fraction patch score used below. Local convention, not a
#: figure derived from a published set of marketed therapeutics.
PATCH_WINDOW = 9
PATCH_BAR = 0.78


def developability(sequence: str):
    """Return (ok, reason). Unpaired cysteine, N-glycosylation sequon, Asn-Gly, Asp-Pro, patch score.

    section 6 qualifies the sequon and motif screens with "in a CDR". A de novo miniprotein has no CDR,
    so for a scaffold without one they are applied over the whole chain and the report says so.
    """
    if sequence.count("C") % 2 == 1:
        return False, "unpaired cysteine"
    for i in range(len(sequence) - 2):
        if sequence[i] == "N" and sequence[i + 1] != "P" and sequence[i + 2] in "ST":
            return False, f"N-glycosylation sequon at {i + 1}"
    if "NG" in sequence:
        return False, f"Asn-Gly at {sequence.index('NG') + 1}"
    if "DP" in sequence:
        return False, f"Asp-Pro at {sequence.index('DP') + 1}"
    for i in range(len(sequence) - PATCH_WINDOW + 1):
        window = sequence[i:i + PATCH_WINDOW]
        fraction = sum(1 for c in window if c in HYDROPHOBIC) / PATCH_WINDOW
        if fraction > PATCH_BAR:
            return False, f"hydrophobic patch {fraction:.2f} at {i + 1}"
    return True, "no stage-one developability liability"


def canonical_aa(chains):
    """An `aa:` key: segments non-decreasing by byte order (follow-agent-contract.md section 3)."""
    return "aa:" + "/".join(sorted(chains))


def valid_binder(key: str) -> bool:
    return V._trace_binder_ok(key)


def admit_candidate(sequence: str):
    """Is this an admissible binder key for this brief? Returns (key, reason-or-None).

    `follow-agent-contract.md` section 3 bounds the alphabet but not the length, so the length window
    comes from the brief. Both failures land on the one gate the trace carrier set offers, `grammar`.
    """
    if not sequence:
        return "", "empty sequence"
    key = canonical_aa([sequence])
    if not valid_binder(key):
        return key, "not a section 3 aa: key"
    if not BRIEF_MIN_AA <= len(sequence) <= BRIEF_MAX_AA:
        return key, f"{len(sequence)} aa outside the brief window {BRIEF_MIN_AA}-{BRIEF_MAX_AA}"
    return key, None


# ---- the fleet -------------------------------------------------------------------------------------

#: The brief's length window. Part of the specification every worker carries (design-binder section 5),
#: so a candidate outside it has not met the brief and is refused rather than screened.
BRIEF_MIN_AA = 45
BRIEF_MAX_AA = 110

WORKER_PROMPT = """You are one scientist agent in a parallel fleet designing a de novo protein binder.

Target: {target} ({protein}, {organism}), length {length} aa.
Indication: {indication}
Target sequence (first 240 aa shown): {head}

Design {k} candidate binders. Breadth is the point: the fleet compares genuinely different hypotheses,
so pick independent scaffolds (minibinder, designed miniprotein, nanobody/single-domain, constrained
peptide, repeat protein) rather than variations of one.

Hard constraints on every sequence you return. A sequence breaking any of them is discarded:
- 20 standard L-amino acids only (ACDEFGHIKLMNPQRSTVWY), one chain, {lo} to {hi} residues. Count them.
- An even number of cysteines, or none at all.
- No N-X-S or N-X-T motif (X not P), no "NG", no "DP" anywhere.
- No tandem repeat: never repeat any 4-residue motif more than twice. A low-complexity repeat is not a
  design, and a run of one motif until the token limit is a failed answer.

Keep each rationale under 200 characters so the whole reply fits. Return STRICT JSON only, no prose and
no code fence:
{{"candidates":[{{"sequence":"...","scaffold":"...","epitope":"...","rationale":"..."}}]}}
"""


def parse_candidates(text: str):
    """LLMs fence and prefix. Take the first balanced JSON object and read `candidates` out of it."""
    start = text.find("{")
    while start != -1:
        depth, in_string, escape = 0, False, False
        for i in range(start, len(text)):
            ch = text[i]
            if in_string:
                if escape:
                    escape = False
                elif ch == "\\":
                    escape = True
                elif ch == '"':
                    in_string = False
                continue
            if ch == '"':
                in_string = True
            elif ch == "{":
                depth += 1
            elif ch == "}":
                depth -= 1
                if depth == 0:
                    try:
                        obj = json.loads(text[start:i + 1])
                    except ValueError:
                        break
                    if isinstance(obj, dict) and isinstance(obj.get("candidates"), list):
                        return obj["candidates"]
                    break
        start = text.find("{", start + 1)
    return []


class Run:
    """One fleet run. Holds the immutable cores and collects per-worker BENCH and TRACES lines."""

    def __init__(self, *, target, indication, spec_sha, bound_n, bound_tok, models, live):
        self.target = target
        self.indication = indication
        self.spec_sha = spec_sha
        self.bound_n = int(bound_n)
        self.bound_tok = int(bound_tok)
        self.models = list(models)
        self.live = live
        self.trace_core = (
            "%trace-core/1\n"
            f'bound-n:"{self.bound_n}"\n'
            f'bound-tok:"{self.bound_tok}"\n'
            f'skill:"{SKILL}"\n'
            f'spec:"{spec_sha}"\n'
        ).encode("utf-8")
        self.run = hashlib.sha256(self.trace_core).hexdigest()
        self.call_id = V.trace_call_id(self.run, SKILL)
        self.bench_core = bench_core_bytes({
            "bound-n": self.bound_n, "bound-tok": self.bound_tok, "skill": SKILL,
            "spec": spec_sha, "target": target, "indication": indication,
        })
        self.bench_run = hashlib.sha256(self.bench_core).hexdigest()
        self.trace_lines = {}   # worker -> [line]
        self.bench_lines = {}   # worker -> [line]
        self.pin_id = None
        self.notes = []
        self.spend = {"openrouter_usd": 0.0, "prompt_tokens": 0, "completion_tokens": 0, "calls": 0}

    # -- trace ---------------------------------------------------------------------------------
    def trace(self, worker, act, parent, fields):
        line = V.trace_emit(act, self.run, SKILL, parent, fields)
        self.trace_lines.setdefault(worker, []).append(line)
        return line

    def trace_all(self, act, parent, fields):
        """A run-level act. Every worker writes the same bytes; set union merges them to one node."""
        line = V.trace_emit(act, self.run, SKILL, parent, fields)
        for worker in self.workers():
            self.trace_lines.setdefault(worker, []).append(line)
        return line

    def workers(self):
        return [self.worker_name(i) for i in range(len(self.models))]

    def worker_name(self, index):
        name = f"w{index + 1}"
        if not _WORKER_RE.match(name):
            raise ValueError(f"worker basename {name!r} has no production")
        return name

    # -- bench ---------------------------------------------------------------------------------
    def bench(self, worker, tier, parents, fields):
        fields = dict(fields, run=self.bench_run, w=worker)
        line = bench_line(tier, parents, fields)
        self.bench_lines.setdefault(worker, []).append(line)
        return bench_id(line)

    # -- write ---------------------------------------------------------------------------------
    def write(self, out: Path):
        out.mkdir(parents=True, exist_ok=True)
        (out / "core.trace").write_bytes(self.trace_core)
        (out / "core.bench").write_bytes(self.bench_core)
        for worker in self.workers():
            lines = self.trace_lines.get(worker)
            if lines:
                header = f"%trace/1 core={self.run} spec={self.spec_sha}\n"
                (out / f"{worker}.trace").write_text(header + "".join(l + "\n" for l in lines), encoding="utf-8")
            # One `<worker>.bench` per worker (systems/use-bench.md section 3), header-only where the
            # worker appended nothing: an absent file and an empty head are different claims.
            bench = self.bench_lines.get(worker) or []
            header = f"%bench/1 core={self.bench_run}\n"
            (out / f"{worker}.bench").write_text(header + "".join(l + "\n" for l in bench), encoding="utf-8")
        return out


def run_fleet(*, target, indication, models, out, live, bound_tok, bound_n=None, k=3, timeout=180):
    """Execute skills/design-binder.md over a fleet, and record it. Returns the report."""
    spec_sha = repo_head_sha()
    models = list(models)
    bound_n = int(bound_n if bound_n is not None else len(models) * k)
    run = Run(target=target, indication=indication, spec_sha=spec_sha, bound_n=bound_n,
              bound_tok=bound_tok, models=models, live=live)
    report = {"target": target, "indication": indication, "spec": spec_sha, "run": run.run,
              "bench_run": run.bench_run, "models": models, "live": live,
              "started": datetime.now(timezone.utc).isoformat(timespec="seconds")}

    run.trace_all("call", "^0", {})
    call_parent = "^" + run.call_id

    # -- section 3 target admission. Pre-pin gates: a refusal here leaves the run with no pin. ----
    if not V.UNIPROT_RE.match(target):
        run.trace_all("refuse", call_parent, {"gate": "grammar", "subject": target})
        return _halt_unpinned(run, report, out, "grammar")
    if not indication or not indication.strip():
        run.trace_all("refuse", call_parent, {"gate": "indication-absent", "subject": target})
        return _halt_unpinned(run, report, out, "indication-absent")
    try:
        record = uniprot_record(target)
    except Unavailable as exc:
        run.trace_all("unavailable", call_parent, _source_fields(target, exc, "catalogue"))
        run.notes.append(f"target admission: {exc}")
        record = None
    if record is not None:
        report["target_record"] = {k2: v for k2, v in record.items() if k2 != "sequence"}
        if record["taxon"] != HUMAN_TAXON:
            run.trace_all("refuse", call_parent,
                          {"gate": "species", "subject": f"{target} is {record['organism']}"})
            return _halt_unpinned(run, report, out, "species")
        if not record["sequence"]:
            run.trace_all("refuse", call_parent, {"gate": "not-protein", "subject": target})
            return _halt_unpinned(run, report, out, "not-protein")
    if record is None:
        # The authority did not answer, so species cannot be established and design must not fire.
        run.trace_all("refuse", call_parent, {"gate": "species", "subject": f"{target} unverified"})
        return _halt_unpinned(run, report, out, "species-unverified")

    # -- section 4 look it up before designing it ------------------------------------------------
    sha, graph = pin_catalogue()
    pin = run.trace_all("pin", call_parent, {"path": "graph.json", "rev": sha})
    run.pin_id = pin.split(" ", 2)[1]
    pin_parent = "^" + run.pin_id
    report["catalogue_rev"] = sha

    index = reverse_index(graph, target)
    evidenced = index.get("pair") or {}
    if evidenced:
        binder = sorted(evidenced)[0]
        pmid = sorted(evidenced[binder])[0]
        # The indication is not in the file. Absent a read paper this run cannot claim the hit is in
        # this indication, and the honest verdict is the weaker one.
        run.trace_all("context", pin_parent, {
            "binder": binder, "gloss": "transfers-not", "pmid": pmid,
            "target": target, "verdict": "hit-other-indication"})
        report["catalogue_context"] = {"verdict": "hit-other-indication", "binder": binder, "pmid": pmid}
    else:
        run.trace_all("context", pin_parent, {
            "gloss": "not-a-negative", "target": target, "verdict": "absent"})
        report["catalogue_context"] = {"verdict": "absent"}

    # Boltz is the design engine, not an optional scorer. Authenticate and price the exact request
    # before the advisory panel runs; OpenRouter must never silently substitute for this step.
    if live:
        try:
            boltz_auth()
            body = boltz_design_body(record["sequence"], bound_n)
            report["boltz_estimate"] = boltz_estimate(body)
        except Unavailable as exc:
            run.trace_all("unavailable", pin_parent, _source_fields(target, exc, "generator"))
            run.trace_all("halt", pin_parent, {
                "bound-n": str(run.bound_n), "bound-tok": str(run.bound_tok),
                "oracle": "not-discharged"})
            report["refused"] = "boltz-unavailable"
            report["boltz_issue"] = exc.detail
            report["workers"] = []
            report["emitted"] = []
            report["post_pin_refusals"] = []
            report["spend"] = run.spend
            report["notes"] = run.notes
            report["out"] = str(run.write(Path(out)))
            return report

    # -- section 5 fan out ------------------------------------------------------------------------
    results = _fan_out(run, record, k=k, timeout=timeout) if live else []
    report["workers"] = []

    survivors = []
    for worker, model, outcome in results:
        entry = {"worker": worker, "model": model}
        if isinstance(outcome, Unavailable):
            run.trace(worker, "unavailable", pin_parent,
                      _source_fields(target, outcome, "generator"))
            run.bench(worker, 2, "^0", {"step": "design", "model": model, "status": "unavailable"})
            entry["status"] = "unavailable"
            entry["detail"] = outcome.detail[:200]
            report["workers"].append(entry)
            continue
        candidates, usage = outcome
        entry["status"] = "ok"
        entry["proposed"] = len(candidates)
        entry["screened"] = []
        design_ids = []
        for cand in candidates:
            sequence = re.sub(r"[^A-Z]", "", (cand.get("sequence") or "").upper())
            key, bad = admit_candidate(sequence)
            if bad is not None:
                # `grammar` is a PrePin gate, so this refusal parents the call even though the design
                # that produced it happened after the pin. See fleet/read-fleet.md on that overload.
                run.trace(worker, "refuse", call_parent, {"gate": "grammar", "subject": bad})
                entry["screened"].append({"key": key[:40], "screen": "grammar", "result": bad})
                continue
            node = run.bench(worker, 2, "^0", {
                "step": "design", "model": model, "binder": key,
                "scaffold": str(cand.get("scaffold", "unstated"))[:60], "n": len(sequence)})
            design_ids.append(node)
            ok, reason = developability(sequence)
            run.bench(worker, 2, f"^{node}", {
                "step": "screen", "screen": "developability",
                "verdict": "pass" if ok else "exclude", "reason": reason})
            if not ok:
                run.trace(worker, "refuse", pin_parent, {"gate": "developability", "subject": reason})
                entry["screened"].append({"key": key, "screen": "developability", "result": reason})
                continue
            survivors.append((worker, model, key, sequence, cand, node))
            entry["screened"].append({"key": key, "screen": "developability", "result": "pass"})
        entry["usage"] = usage
        entry["bench_designs"] = len(design_ids)
        report["workers"].append(entry)

    # -- section 6 the screens that need a predictor, and the scorer -------------------------------
    # Selectivity and immunogenicity need predicted affinity against the paralogue panel and an MHC-II
    # predictor. Both are the model step. Where the source does not answer the verdict is `unavailable`.
    emitted, refused = _screen_and_emit(run, survivors, pin_parent, target, live)
    report["emitted"] = emitted
    report["post_pin_refusals"] = refused

    run.trace_all("halt", pin_parent, {
        "bound-n": str(run.bound_n), "bound-tok": str(run.bound_tok), "oracle": "not-discharged"})
    report["spend"] = run.spend
    report["notes"] = run.notes
    report["out"] = str(run.write(Path(out)))
    report["finished"] = datetime.now(timezone.utc).isoformat(timespec="seconds")
    return report


def _source_fields(key, exc: Unavailable, step):
    source = re.sub(r"[^A-Za-z0-9._:/-]", "-", exc.source)[:64]
    return {"key": key, "release": "unspecified", "retrieved": utc_day(), "source": source, "step": step}


def _halt_unpinned(run, report, out, reason):
    run.trace_all("halt", "^" + run.call_id, {
        "bound-n": str(run.bound_n), "bound-tok": str(run.bound_tok), "oracle": "not-discharged"})
    report["refused"] = reason
    report["out"] = str(run.write(Path(out)))
    report["spend"] = run.spend
    report["notes"] = run.notes
    return report


def _fan_out(run, record, *, k, timeout):
    """One worker per model, in parallel, each carrying the same specification."""
    head = record["sequence"][:240]
    prompt = WORKER_PROMPT.format(
        target=run.target, protein=record.get("type", "protein"), organism=record["organism"],
        length=record["length"], head=head, indication=run.indication, k=k,
        lo=BRIEF_MIN_AA, hi=BRIEF_MAX_AA)

    def one(index_model):
        index, model = index_model
        worker = run.worker_name(index)
        try:
            text, usage = openrouter_chat(model, prompt, timeout=timeout)
        except Unavailable as exc:
            return worker, model, exc
        candidates = parse_candidates(text)
        if not candidates:
            # A reply with no readable candidates object is not an empty design space. Counting it as
            # zero candidates would report a parse failure as a scientific result.
            return worker, model, Unavailable(
                f"openrouter-{_slug(model)}-unparsed",
                f"reply carried no candidates object ({len(text)} chars)")
        return worker, model, (candidates, usage)

    with ThreadPoolExecutor(max_workers=max(1, len(run.models))) as pool:
        results = list(pool.map(one, enumerate(run.models)))
    for _, _, outcome in results:
        if not isinstance(outcome, Unavailable):
            usage = outcome[1] or {}
            run.spend["prompt_tokens"] += int(usage.get("prompt_tokens") or 0)
            run.spend["completion_tokens"] += int(usage.get("completion_tokens") or 0)
            run.spend["calls"] += 1
            cost = usage.get("cost")
            if cost is not None:
                run.spend["openrouter_usd"] += float(cost)
    return results


def _screen_and_emit(run, survivors, pin_parent, target, live):
    """Fail closed until the two killing assays exist. A submitted/running job is not a result."""
    emitted, refused = [], []
    for worker, model, key, sequence, cand, node in survivors:
        reason = "binding assay and paralogue counter-screen not run"
        run.trace(worker, "refuse", pin_parent, {"gate": "no-assay", "subject": reason})
        run.bench(worker, 2, f"^{node}", {
            "step": "screen", "screen": "killing-assays", "verdict": "refuse",
            "reason": reason})
        refused.append({"binder": key, "screen": "killing-assays", "result": "not-run"})
    return emitted, refused


def repo_head_sha():
    """The spec revision this run was decided against. Hex40, per the trace core."""
    env = os.environ.get("FLEET_SPEC_SHA")
    if env and re.fullmatch(r"[0-9a-f]{40}", env):
        return env
    head = (REPO / ".git" / "HEAD").read_text(encoding="utf-8").strip()
    if head.startswith("ref: "):
        ref = (REPO / ".git" / head[5:]).resolve()
        if ref.exists():
            return ref.read_text(encoding="utf-8").strip()
        packed = (REPO / ".git" / "packed-refs")
        if packed.exists():
            for line in packed.read_text(encoding="utf-8").splitlines():
                if line.endswith(" " + head[5:]):
                    return line.split(" ", 1)[0]
        raise RuntimeError("cannot resolve HEAD to a commit sha")
    return head


# ---- preflight -------------------------------------------------------------------------------------


def preflight(*, models, budget_usd, target="uniprot:Q9NZQ7", k=3, workers=None):
    """Price and probe every live service this fleet needs. Spends nothing.

    This is the cheapest-first stopping rule of skills/design-binder.md section 5, run as a gate:
    surface the Pareto-minimal option before spending anything beyond it, and refuse to launch where
    the projected cost crosses the stated bar.
    """
    models = list(models)
    workers = workers or len(models)
    checks = []
    state = {}
    budget = {"cap_usd": round(float(budget_usd), 4)}

    def probe(name, fn, *, spends=False, required=True):
        started = time.time()
        try:
            value = fn()
            checks.append({"service": name, "status": "ok", "ms": int((time.time() - started) * 1000),
                           "spends": spends, "required": required, "detail": value})
        except Unavailable as exc:
            checks.append({"service": name, "status": "unavailable", "ms": int((time.time() - started) * 1000),
                           "spends": spends, "required": required, "detail": exc.detail[:300]})
        except Exception as exc:  # a probe must never abort the preflight
            checks.append({"service": name, "status": "error", "ms": int((time.time() - started) * 1000),
                           "spends": spends, "required": required,
                           "detail": f"{type(exc).__name__}: {exc}"[:300]})

    def check_uniprot():
        state["target"] = uniprot_record(target)
        return {"target": target, "organism": state["target"]["organism"]}

    def check_boltz():
        identity = boltz_auth()
        record = state.get("target")
        if not record or not record.get("sequence"):
            raise Unavailable("boltz", "target sequence unavailable for cost estimate")
        count = max(10, workers * k)  # live API minimum, verified by its 400 response
        estimate = boltz_estimate(boltz_design_body(record["sequence"], count))
        budget["boltz_usd"] = float(estimate["estimated_cost_usd"])
        budget["boltz_designs"] = count
        return {
            "mode": identity.get("mode"), "workspace_id": identity.get("workspace_id"),
            "estimated_cost_usd": estimate.get("estimated_cost_usd"), "num_proteins": count,
        }

    probe("github/catalogue-pin", lambda: {"rev": pin_catalogue()[0]})
    probe("uniprot", check_uniprot)
    probe("ncbi/eutils", _probe_ncbi, required=False)
    probe("boltz/estimate", check_boltz)
    probe("modal/run_gates", lambda: {"gates": sorted(modal_call("run_gates", {}).keys())})

    # -- OpenRouter advisory spend plus the Boltz estimate is the total fleet projection ----------
    try:
        remaining = openrouter_budget()
        budget["key_limit_usd"] = remaining.get("limit")
        budget["key_remaining_usd"] = remaining.get("limit_remaining")
        prices = openrouter_prices(models)
        # One call per worker. The prompt is the target head plus the brief; the reply is k candidates.
        prompt_tokens, completion_tokens = 700, 1400
        rows = []
        total = 0.0
        for model in models:
            price = prices.get(model)
            if price is None:
                rows.append({"model": model, "status": "not-offered"})
                continue
            cost = price[0] * prompt_tokens + price[1] * completion_tokens
            total += cost
            rows.append({"model": model, "usd_per_worker": round(cost, 6),
                         "in_per_mtok": round(price[0] * 1e6, 4), "out_per_mtok": round(price[1] * 1e6, 4)})
        rows.sort(key=lambda r: r.get("usd_per_worker", 1e9))
        budget["models"] = rows
        budget["openrouter_usd"] = round(total, 6)
        budget["projected_usd"] = round(total + float(budget.get("boltz_usd", 0.0)), 6)
        budget["projected_candidates"] = workers * k
        cheapest = next((r for r in rows if "usd_per_worker" in r), None)
        budget["pareto_minimal"] = cheapest["model"] if cheapest else None
        budget["within_cap"] = (
            "boltz_usd" in budget and budget["projected_usd"] <= float(budget_usd)
        )
        checks.append({"service": "openrouter", "status": "ok", "spends": True,
                       "required": True, "detail": budget})
    except Unavailable as exc:
        budget["error"] = exc.detail[:300]
        budget["within_cap"] = False
        checks.append({"service": "openrouter", "status": "unavailable", "spends": True,
                       "required": True, "detail": exc.detail[:300]})

    launch = bool(budget.get("within_cap")) and all(
        c["status"] == "ok" for c in checks if c["required"])
    return {"checked": utc_day(), "budget": budget, "checks": checks, "launch": launch,
            "blocking": [c["service"] for c in checks if c["status"] != "ok" and c["required"]],
            "degraded": [c["service"] for c in checks if c["status"] != "ok" and not c["required"]]}


def _probe_ncbi():
    url = ("https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esummary.fcgi"
           "?db=pubmed&id=11248153&retmode=json")
    data = _http("GET", url, source="ncbi")
    return {"resolved": "11248153" in (data.get("result") or {})}


# ---- verify -----------------------------------------------------------------------------------------


def verify_run(out: Path):
    """Hand the run directory to the checker. Exit 0 is the judgement `result`."""
    out = Path(out)
    core = out / "core.trace"
    workers = sorted(p for p in out.glob("*.trace") if p.name != "core.trace")
    if not core.exists():
        return False, "R1", ["no core.trace"]
    ok, code, rows = V.check_trace(str(core), [str(p) for p in workers])
    return ok, code, rows


# ---- CLI ---------------------------------------------------------------------------------------------


def main(argv=None):
    parser = argparse.ArgumentParser(prog="fleet.py", description=__doc__.splitlines()[0])
    sub = parser.add_subparsers(dest="cmd", required=True)

    pre = sub.add_parser("preflight", help="price and probe every live service; spend nothing")
    pre.add_argument("--budget-usd", type=float, default=2.0)
    pre.add_argument("--target", default="uniprot:Q9NZQ7")
    pre.add_argument("--models", nargs="*", default=list(DEFAULT_MODELS))
    pre.add_argument("--candidates", type=int, default=3)
    pre.add_argument("--json", action="store_true")

    run = sub.add_parser("run", help="run one fleet and write its BENCH and TRACES artifacts")
    run.add_argument("--target", required=True)
    run.add_argument("--indication", required=True)
    run.add_argument("--out", required=True)
    run.add_argument("--models", nargs="*", default=list(DEFAULT_MODELS))
    run.add_argument("--candidates", type=int, default=3)
    run.add_argument("--bound-tok", type=int, default=60000)
    run.add_argument("--live", action="store_true", help="call the live services")
    run.add_argument("--json", action="store_true")

    ver = sub.add_parser("verify", help="decide the trace in a run directory")
    ver.add_argument("out")

    args = parser.parse_args(argv)

    if args.cmd == "preflight":
        report = preflight(models=args.models, budget_usd=args.budget_usd,
                           target=args.target, k=args.candidates)
        print(json.dumps(report, indent=2) if args.json else _format_preflight(report))
        return 0 if report["launch"] else 1

    if args.cmd == "run":
        report = run_fleet(target=args.target, indication=args.indication, models=args.models,
                           out=args.out, live=args.live, bound_tok=args.bound_tok, k=args.candidates)
        ok, code, rows = verify_run(Path(args.out))
        report["trace_judgement"] = {"ok": ok, "code": code, "rows": rows}
        print(json.dumps(report, indent=2) if args.json else _format_run(report))
        return 0 if ok else 1

    ok, code, rows = verify_run(Path(args.out))
    print(f"{code}" + ("" if ok else ": " + "; ".join(str(r) for r in rows)))
    return 0 if ok else 1


def _format_preflight(report):
    out = [f"PREFLIGHT {report['checked']}  launch={report['launch']}"]
    for check in report["checks"]:
        mark = {"ok": "PASS", "unavailable": "UNAVAIL", "error": "ERROR"}[check["status"]]
        detail = check["detail"]
        if isinstance(detail, dict) and check["service"] == "openrouter":
            detail = (f"projected ${detail.get('projected_usd')} of cap ${detail.get('cap_usd')}; "
                      f"cheapest {detail.get('pareto_minimal')}")
        out.append(f"  [{mark:7}] {check['service']:24} {'SPENDS' if check['spends'] else '      '} {detail}")
    if report["blocking"]:
        out.append("  blocking: " + ", ".join(report["blocking"]))
    if report["degraded"]:
        out.append("  degraded: " + ", ".join(report["degraded"]))
    return "\n".join(out)


def _format_run(report):
    out = [f"RUN {report['run'][:16]}  target={report['target']}  spec={report['spec'][:12]}"]
    if report.get("refused"):
        out.append(f"  refused before the pin: {report['refused']}")
    else:
        out.append(f"  catalogue rev {report.get('catalogue_rev', '?')[:12]} "
                   f"verdict {report.get('catalogue_context', {}).get('verdict')}")
    for worker in report.get("workers", []):
        out.append(f"  {worker['worker']:4} {worker['model']:34} {worker['status']:11} "
                   f"proposed={worker.get('proposed', 0)}")
    out.append(f"  emitted {len(report.get('emitted', []))}, "
               f"post-pin refusals {len(report.get('post_pin_refusals', []))}")
    judgement = report.get("trace_judgement") or {}
    out.append(f"  trace: {judgement.get('code')}")
    return "\n".join(out)


if __name__ == "__main__":
    sys.exit(main())
