#!/usr/bin/env python3
"""Tests for product-wide delta_orchestrator."""

from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPTS))

import delta_orchestrator as delta  # noqa: E402


class DeltaProgramTest(unittest.TestCase):
    def _peer_with_domains(self, root: Path) -> Path:
        for name in ("d01_scope", "d03_information_conceptual", "d04a_information_logical"):
            (root / name).mkdir()
            # minimal accepted round
            rid = "20260101T000000Z"
            rdir = root / name / rid
            rdir.mkdir()
            (rdir / "round.md").write_text(f"kind: initial\nround_id: {rid}\n", encoding="utf-8")
            (rdir / "phase0_setup.md").write_text(f"# {name}\n", encoding="utf-8")
            (root / name / "current.json").write_text(
                json.dumps({"round_id": rid, "status": "accepted"}),
                encoding="utf-8",
            )
        return root

    def test_program_folder_timestamp_prefix(self) -> None:
        name = delta.program_dir_name("20260401T120000Z", "Taxonomy Fees!")
        self.assertTrue(name.startswith("20260401T120000Z_"))
        self.assertIn("taxonomy", name)

    def test_scaffold_and_status_impact_dispatch(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            peer = self._peer_with_domains(Path(tmp))
            result = delta.scaffold_program(
                peer,
                cause="taxonomy_and_tax",
                timestamp="20260401T120000Z",
                change_summary="multi taxonomy",
            )
            prog = Path(result["program_dir"])
            self.assertEqual(prog.name, "20260401T120000Z_taxonomy_and_tax")
            self.assertTrue((prog / "change_pack.md").is_file())
            self.assertTrue((prog / "impact_by_domain" / "d01_scope.md").is_file())
            action = delta.next_action(peer, prog)
            self.assertEqual(action["next_action"], "dispatch_impact_subagents")

    def test_rollup_promotes_downstream(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            peer = self._peer_with_domains(Path(tmp))
            result = delta.scaffold_program(
                peer, cause="tax", timestamp="20260402T000000Z"
            )
            prog = Path(result["program_dir"])
            # Mark impact done without PENDING marker; d01 touch, others no-touch
            (prog / "impact_by_domain" / "d01_scope.md").write_text(
                "verdict: touch\nseverity: high\nwhy: scope\n",
                encoding="utf-8",
            )
            (prog / "impact_by_domain" / "d03_information_conceptual.md").write_text(
                "verdict: no-touch\nseverity: none\n",
                encoding="utf-8",
            )
            (prog / "impact_by_domain" / "d04a_information_logical.md").write_text(
                "verdict: no-touch\nseverity: none\n",
                encoding="utf-8",
            )
            rollup = delta.rollup_impact(peer, prog)
            self.assertIn("d01_scope", rollup["touch_order"])
            self.assertIn("d03_information_conceptual", rollup["touch_order"])
            self.assertIn("d04a_information_logical", rollup["touch_order"])
            self.assertIn("d03_information_conceptual", rollup["promoted"])

    def test_coherence_ok_skips_promotion(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            peer = self._peer_with_domains(Path(tmp))
            result = delta.scaffold_program(
                peer, cause="tax", timestamp="20260403T000000Z"
            )
            prog = Path(result["program_dir"])
            (prog / "impact_by_domain" / "d01_scope.md").write_text(
                "verdict: touch\nseverity: medium\n",
                encoding="utf-8",
            )
            (prog / "impact_by_domain" / "d03_information_conceptual.md").write_text(
                "verdict: no-touch\nseverity: none\ncoherence_ok: true\n",
                encoding="utf-8",
            )
            (prog / "impact_by_domain" / "d04a_information_logical.md").write_text(
                "verdict: no-touch\nseverity: none\ncoherence_ok: true\n",
                encoding="utf-8",
            )
            rollup = delta.rollup_impact(peer, prog)
            self.assertEqual(rollup["touch_order"], ["d01_scope"])
            self.assertEqual(rollup["promoted"], [])

    def test_approve_and_next_run_domain(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            peer = self._peer_with_domains(Path(tmp))
            result = delta.scaffold_program(
                peer, cause="tax", timestamp="20260404T000000Z"
            )
            prog = Path(result["program_dir"])
            for d in ("d01_scope", "d03_information_conceptual", "d04a_information_logical"):
                (prog / "impact_by_domain" / f"{d}.md").write_text(
                    "verdict: touch\nseverity: high\nnotes: x\n",
                    encoding="utf-8",
                )
            delta.rollup_impact(peer, prog)
            delta.mark_impact_approved(prog)
            action = delta.next_action(peer, prog)
            self.assertEqual(action["next_action"], "run_domain_revision")
            self.assertEqual(action["domain"], "d01_scope")
            # One reassessment timestamp is the round id of every touch domain.
            self.assertEqual(action["round_id"], "20260404T000000Z")

    def test_accept_domain_updates_current(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            peer = self._peer_with_domains(Path(tmp))
            result = delta.scaffold_program(
                peer, cause="tax", timestamp="20260405T000000Z"
            )
            prog = Path(result["program_dir"])
            (prog / "impact_by_domain" / "d01_scope.md").write_text(
                "verdict: touch\nseverity: low\n",
                encoding="utf-8",
            )
            for d in ("d03_information_conceptual", "d04a_information_logical"):
                (prog / "impact_by_domain" / f"{d}.md").write_text(
                    "verdict: no-touch\nseverity: none\ncoherence_ok: true\n",
                    encoding="utf-8",
                )
            delta.rollup_impact(peer, prog)
            delta.mark_impact_approved(prog)
            # simulate new revision round
            orch = delta._import_orchestrator()
            init = orch.init_round(
                peer / "d01_scope",
                kind="revision",
                peer_review_root=peer,
                round_id="20260405T120000Z",
                change_pack=prog / "change_pack.md",
            )
            delta.set_domain_status(
                prog,
                "d01_scope",
                "awaiting_human",
                round_id=init["round_id"],
            )
            accepted = delta.accept_domain(peer, prog, "d01_scope")
            self.assertEqual(accepted["round_id"], "20260405T120000Z")
            current = json.loads(
                (peer / "d01_scope" / "current.json").read_text(encoding="utf-8")
            )
            self.assertEqual(current["status"], "accepted")
            self.assertEqual(current["round_id"], "20260405T120000Z")

    def test_meaning_slug_matches_contract_examples(self) -> None:
        self.assertEqual(delta.meaning_slug("Taxonomy flexibility"), "taxonomy_flexibility")
        self.assertEqual(delta.meaning_slug("Offer price & currency"), "offer_price_currency")
        self.assertEqual(delta.meaning_slug("taxonomy_flexibility"), "taxonomy_flexibility")
        self.assertEqual(
            delta.program_change_filename("PC-20261015-001", "Taxonomy flexibility"),
            "PC-20261015-001_taxonomy_flexibility.md",
        )
        for bad in ("", "  ", "ab", "x" * 49):
            with self.assertRaises(ValueError):
                delta.meaning_slug(bad)

    def test_record_change_suffixes_filename_and_skips_legacy_ids(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            peer = Path(tmp)
            first = delta.record_program_change(
                peer,
                meaning="Taxonomy flexibility",
                title="Taxonomy flexibility",
                summary="Allow more than one taxonomy on an offer.",
                date="20261015",
            )
            self.assertEqual(first["id"], "PC-20261015-001")
            self.assertEqual(first["filename"], "PC-20261015-001_taxonomy_flexibility.md")
            text = Path(first["path"]).read_text(encoding="utf-8")
            self.assertIn('id: "PC-20261015-001"', text)
            self.assertIn('meaning: "taxonomy_flexibility"', text)
            self.assertIn("Allow more than one taxonomy on an offer.", text)
            legacy = peer / "program_changes" / "changes" / "PC-20261015-002.md"
            legacy.write_text("---\nid: PC-20261015-002\n---\n", encoding="utf-8")
            second = delta.record_program_change(
                peer,
                meaning="geo tax",
                title="Geo tax",
                summary="Tax rules vary by geography.",
                date="20261015",
            )
            self.assertEqual(second["id"], "PC-20261015-003")
            self.assertEqual(second["filename"], "PC-20261015-003_geo_tax.md")

    def test_record_change_rejects_duplicate_id(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            peer = Path(tmp)
            changes = peer / "program_changes" / "changes"
            changes.mkdir(parents=True)
            (changes / "PC-20261015-001.md").write_text("legacy\n", encoding="utf-8")
            (changes / "PC-20261015-001_tax.md").write_text("dup\n", encoding="utf-8")
            with self.assertRaises(ValueError):
                delta.record_program_change(
                    peer,
                    meaning="other change",
                    title="Other",
                    summary="Something else entirely.",
                    date="20261015",
                )

    def test_record_change_rejects_bad_pc_name(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            peer = Path(tmp)
            changes = peer / "program_changes" / "changes"
            changes.mkdir(parents=True)
            (changes / "PC-notes.md").write_text("nope\n", encoding="utf-8")
            with self.assertRaises(ValueError):
                delta.next_change_id(changes, "20261015")

    def test_cli_record_change(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            peer = Path(tmp)
            code = delta.main(
                [
                    "--peer-review-root",
                    str(peer),
                    "record-change",
                    "--meaning",
                    "stakeholder scope",
                    "--title",
                    "Stakeholder scope",
                    "--summary",
                    "Narrow the in-scope actors.",
                    "--date",
                    "20261019",
                ]
            )
            self.assertEqual(code, 0)
            written = peer / "program_changes" / "changes" / "PC-20261019-001_stakeholder_scope.md"
            self.assertTrue(written.is_file())
            self.assertIn('meaning: "stakeholder_scope"', written.read_text(encoding="utf-8"))

    def test_cli_scaffold(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            peer = self._peer_with_domains(Path(tmp))
            code = delta.main(
                [
                    "--peer-review-root",
                    str(peer),
                    "--cause",
                    "demo",
                    "scaffold",
                    "--timestamp",
                    "20260501T010101Z",
                ]
            )
            self.assertEqual(code, 0)
            self.assertTrue(
                (peer / "program_changes" / "20260501T010101Z_demo" / "change_pack.md").is_file()
            )


if __name__ == "__main__":
    unittest.main()
