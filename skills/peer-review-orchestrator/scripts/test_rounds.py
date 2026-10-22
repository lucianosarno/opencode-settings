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
                (p4 / "artifact_manifest.json").write_text("{}\n", encoding="utf-8")
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
            (p5 / "artifact_manifest.json").write_text("{}\n", encoding="utf-8")
            (p5 / "_internal").mkdir()
            (p5 / "_internal" / "consolidation_matrix.md").write_text(
                "# matrix\n", encoding="utf-8"
            )
            self.assertFalse(orch._phase5_complete(review, participants))
            self._write_audit(p5, status="pass")
            self.assertTrue(orch._phase5_complete(review, participants))

    def test_single_participant_skips_internal_artifacts(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            review = Path(tmp)
            one = [Participant(slot="llm1", alias="a", folder_suffix="llm1_a")]
            p4 = review / "phase4_final_proposals" / "llm1_a"
            p4.mkdir(parents=True)
            (p4 / "overview.md").write_text("# proposal\n", encoding="utf-8")
            (p4 / "artifact_manifest.json").write_text("{}\n", encoding="utf-8")
            self.assertTrue(orch._phase4_complete(review, one))
            p5 = review / "phase5_unified_answer_leader"
            p5.mkdir()
            (p5 / "overview.md").write_text("# unified\n", encoding="utf-8")
            (p5 / "artifact_manifest.json").write_text("{}\n", encoding="utf-8")
            self._write_audit(p5, status="pass")
            self.assertTrue(orch._phase5_complete(review, one))

    @staticmethod
    def _write_audit(folder: Path, *, status: str, findings: str = "[]") -> None:
        (folder / "_internal").mkdir(exist_ok=True)
        (folder / "_internal" / "boundary_audit.json").write_text(
            '{"schema_version": 1, "status": "%s", "auditor_role": "boundary_adversary", '
            '"independent_of_leader": true, "checked_artifacts": ["OVERVIEW"], "findings": %s}'
            % (status, findings),
            encoding="utf-8",
        )

    def test_phase5_audit_blocks_on_block_finding(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            folder = Path(tmp) / "phase5_unified_answer_leader"
            folder.mkdir()
            self._write_audit(
                folder,
                status="fail",
                findings='[{"id": "F1", "severity": "block", "axis": "x", "owner": "d03", '
                '"artifacts": [], "evidence": "e", "required_action": "r"}]',
            )
            ok, reason = orch.boundary_audit_status(folder)
            self.assertFalse(ok)
            self.assertIn("fail", reason)
            self._write_audit(folder, status="pass")
            self.assertTrue(orch.boundary_audit_status(folder)[0])

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


PHASE0 = """# Peer review setup

## Roles
- User role: product owner

## Domains
- Manifest: program_manifest.md

## Brownfield
- Mode: no

## Deliverable profile
- Profile(s): Scope definition

## Participants
| Slot | Model alias | Folder suffix |
| --- | --- | --- |
| llm1 | a | `llm1_a` |
| llm2 | b | `llm2_b` |

## Decision-boundary conditions
- Active conditions: none
"""

MANIFEST = """# Program manifest

- **Frozen:** yes
- **Order:** [d01_scope, d03_information_conceptual]
"""


class Phase1CycleTest(unittest.TestCase):
    """Phase 1 = one propose/critique/revise/consolidate cycle + stakeholder gate."""

    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.peer = Path(self._tmp.name)
        (self.peer / "program_manifest.md").write_text(MANIFEST, encoding="utf-8")
        self.d01 = self.peer / "d01_scope"
        self.d03 = self.peer / "d03_information_conceptual"
        self.d01.mkdir()
        self.d03.mkdir()
        self.participants = [
            Participant(slot="llm1", alias="a", folder_suffix="llm1_a"),
            Participant(slot="llm2", alias="b", folder_suffix="llm2_b"),
        ]

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def _round(self, domain: Path, rid: str) -> Path:
        orch.init_round(domain, kind="initial", peer_review_root=self.peer, round_id=rid)
        orch.write_current_json(domain, rid, "in_progress")
        review = domain / rid
        (review / "phase0_setup.md").write_text(PHASE0, encoding="utf-8")
        return review

    def _write(self, path: Path, text: str) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")

    def _cycle_files(self, review: Path, pairs: list[str]) -> None:
        p1 = review / "phase1_questions"
        for p in self.participants:
            self._write(p1 / "proposals" / p.folder_suffix / "d01_scope_option.md", "# draft\n")
            self._write(p1 / "revisions" / p.folder_suffix / "d01_scope_option.md", "# revised\n")
        self._write(p1 / "critiques" / "llm1_vs_llm2.md", "# c\n")
        self._write(p1 / "critiques" / "llm2_vs_llm1.md", "# c\n")
        self._write(p1 / "decisions" / "_index.md", "# index\n")
        rows = "\n".join(f"| {pair} | 1 | — |" for pair in pairs)
        self._write(p1 / "coverage.md", "| pair | count | why |\n| --- | --- | --- |\n" + rows + "\n")

    @staticmethod
    def _decision(origin: str, enters: str, target: str, answer: str = "") -> str:
        return (
            "# Decision\n\n"
            "- **Priority:** 24 (lower = read sooner)\n"
            "- **Technical percentage:** 40\n"
            "- **Certainty:** 60\n"
            f"- **Origin:** {origin}\n"
            f"- **Pair:** d03_vs_{target}\n"
            f"- **Target domain:** {target}\n"
            f"- **Enters this deliverable:** {enters}\n"
            "- **Also affects:** none\n"
            "- **Status:** awaiting stakeholder\n\n"
            "## Decision\nPick a scope.\n\n"
            f"## Stakeholder decision\n{answer}\n\n"
            "## Analyst reading\n\n"
        )

    def test_cycle_complete_with_llm_closed_decision(self) -> None:
        review = self._round(self.d03, "20260601T000000Z")
        self._cycle_files(review, ["d03_vs_d03"])
        self._write(
            review / "phase1_questions" / "decisions" / "d03_vs_d03" / "pr024tp040cl060_scope_terms.md",
            self._decision("llm-closed", "yes", "d03"),
        )
        cycle = orch.phase1_cycle_status(review, self.participants, ["d01", "d03"], "d03")
        self.assertTrue(cycle["complete"], cycle)
        gate = orch.stakeholder_gate(review, self.peer, "d03", {})
        self.assertEqual(gate["own_blockers"], [])

    def test_missing_critique_and_bad_decision_name_block_cycle(self) -> None:
        review = self._round(self.d03, "20260601T010000Z")
        self._cycle_files(review, ["d03_vs_d03"])
        (review / "phase1_questions" / "critiques" / "llm2_vs_llm1.md").unlink()
        self._write(
            review / "phase1_questions" / "decisions" / "d03_vs_d03" / "scope.md",
            self._decision("llm-closed", "yes", "d03"),
        )
        cycle = orch.phase1_cycle_status(review, self.participants, ["d01", "d03"], "d03")
        self.assertFalse(cycle["complete"])
        self.assertEqual(cycle["critiques_missing"], ["llm2_vs_llm1.md"])
        self.assertTrue(cycle["bad_decision_names"])

    def test_coverage_must_list_every_pair_from_this_domain_forward(self) -> None:
        review = self._round(self.d01, "20260601T020000Z")
        self._cycle_files(review, ["d01_vs_d01"])  # missing d01_vs_d03
        cycle = orch.phase1_cycle_status(review, self.participants, ["d01", "d03"], "d01")
        self.assertEqual(cycle["coverage_missing_pairs"], ["d01_vs_d03"])
        self.assertFalse(cycle["complete"])

    def test_own_stakeholder_appetite_blocks_phase_1_until_answered(self) -> None:
        review = self._round(self.d03, "20260601T030000Z")
        self._cycle_files(review, ["d03_vs_d03"])
        decision = review / "phase1_questions" / "decisions" / "d03_vs_d03" / "pr024tp040cl060_scope.md"
        self._write(decision, self._decision("stakeholder-appetite", "yes", "d03"))
        gate = orch.stakeholder_gate(review, self.peer, "d03", {})
        self.assertEqual(gate["own_blockers"], [str(decision)])
        status = orch.infer_status(review, self.peer, resolve_models=False)
        self.assertEqual(status["current_phase"], 1)
        self.assertIn("PAUSE", status["next_action"])
        self._write(decision, self._decision("stakeholder-appetite", "yes", "d03", "Keep it narrow."))
        status = orch.infer_status(review, self.peer, resolve_models=False)
        self.assertNotIn("PAUSE", status["next_action"])
        self.assertTrue(status["phases"]["1"]["complete"])

    def test_inbound_parked_decision_blocks_phase_2_of_target(self) -> None:
        d01_round = self._round(self.d01, "20260601T040000Z")
        self._cycle_files(d01_round, ["d01_vs_d01", "d01_vs_d03"])
        self._write(
            d01_round / "phase1_questions" / "decisions" / "d01_vs_d03" / "pr010tp020cl050_audience.md",
            self._decision("stakeholder-appetite", "no", "d03").replace(
                "d03_vs_d03", "d01_vs_d03"
            ),
        )
        orch.write_current_json(self.d01, "20260601T040000Z", "accepted")
        review = self._round(self.d03, "20260601T050000Z")
        self._cycle_files(review, ["d03_vs_d03"])
        status = orch.infer_status(review, self.peer, resolve_models=False)
        self.assertTrue(status["phases"]["1"]["complete"], status["next_action"])
        self.assertEqual(status["current_phase"], 2)
        self.assertIn("PAUSE", status["next_action"])
        self.assertEqual(len(status["phases"]["1"]["stakeholder_gate"]["inbound_blockers"]), 1)

    def test_phase0_requires_frozen_manifest(self) -> None:
        (self.peer / "program_manifest.md").unlink()
        review = self._round(self.d03, "20260601T060000Z")
        status = orch.infer_status(review, self.peer, resolve_models=False)
        self.assertEqual(status["current_phase"], 0)
        self.assertIn("program_manifest.md", status["next_action"])

    def test_phase0_lists_missing_sections(self) -> None:
        review = self._round(self.d03, "20260601T070000Z")
        (review / "phase0_setup.md").write_text("# Peer review setup\n\n## Roles\n", encoding="utf-8")
        status = orch.infer_status(review, self.peer, resolve_models=False)
        self.assertEqual(status["current_phase"], 0)
        self.assertIn("Decision-boundary conditions", status["next_action"])


class ReassessmentRoundTest(unittest.TestCase):
    """Revision rounds of a delta reassessment obey the frozen plan."""

    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.peer = Path(self._tmp.name)
        self.d01 = self.peer / "d01_scope"
        self.d03 = self.peer / "d03_information_conceptual"
        for d in (self.d01, self.d03):
            d.mkdir()
        self.prog = self.peer / "program_changes" / "20260701T000000Z_tax"
        (self.prog / "impact_by_domain").mkdir(parents=True)
        (self.prog / "reassessment.md").write_text(
            "---\n"
            'reassessment_id: "20260701T000000Z_tax"\n'
            "run_status: approved\n"
            "change_refs:\n  - PC-20261015-001\n  - PC-20261015-002\n"
            "touch_order:\n  - d01_scope\n  - d03_information_conceptual\n"
            "---\n",
            encoding="utf-8",
        )
        self._impact("d01_scope", "PC-20261015-001 | touch", "PC-20261015-002 | touch")
        self._impact("d03_information_conceptual", "PC-20261015-001 | no-touch", "PC-20261015-002 | touch")

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def _impact(self, domain: str, *rows: str) -> None:
        lines = ["| change_id | effect | reason |", "| --- | --- | --- |"]
        for row in rows:
            cid, eff = (c.strip() for c in row.split("|"))
            lines.append(f"| {cid} | {eff} | because |")
        (self.prog / "impact_by_domain" / f"{domain}.md").write_text(
            "\n".join(lines) + "\n", encoding="utf-8"
        )

    def test_revision_round_requires_touch_rows_and_shared_id(self) -> None:
        ref = self.prog / "reassessment.md"
        with self.assertRaises(ValueError):
            orch.init_round(
                self.d01, kind="revision", peer_review_root=self.peer,
                round_id="20260702T000000Z", reassessment_ref=ref,
                change_ids=["PC-20261015-001"],
            )
        with self.assertRaises(ValueError):  # d03 does not touch PC-…-001
            orch.init_round(
                self.d03, kind="revision", peer_review_root=self.peer,
                round_id="20260701T000000Z", reassessment_ref=ref,
                change_ids=["PC-20261015-001"],
            )
        result = orch.init_round(
            self.d03, kind="revision", peer_review_root=self.peer,
            round_id="20260701T000000Z", reassessment_ref=ref,
            change_ids=["PC-20261015-002"],
        )
        self.assertEqual(result["change_ids"], ["PC-20261015-002"])
        round_md = orch.read_front_matter(Path(result["review_root"]) / "round.md")
        self.assertEqual(round_md["change_ids"], ["PC-20261015-002"])
        self.assertIsNone(round_md.get("change_pack_ref"))
        self.assertEqual(round_md["reassessment_ref"], str(ref.resolve()))

    def test_draft_run_is_refused(self) -> None:
        ref = self.prog / "reassessment.md"
        ref.write_text(ref.read_text(encoding="utf-8").replace("approved", "awaiting_plan_approval"), encoding="utf-8")
        with self.assertRaises(ValueError):
            orch.init_round(
                self.d01, kind="revision", peer_review_root=self.peer,
                round_id="20260701T000000Z", reassessment_ref=ref,
                change_ids=["PC-20261015-001"],
            )

    def test_round_id_must_match_reassessment_timestamp(self) -> None:
        with self.assertRaises(ValueError):
            orch.init_round(
                self.d01, kind="revision", peer_review_root=self.peer,
                round_id="20260709T000000Z", reassessment_ref=self.prog / "reassessment.md",
                change_ids=["PC-20261015-001"],
            )

    def test_read_front_matter_parses_lists_and_block_text(self) -> None:
        path = self.prog / "reassessment.md"
        fm = orch.read_front_matter(path)
        self.assertEqual(fm["change_refs"], ["PC-20261015-001", "PC-20261015-002"])
        self.assertEqual(fm["run_status"], "approved")
        self.assertEqual(orch.impact_effects(self.prog / "impact_by_domain" / "d03_information_conceptual.md"),
                         {"PC-20261015-001": "no-touch", "PC-20261015-002": "touch"})


if __name__ == "__main__":
    unittest.main()
