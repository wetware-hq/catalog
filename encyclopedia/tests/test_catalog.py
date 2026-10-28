from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def run_cli(*args: str):
    from ecatalog.cli import main

    import io
    from contextlib import redirect_stdout

    buf = io.StringIO()
    code = None
    with redirect_stdout(buf):
        code = main(list(args))
    return code, buf.getvalue()


def test_lint_passes():
    code, out = run_cli("lint", "--json")
    assert code == 0, out
    assert json.loads(out)["ok"] is True


def test_references_in_sync():
    from ecatalog.refs import check_references_sync

    assert check_references_sync() == []


def test_query_get_git():
    code, out = run_cli("query", "get", "git-scm--git", "--json")
    assert code == 0, out
    assert json.loads(out)["entry"]["id"] == "git-scm--git"


def test_query_search():
    code, out = run_cli("query", "search", "Git", "--json")
    assert code == 0, out
    rows = json.loads(out)
    assert any(r["id"] == "git-scm--git" for r in rows)


def test_verify_rejects_bad_evidence():
    from ecatalog.pipeline import verify_draft

    draft = {
        "run_id": "t",
        "entry": {
            "id": "x--y",
            "category": "software/devtools/version-control",
            "sources": ["88b6b8e99a4059b695185efd7b888ee4d7f6ff1ba0f5a1ea350ca256826449ee"],
        },
        "fields": {
            "specs": {
                "license": {
                    "raw": "x",
                    "value": "x",
                    "source": "88b6b8e99a4059b695185efd7b888ee4d7f6ff1ba0f5a1ea350ca256826449ee",
                    "evidence": "this quote is not in the pro git snapshot",
                    "observed_at": "2026-10-28T00:00:00Z",
                }
            }
        },
    }
    _, errors = verify_draft(draft)
    assert errors


def test_research_idempotent_cas():
    from ecatalog.io import sha256_text, put_text_object

    t = "immutable snapshot body"
    assert put_text_object(t) == put_text_object(t)
    assert sha256_text(t) == put_text_object(t)


def test_strong_id_merge_units():
    from ecatalog.pipeline import _strong_id_key

    a = {"maker": {"name": "Acme"}, "identifiers": {"gtin": "1"}}
    b = {"maker": {"name": "Acme"}, "identifiers": {"gtin": "1"}}
    assert _strong_id_key(a) == _strong_id_key(b)
