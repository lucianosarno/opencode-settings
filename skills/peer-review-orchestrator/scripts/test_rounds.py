#!/usr/bin/env python3
"""Tests for timestamped round helpers (init-round, upstream pins, resolve)."""

from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPTS))

import orchestrator as orch  # noqa: E402
from orchestrator import Participant  # noqa: E402


class RoundHelpersTest(unittest.TestCase):
    def test_phase4_and5_require_internal_artifacts_when_multi_participant(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            review = Path(tmp)
            participants = [
                Participant(slot="llm1", alias="a", folder_suffix="llm1_a"),
                Participant(slot="llm2", alias="b", folder_suffix="llm2_b"),
            ]
            for p in participants:
                p4 = review / "phase4_final_proposals" / p.folder_suffix
                p4.mkdir(parents=True)
                (p4 / "overview.md").write_text("# proposal\n", encoding="utf-8")
            self.assertFalse(orch._phase4_complete(review, participants))
            (review / "phase4_final_proposals" / "llm1_a" / "_internal").mkdir()
            (
                review
                / "phase4_final_proposals"
                / "llm1_a"
                / "_internal"
                / "post_critique_revision_log.md"
            ).write_text("# log\n", encoding="utf-8")
            self.assertFalse(orch._phase4_complete(review, participants))
            (review / "phase4_final_proposals" / "llm2_b" / "_internal").mkdir()
            (
                review
                / "phase4_final_proposals"
                / "llm2_b"
                / "_internal"
                / "post_critique_revision_log.md"
            ).write_text("# log\n", encoding="utf-8")
            self.assertTrue(orch._phase4_complete(review, participants))

            p5 = review / "phase5_unified_answer_leader"
            p5.mkdir()
            (p5 / "overview.md").write_text("# unified\n", encoding="utf-8")
            self.assertFalse(orch._phase5_complete(review, participants))
            (p5 / "_internal").mkdir()
            (p5 / "_internal" / "consolidation_matrix.md").write_text(
                "# matrix\n", encoding="utf-8"
            )
            self.assertTrue(orch._phase5_complete(review, participants))

    def test_single_participant_skips_internal_artifacts(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            review = Path(tmp)
            one = [Participant(slot="llm1", alias="a", folder_suffix="llm1_a")]
            p4 = review / "phase4_final_proposals" / "llm1_a"
            p4.mkdir(parents=True)
            (p4 / "overview.md").write_text("# proposal\n", encoding="utf-8")
            self.assertTrue(orch._phase4_complete(review, one))
            p5 = review / "phase5_unified_answer_leader"
            p5.mkdir()
            (p5 / "overview.md").write_text("# unified\n", encoding="utf-8")
            self.assertTrue(orch._phase5_complete(review, one))

    def test_init_initial_round_and_current(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            d01 = root / "d01_scope"
            d01.mkdir()
            result = orch.init_round(
                d01,
                kind="initial",
                peer_review_root=root,
                round_id="20260101T000000Z",
                summary="First scope round",
            )
            self.assertEqual(result["round_id"], "20260101T000000Z")
            review = Path(result["review_root"])
            self.assertTrue((review / "round.md").is_file())
            current = json.loads((d01 / "current.json").read_text(encoding="utf-8"))
            self.assertEqual(current["round_id"], "20260101T000000Z")
            self.assertEqual(current["status"], "in_progress")
            self.assertEqual(orch.infer_domain_code(review), "d01_scope")

    def test_upstream_pins_and_revision_copies_phase0(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            d01 = root / "d01_scope"
            d03 = root / "d03_information_conceptual"
            d01.mkdir()
            d03.mkdir()
            orch.init_round(
                d01,
                kind="initial",
                peer_review_root=root,
                round_id="20260101T000000Z",
            )
            orch.write_current_json(d01, "20260101T000000Z", "accepted")
            (d01 / "20260101T000000Z" / "phase5_unified_answer_leader").mkdir()
            (
                d01 / "20260101T000000Z" / "phase5_unified_answer_leader" / "overview.md"
            ).write_text("# d01\n", encoding="utf-8")

            baseline = orch.init_round(
                d03,
                kind="initial",
                peer_review_root=root,
                round_id="20260102T000000Z",
            )
            (Path(baseline["review_root"]) / "phase0_setup.md").write_text(
                "# setup d03\n", encoding="utf-8"
            )
            orch.write_current_json(d03, "20260102T000000Z", "accepted")

            rev = orch.init_round(
                d03,
                kind="revision",
                peer_review_root=root,
                baseline_round_id="20260102T000000Z",
                round_id="20260103T120000Z",
                summary="Align with taxonomy change",
            )
            self.assertEqual(rev["baseline_round_id"], "20260102T000000Z")
            self.assertEqual(rev["upstream_pins"].get("d01_scope"), "20260101T000000Z")
            self.assertTrue(
                (Path(rev["review_root"]) / "phase0_setup.md").is_file()
            )
            self.assertIn(
                "setup d03",
                (Path(rev["review_root"]) / "phase0_setup.md").read_text(encoding="utf-8"),
            )
            paths = rev["upstream_artifact_paths"]
            self.assertTrue(any("d01_scope" in p for p in paths))

    def test_resolve_review_root_via_current(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            d01 = root / "d01_scope"
            d01.mkdir()
            orch.init_round(
                d01,
                kind="initial",
                peer_review_root=root,
                round_id="20260202T010101Z",
            )
            resolved = orch.resolve_review_root(domain_root=d01)
            self.assertEqual(resolved.name, "20260202T010101Z")

    def test_catalog_upstream_order(self) -> None:
        ups = orch.upstream_domain_codes("d04a_information_logical")
        self.assertIn("d01_scope", ups)
        self.assertIn("d03_information_conceptual", ups)
        self.assertNotIn("d04a_information_logical", ups)
        self.assertNotIn("d04b_contracts_draft", ups)

    def test_shared_review_round_id_across_domains(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            d01 = root / "d01_scope"
            d03 = root / "d03_information_conceptual"
            d01.mkdir()
            d03.mkdir()
            shared = "20260301T100000Z"
            orch.init_round(d01, kind="initial", peer_review_root=root, round_id=shared)
            # Same review, another domain: same id is allowed while d01 is still open.
            second = orch.init_round(
                d03, kind="initial", peer_review_root=root, round_id=shared
            )
            self.assertEqual(second["round_id"], shared)
            self.assertTrue((d03 / shared / "round.md").is_file())

    def test_init_round_refuses_different_id_while_review_open(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            d01 = root / "d01_scope"
            d03 = root / "d03_information_conceptual"
            d01.mkdir()
            d03.mkdir()
            orch.init_round(
                d01, kind="initial", peer_review_root=root, round_id="20260301T100000Z"
            )
            with self.assertRaises(ValueError) as ctx:
                orch.init_round(
                    d03,
                    kind="initial",
                    peer_review_root=root,
                    round_id="20260302T100000Z",
                )
            self.assertIn("d01_scope=20260301T100000Z", str(ctx.exception))
            self.assertFalse((d03 / "20260302T100000Z").exists())

    def test_init_round_allows_different_id_after_review_accepted(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            d01 = root / "d01_scope"
            d03 = root / "d03_information_conceptual"
            d01.mkdir()
            d03.mkdir()
            orch.init_round(
                d01, kind="initial", peer_review_root=root, round_id="20260301T100000Z"
            )
            orch.write_current_json(d01, "20260301T100000Z", "accepted")
            result = orch.init_round(
                d03, kind="initial", peer_review_root=root, round_id="20260302T100000Z"
            )
            self.assertEqual(result["round_id"], "20260302T100000Z")

    def test_cli_init_round(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            d01 = root / "d01_scope"
            d01.mkdir()
            code = orch.main(
                [
                    "init-round",
                    "--domain-root",
                    str(d01),
                    "--peer-review-root",
                    str(root),
                    "--kind",
                    "initial",
                    "--round-id",
                    "20260303T030303Z",
                ]
            )
            self.assertEqual(code, 0)
            self.assertTrue((d01 / "20260303T030303Z" / "round.md").is_file())


if __name__ == "__main__":
    unittest.main()
