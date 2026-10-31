"""Hermetic tests for the agent.fleet runner. Standard-library unittest only."""

from __future__ import annotations

import importlib.util
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
SPEC = importlib.util.spec_from_file_location("catalog_fleet", ROOT / "fleet" / "fleet.py")
fleet = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = fleet
SPEC.loader.exec_module(fleet)


class FleetTests(unittest.TestCase):
    def test_bench_line_is_content_addressed_and_field_order_independent(self):
        left = fleet.bench_line(2, "^0", {"z": 1, "a": "x"})
        right = fleet.bench_line(2, "^0", {"a": "x", "z": 1})
        self.assertEqual(left, right)
        self.assertRegex(left, r"^2 [0-9a-f]{12} \^0 a:x z:1$")

    def test_bench_refuses_untiered_values(self):
        with self.assertRaisesRegex(ValueError, "not a record"):
            fleet.bench_line(0, "^0", {})

    def test_candidate_admission_enforces_key_and_brief_length(self):
        key, reason = fleet.admit_candidate("A" * 45)
        self.assertEqual(key, "aa:" + "A" * 45)
        self.assertIsNone(reason)
        _, reason = fleet.admit_candidate("A" * 44)
        self.assertIn("outside the brief window", reason)
        _, reason = fleet.admit_candidate("B" * 50)
        self.assertIn("section 3", reason)

    def test_developability_kills_liabilities_without_weighting(self):
        clean = "EKQ" * 15
        self.assertEqual(fleet.developability(clean), (True, "no stage-one developability liability"))
        self.assertEqual(fleet.developability("C" + "A" * 44)[0], False)
        self.assertIn("N-glycosylation", fleet.developability("ANAS" + "A" * 41)[1])
        self.assertIn("Asn-Gly", fleet.developability("ANG" + "A" * 42)[1])
        self.assertIn("Asp-Pro", fleet.developability("ADP" + "A" * 42)[1])

    def test_parse_candidates_accepts_fenced_json_and_refuses_truncation(self):
        raw = 'prefix ```json\n{"candidates":[{"sequence":"AAAA"}]}\n```'
        self.assertEqual(fleet.parse_candidates(raw)[0]["sequence"], "AAAA")
        self.assertEqual(fleet.parse_candidates('{"candidates":[{"sequence":"AAAA"}]'), [])

    def test_pre_pin_refusal_still_decides_result(self):
        with tempfile.TemporaryDirectory() as tmp:
            report = fleet.run_fleet(
                target="bad", indication="research", models=["test/model"],
                out=tmp, live=False, bound_tok=100, bound_n=1, k=1,
            )
            self.assertEqual(report["refused"], "grammar")
            ok, code, _ = fleet.verify_run(Path(tmp))
            self.assertTrue(ok)
            self.assertEqual(code, "result")
            self.assertTrue((Path(tmp) / "w1.bench").exists())

    def test_boltz_unavailable_halts_before_advisory_models(self):
        record = {
            "accession": "P01111", "taxon": fleet.HUMAN_TAXON, "organism": "Homo sapiens",
            "sequence": "A" * 100, "length": 100, "type": "protein",
        }
        graph = {"version": 2, "pair": {}, "preclinical": {}}
        with tempfile.TemporaryDirectory() as tmp, \
                patch.object(fleet, "uniprot_record", return_value=record), \
                patch.object(fleet, "pin_catalogue", return_value=("a" * 40, graph)), \
                patch.object(fleet, "boltz_auth",
                             side_effect=fleet.Unavailable("boltz", "HTTP 401")), \
                patch.object(fleet, "_fan_out") as fan_out:
            report = fleet.run_fleet(
                target="uniprot:P01111", indication="research", models=["test/model"],
                out=tmp, live=True, bound_tok=100, bound_n=1, k=1,
            )
            self.assertEqual(report["refused"], "boltz-unavailable")
            fan_out.assert_not_called()
            ok, code, rows = fleet.verify_run(Path(tmp))
            self.assertTrue(ok, (code, rows))

    def test_preflight_treats_boltz_as_blocking(self):
        with patch.object(fleet, "pin_catalogue",
                          return_value=("a" * 40, {"version": 2, "pair": {}, "preclinical": {}})), \
                patch.object(fleet, "uniprot_record", return_value={"organism": "Homo sapiens"}), \
                patch.object(fleet, "_probe_ncbi", return_value={"resolved": True}), \
                patch.object(fleet, "boltz_auth",
                             side_effect=fleet.Unavailable("boltz", "HTTP 401")), \
                patch.object(fleet, "modal_call", return_value={"config": {}}), \
                patch.object(fleet, "openrouter_budget", return_value={"limit_remaining": 10}), \
                patch.object(fleet, "openrouter_prices", return_value={"test/model": (0.0, 0.0)}):
            result = fleet.preflight(models=["test/model"], budget_usd=1.0)
            self.assertFalse(result["launch"])
            self.assertEqual(result["blocking"], ["boltz/estimate"])

    def test_preflight_cap_includes_boltz_and_advisory_panel(self):
        record = {"organism": "Homo sapiens", "sequence": "E" * 100}
        common = (
            patch.object(fleet, "pin_catalogue",
                         return_value=("a" * 40, {"version": 2, "pair": {}, "preclinical": {}})),
            patch.object(fleet, "uniprot_record", return_value=record),
            patch.object(fleet, "_probe_ncbi", return_value={"resolved": True}),
            patch.object(fleet, "boltz_auth", return_value={"mode": "test", "workspace_id": "ws_test"}),
            patch.object(fleet, "boltz_estimate", return_value={"estimated_cost_usd": "0.5000"}),
            patch.object(fleet, "modal_call", return_value={"config": {}}),
            patch.object(fleet, "openrouter_budget", return_value={"limit_remaining": 10}),
            patch.object(fleet, "openrouter_prices", return_value={"test/model": (0.0001, 0.0)}),
        )
        with common[0], common[1], common[2], common[3], common[4], common[5], common[6], common[7]:
            result = fleet.preflight(models=["test/model"], budget_usd=0.60, k=1)
        self.assertTrue(result["launch"])
        self.assertEqual(result["budget"]["projected_usd"], 0.57)
        self.assertEqual(result["budget"]["boltz_designs"], 10)

    def test_terminal_screen_never_emits_without_two_assays(self):
        run = fleet.Run(
            target="uniprot:P01111", indication="research", spec_sha="a" * 40,
            bound_n=1, bound_tok=100, models=["test/model"], live=True,
        )
        survivor = (
            "w1", "test/model", "aa:" + "E" * 50, "E" * 50,
            {"scaffold": "miniprotein"}, "abc123",
        )
        emitted, refused = fleet._screen_and_emit(
            run, [survivor], "^" + "b" * 64, "uniprot:P01111", True,
        )
        self.assertEqual(emitted, [])
        self.assertEqual(refused[0]["screen"], "killing-assays")
        self.assertIn("gate:\"no-assay\"", run.trace_lines["w1"][0])

    def test_live_shape_with_fakes_writes_valid_trace_and_all_worker_heads(self):
        record = {
            "accession": "P01111", "taxon": fleet.HUMAN_TAXON, "organism": "Homo sapiens",
            "sequence": "A" * 100, "length": 100, "type": "protein",
        }
        graph = {"version": 2, "pair": {}, "preclinical": {}}
        outcomes = [
            ("w1", "test/one", ([{"sequence": "E" * 50, "scaffold": "miniprotein"}],
                                 {"prompt_tokens": 10, "completion_tokens": 20, "cost": 0.001})),
            ("w2", "test/two", fleet.Unavailable("test/two", "timeout")),
        ]
        with tempfile.TemporaryDirectory() as tmp, \
                patch.object(fleet, "uniprot_record", return_value=record), \
                patch.object(fleet, "pin_catalogue", return_value=("a" * 40, graph)), \
                patch.object(fleet, "boltz_auth", return_value={"workspace": "test"}), \
                patch.object(fleet, "boltz_estimate", return_value={"estimated_cost_usd": "0.01"}), \
                patch.object(fleet, "_fan_out", return_value=outcomes), \
                patch.object(fleet, "_screen_and_emit", return_value=([], [])):
            report = fleet.run_fleet(
                target="uniprot:P01111", indication="research",
                models=["test/one", "test/two"], out=tmp, live=True,
                bound_tok=1000, bound_n=2, k=1,
            )
            self.assertEqual(report["catalogue_context"]["verdict"], "absent")
            ok, code, rows = fleet.verify_run(Path(tmp))
            self.assertTrue(ok, (code, rows))
            self.assertEqual(sorted(p.name for p in Path(tmp).glob("w*.bench")),
                             ["w1.bench", "w2.bench"])


if __name__ == "__main__":
    unittest.main(verbosity=2)
