from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from ecatalog.graph import build_graph
from ecatalog.lint import lint_catalog
from ecatalog.pipeline import research_urls, run_dedup, validate_draft, verify_draft, write_entry
from ecatalog.query import get_entry, search
from ecatalog.refs import write_references_md


def _load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def main(argv: list[str] | None = None) -> int:
    argv = list(argv if argv is not None else sys.argv[1:])
    as_json = "--json" in argv
    if as_json:
        argv = [a for a in argv if a != "--json"]

    parser = argparse.ArgumentParser(prog="catalog")
    sub = parser.add_subparsers(dest="cmd", required=True)

    sub.add_parser("lint")
    ref = sub.add_parser("references")
    ref_sub = ref.add_subparsers(dest="ref_cmd", required=True)
    ref_sub.add_parser("refresh")

    p_res = sub.add_parser("research")
    p_res.add_argument("--url", action="append", required=True)
    p_res.add_argument("--run-id", required=True)

    p_ext = sub.add_parser("extract")
    p_ext.add_argument("--draft", type=Path, required=True)

    p_ver = sub.add_parser("verify")
    p_ver.add_argument("--draft", type=Path, required=True)
    p_ver.add_argument("--out", type=Path, required=True)

    p_write = sub.add_parser("write")
    p_write.add_argument("--verified", type=Path, required=True)
    p_write.add_argument("--run-id", required=True)

    p_dedup = sub.add_parser("dedup")
    p_dedup.add_argument("--run-id", required=True)

    p_graph = sub.add_parser("graph")
    g_sub = p_graph.add_subparsers(dest="graph_cmd", required=True)
    g_sub.add_parser("build")

    p_q = sub.add_parser("query")
    q_sub = p_q.add_subparsers(dest="query_cmd", required=True)
    q_get = q_sub.add_parser("get")
    q_get.add_argument("id")
    q_get.add_argument("--include-unverified", action="store_true")
    q_search = q_sub.add_parser("search")
    q_search.add_argument("text", nargs="?", default="")
    q_search.add_argument("--category")
    q_search.add_argument("--kind")
    q_search.add_argument("--maker")
    q_search.add_argument("--tag")
    q_search.add_argument("--include-unverified", action="store_true")

    args = parser.parse_args(argv)

    def out(data: object, code: int = 0) -> int:
        if as_json:
            print(json.dumps(data, indent=2))
        elif isinstance(data, str):
            print(data)
        else:
            print(json.dumps(data, indent=2))
        return code

    if args.cmd == "lint":
        errors = lint_catalog()
        return out({"ok": not errors, "errors": errors}, 1 if errors else 0)

    if args.cmd == "references" and args.ref_cmd == "refresh":
        body = write_references_md()
        return out({"ok": True, "bytes": len(body)})

    if args.cmd == "research":
        result = research_urls(args.url, args.run_id)
        return out(result, 1 if result.get("errors") else 0)

    if args.cmd == "extract":
        draft = _load_json(args.draft)
        errors = validate_draft(draft)
        return out({"ok": not errors, "errors": errors, "entry_id": draft.get("entry", {}).get("id")}, 1 if errors else 0)

    if args.cmd == "verify":
        draft = _load_json(args.draft)
        verified, errors = verify_draft(draft)
        if errors:
            return out({"ok": False, "errors": errors}, 1)
        args.out.write_text(json.dumps(verified, indent=2) + "\n", encoding="utf-8")
        return out({"ok": True, "out": str(args.out)})

    if args.cmd == "write":
        verified = _load_json(args.verified)
        path, _noop = write_entry(verified, args.run_id)
        return out({"ok": True, "path": str(path)})

    if args.cmd == "dedup":
        return out(run_dedup(args.run_id))

    if args.cmd == "graph" and args.graph_cmd == "build":
        return out({"ok": True, **build_graph()})

    if args.cmd == "query":
        inc = getattr(args, "include_unverified", False)
        try:
            if args.query_cmd == "get":
                return out(get_entry(args.id, include_unverified=inc))
            if args.query_cmd == "search":
                return out(
                    search(
                        args.text,
                        category=args.category,
                        kind=args.kind,
                        maker=args.maker,
                        tag=args.tag,
                        include_unverified=inc,
                    )
                )
        except KeyError:
            return out({"ok": False, "error": "not found"}, 1)

    return 2


if __name__ == "__main__":
    sys.exit(main())

# References:
# [22] Read-only query; writes only through pipeline commands.
