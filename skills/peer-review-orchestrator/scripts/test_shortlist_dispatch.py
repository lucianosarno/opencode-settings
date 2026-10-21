#!/usr/bin/env python3
"""Tests for shortlist → Task slug dispatch roster (no review folder required)."""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

import orchestrator as orch


class ShortlistDispatchTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        # Fake llms_peer_review layout: <repo>/process + reports shortlist
        self.process = self.root / "process"
        self.process.mkdir()
        reports = self.root / "tools" / "llm_selection" / "reports"
        reports.mkdir(parents=True)
        self.shortlist = reports / "ranking_shortlist_cursor_capability_weighted_latest.json"
        payload = {
            "fv": "1.6.1-test",
            "applications": {
                "d06_architecture_phase2": [
                    ["mimo-v2-5-0424", 300.0],
                    ["gpt-5-6-luna-low", 200.0],
                    ["gpt-5-6-luna-medium", 180.0],
                    ["gpt-5-6-sol", 150.0],
                    ["claude-sonnet-5", 140.0],
                    ["grok-4-5", 120.0],
                    ["composer-2-5", 100.0],
                ],
                "d06_architecture_phase5": [
                    ["mimo-v2-5-0424", 250.0],
                    ["gpt-5-6-luna-low", 210.0],
                    ["claude-fable-5", 160.0],
                ],
                "generic_phase2_proposal": [
                    ["gpt-5-6-terra-medium", 90.0],
                ],
                "generic_phase5_leader": [
                    ["claude-fable-5", 80.0],
                ],
                "generic_phase3_critique": [
                    ["gpt-5-6-sol-medium", 70.0],
                ],
            },
        }
        self.shortlist.write_text(json.dumps(payload), encoding="utf-8")

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def test_map_and_dedupe_families_and_providers(self) -> None:
        data = orch.load_shortlist(self.shortlist)
        app = orch.resolve_application_key(
            data, domain_code="d06_architecture", phase=2
        )
        self.assertEqual(app["application_key"], "d06_architecture_phase2")
        cands = orch.shortlist_task_candidates(data, app["application_key"])
        slugs = [r["task_slug"] for r in cands["selected"]]
        # Sol is same OpenAI vendor as Luna → skipped even though different family
        self.assertEqual(
            slugs,
            [
                "gpt-5.6-luna-low",
                "claude-sonnet-5-thinking-high",
                "cursor-grok-4.5-high-fast",
                "composer-2.5-fast",
            ],
        )
        providers = [r["provider"] for r in cands["selected"]]
        self.assertEqual(len(providers), len(set(providers)))
        reasons = {s["llm_code"]: s["reason"] for s in cands["skipped"]}
        self.assertEqual(reasons["mimo-v2-5-0424"], "not_in_task_map")
        self.assertTrue(reasons["gpt-5-6-luna-medium"].startswith("duplicate_family"))
        self.assertEqual(reasons["gpt-5-6-sol"], "duplicate_provider:OpenAI")

    def test_roster_fills_from_shortlist_unique_providers(self) -> None:
        roster = orch.build_dispatch_roster(
            llms_root=self.process,
            review_root=None,
            domain_code="d06",
            phase=2,
            slot_count=5,
            shortlist_path=self.shortlist,
        )
        slots = roster["slots"]
        self.assertEqual(slots["llm1"]["source"], "shortlist")
        self.assertEqual(slots["llm1"]["model_slug"], "gpt-5.6-luna-low")
        self.assertEqual(slots["llm1"]["provider"], "OpenAI")
        self.assertEqual(slots["llm2"]["model_slug"], "claude-sonnet-5-thinking-high")
        self.assertEqual(slots["llm2"]["provider"], "Anthropic")
        self.assertEqual(slots["llm3"]["model_slug"], "cursor-grok-4.5-high-fast")
        self.assertEqual(slots["llm4"]["model_slug"], "composer-2.5-fast")
        # Only 4 Task-dispatchable unique providers in the fixture; 5th stays open
        self.assertFalse(slots["llm5"]["resolved"])
        resolved_providers = [
            s["provider"] for s in slots.values() if s.get("resolved")
        ]
        self.assertEqual(len(resolved_providers), len(set(resolved_providers)))
        self.assertTrue(roster["unique_provider"])
        self.assertEqual(roster["fv"], "1.6.1-test")

    def test_phase5_leader_app(self) -> None:
        roster = orch.build_dispatch_roster(
            llms_root=self.process,
            review_root=None,
            domain_code="d06_architecture",
            phase=5,
            slot_count=2,
            shortlist_path=self.shortlist,
        )
        self.assertEqual(
            roster["application"]["application_key"], "d06_architecture_phase5"
        )
        # Without calculation fixture, quality basis falls back to shortlist value.
        # Leader phase fills highest slot first; Luna then Fable (different vendors)
        self.assertEqual(roster["slots"]["llm2"]["model_slug"], "gpt-5.6-luna-low")
        self.assertEqual(roster["slots"]["llm2"]["provider"], "OpenAI")
        self.assertEqual(
            roster["slots"]["llm1"]["model_slug"], "claude-fable-5-thinking-high"
        )
        self.assertEqual(roster["slots"]["llm1"]["provider"], "Anthropic")

    def test_phase5_leader_uses_quality_among_participants(self) -> None:
        """Leader = highest pure quality among phase-2 proposers, not value/cost."""
        reports = self.root / "tools" / "llm_selection" / "reports"
        calc = reports / "ranking_calculation_latest.json"
        # Phase2 shortlist prefers Luna (value). Quality report prefers Fable.
        payload = {
            "fv": "1.6.1-test",
            "applications": {
                "d06_architecture_phase2": [
                    ["gpt-5-6-luna-low", 300.0],
                    ["claude-fable-5", 100.0],
                    ["grok-4-5", 90.0],
                    ["composer-2-5", 80.0],
                ],
                "d06_architecture_phase5": [
                    ["gpt-5-6-luna-low", 400.0],
                    ["claude-fable-5", 50.0],
                ],
            },
        }
        self.shortlist.write_text(json.dumps(payload), encoding="utf-8")
        calc.write_text(
            json.dumps(
                {
                    "formula_version": "1.6.1-test",
                    "applications": {
                        "d06_architecture_phase5": {
                            "llms": [
                                {
                                    "llm_code": "gpt-5-6-luna-low",
                                    "calculation": {"quality": {"value": 0.40}},
                                },
                                {
                                    "llm_code": "claude-fable-5",
                                    "calculation": {"quality": {"value": 0.95}},
                                },
                                {
                                    "llm_code": "grok-4-5",
                                    "calculation": {"quality": {"value": 0.70}},
                                },
                                {
                                    "llm_code": "composer-2-5",
                                    "calculation": {"quality": {"value": 0.55}},
                                },
                            ]
                        }
                    },
                }
            ),
            encoding="utf-8",
        )
        roster = orch.build_dispatch_roster(
            llms_root=self.process,
            review_root=None,
            domain_code="d06_architecture",
            phase=5,
            slot_count=4,
            shortlist_path=self.shortlist,
        )
        self.assertTrue(roster["leader_selection"]["applied"])
        self.assertEqual(roster["leader_selection"]["leader_llm_code"], "claude-fable-5")
        # Highest slot (llm4) gets quality #1 among participants
        self.assertEqual(
            roster["slots"]["llm4"]["model_slug"], "claude-fable-5-thinking-high"
        )
        self.assertEqual(roster["slots"]["llm4"]["source"], "quality_among_participants")
        self.assertEqual(roster["slots"]["llm4"]["score"], 0.95)
        # Second-best quality among participants → llm3
        self.assertEqual(
            roster["slots"]["llm3"]["model_slug"], "cursor-grok-4.5-high-fast"
        )
        self.assertAlmostEqual(roster["slots"]["llm3"]["score"], 0.70)

    def test_quality_filter_keeps_best_per_family(self) -> None:
        rows = [
            ["gpt-5-6-luna-low", 0.4],
            ["gpt-5-6-luna-medium", 0.6],
            ["claude-fable-5", 0.9],
        ]
        filtered = orch.filter_quality_rows_to_families(
            rows, {"gpt-5.6-luna", "claude-fable"}
        )
        self.assertEqual(filtered[0], ["claude-fable-5", 0.9])
        self.assertEqual(filtered[1], ["gpt-5-6-luna-medium", 0.6])

    def test_override_same_provider_rejected(self) -> None:
        review = self.root / "review"
        review.mkdir()
        (review / "peer_review.models.yaml").write_text(
            "llm1: gpt-5.6-luna-low\nllm2: gpt-5.6-sol-none\n",
            encoding="utf-8",
        )
        roster = orch.build_dispatch_roster(
            llms_root=self.process,
            review_root=review,
            domain_code="d06",
            phase=2,
            slot_count=2,
            shortlist_path=self.shortlist,
        )
        self.assertTrue(roster["slots"]["llm1"]["resolved"])
        self.assertEqual(roster["slots"]["llm1"]["provider"], "OpenAI")
        self.assertFalse(roster["slots"]["llm2"]["resolved"])
        self.assertEqual(
            roster["slots"]["llm2"]["reason"], "duplicate_provider:OpenAI"
        )
        self.assertEqual(len(roster["provider_collisions"]), 1)

    def test_default_path_from_llms_root(self) -> None:
        path = orch.default_shortlist_path(self.process)
        self.assertEqual(path.resolve(), self.shortlist.resolve())

    def test_luna_low_maps_to_luna_low_task_slug(self) -> None:
        """Ranking winner luna-low maps 1:1 to Task slug gpt-5.6-luna-low."""
        self.assertEqual(
            orch.map_llm_code_to_task("gpt-5-6-luna-low"),
            "gpt-5.6-luna-low",
        )
        self.assertEqual(
            orch.map_llm_code_to_task("gpt-5-6-luna-medium"),
            "gpt-5.6-luna-low",
        )
        self.assertEqual(
            orch.map_llm_code_to_task("gpt-5-6-sol-non-reasoning"),
            "gpt-5.6-sol-none",
        )
        roster = orch.build_dispatch_roster(
            llms_root=self.process,
            review_root=None,
            domain_code="d06",
            phase=2,
            slot_count=1,
            shortlist_path=self.shortlist,
        )
        llm1 = roster["slots"]["llm1"]
        self.assertEqual(llm1["llm_code"], "gpt-5-6-luna-low")
        self.assertEqual(llm1["model_slug"], "gpt-5.6-luna-low")
        self.assertEqual(llm1["folder_alias"], "gpt56_luna")
        self.assertEqual(llm1["suggested_folder_suffix"], "llm1_gpt56_luna")

    def test_alias_mismatch_detection(self) -> None:
        participants = [
            orch.Participant(
                slot="llm1", alias="composer", folder_suffix="llm1_composer"
            )
        ]
        roster_slots = {
            "llm1": {
                "family": "gpt-5.6-luna",
                "model_slug": "gpt-5.6-luna-low",
                "llm_code": "gpt-5-6-luna-low",
            }
        }
        mismatches = orch.detect_participant_model_mismatches(
            participants, roster_slots
        )
        self.assertEqual(len(mismatches), 1)
        self.assertEqual(mismatches[0]["expected_folder_suffix"], "llm1_gpt56_luna")
        self.assertTrue(
            orch.alias_matches_family("gpt56_luna", "gpt-5.6-luna")
        )
        self.assertFalse(orch.alias_matches_family("composer", "gpt-5.6-luna"))

    def test_choose_roster_size_ignores_cliff_inside_min(self) -> None:
        # Sharp drop llm2→llm3 must not shrink below min_slots=4
        result = orch.choose_roster_size(
            [100.0, 90.0, 20.0, 18.0, 17.0],
            min_slots=4,
            max_slots=8,
            tau_vs_leader=0.15,
            rho_vs_prev=0.40,
        )
        self.assertEqual(result["chosen_k"], 5)
        self.assertEqual(result["stop_reason"], "no_more_scored")

    def test_choose_roster_size_cliff_after_min(self) -> None:
        # Flat through seat 6, cliff into seat 7 → keep 6
        result = orch.choose_roster_size(
            [100.0, 95.0, 90.0, 85.0, 80.0, 75.0, 25.0],
            min_slots=4,
            max_slots=8,
            tau_vs_leader=0.15,
            rho_vs_prev=0.40,
        )
        self.assertEqual(result["chosen_k"], 6)
        self.assertEqual(result["stop_reason"], "rho_vs_prev")
        self.assertEqual(result["stop_at_index"], 7)

    def test_choose_roster_size_tau_after_min(self) -> None:
        result = orch.choose_roster_size(
            [100.0, 90.0, 85.0, 80.0, 10.0],
            min_slots=4,
            max_slots=8,
            tau_vs_leader=0.15,
            rho_vs_prev=0.40,
        )
        self.assertEqual(result["chosen_k"], 4)
        self.assertEqual(result["stop_reason"], "tau_vs_leader")

    def test_choose_roster_size_few_scores_uses_min(self) -> None:
        result = orch.choose_roster_size(
            [200.0],
            min_slots=4,
            max_slots=8,
            tau_vs_leader=0.15,
            rho_vs_prev=0.40,
        )
        self.assertEqual(result["chosen_k"], 4)
        self.assertEqual(result["stop_reason"], "at_min_floor")

    def test_auto_roster_sizing_applied_on_resolve(self) -> None:
        # Extend fixture with a 5th unique provider + cliff 6th
        payload = json.loads(self.shortlist.read_text(encoding="utf-8"))
        payload["applications"]["d06_architecture_phase2"] = [
            ["gpt-5-6-luna-low", 100.0],
            ["claude-sonnet-5", 90.0],
            ["grok-4-5", 85.0],
            ["composer-2-5", 80.0],
            ["gpt-5-5", 75.0],  # same OpenAI as Luna → skipped by provider rule
            ["claude-fable-5", 70.0],  # same Anthropic → skipped
        ]
        # Only 4 unique providers → auto size stays at min_slots=4
        self.shortlist.write_text(json.dumps(payload), encoding="utf-8")
        roster = orch.build_dispatch_roster(
            llms_root=self.process,
            review_root=None,
            domain_code="d06",
            phase=2,
            slot_count=None,
            shortlist_path=self.shortlist,
        )
        self.assertTrue(roster["roster_sizing"]["applied"])
        self.assertEqual(roster["slot_count"], 4)
        self.assertEqual(roster["roster_sizing"]["chosen_k"], 4)
        self.assertEqual(len(roster["slots"]), 4)


if __name__ == "__main__":
    unittest.main()
