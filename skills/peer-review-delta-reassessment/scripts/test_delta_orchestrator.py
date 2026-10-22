#!/usr/bin/env python3
"""Tests for product-wide delta_orchestrator (process/standards/revision_rounds.md)."""

from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPTS))

import delta_orchestrator as delta  # noqa: E402

DOMAINS = ("d01_scope", "d03_information_conceptual", "d04a_information_logical")
ROUND = "20260101T000000Z"
PC1 = "PC-20261015-001"
PC2 = "PC-20261015-002"


class DeltaTestBase(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.peer = Path(self._tmp.name)
        for name in DOMAINS:
            domain = self.peer / name
            rdir = domain / ROUND
            rdir.mkdir(parents=True)
            (rdir / "round.md").write_text(f"kind: initial\nround_id: {ROUND}\n", encoding="utf-8")
            (rdir / "phase0_setup.md").write_text(f"# {name}\n", encoding="utf-8")
            (domain / "current.json").write_text(
                json.dumps({"round_id": ROUND, "status": "accepted"}), encoding="utf-8"
            )

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def record(self, meaning: str, disposition: str = "accepted", date: str = "20261015") -> str:
        result = delta.record_program_change(
            self.peer,
            meaning=meaning,
            title=meaning.title(),
            summary=f"Change {meaning}.",
            date=date,
            disposition=disposition,
        )
        return result["id"]

    def scaffold(self, change_ids: list[str], cause: str = "tax", ts: str = "20260701T000000Z") -> Path:
        result = delta.scaffold_program(self.peer, cause=cause, change_ids=change_ids, timestamp=ts)
        return Path(result["program_dir"])

    def write_impact(self, prog: Path, domain: str, effects: dict[str, str]) -> None:
        rows = ["| change_id | effect | reason |", "| --- | --- | --- |"]
        rows += [f"| {cid} | {eff} | because |" for cid, eff in effects.items()]
        (prog / "impact_by_domain" / f"{domain}.md").write_text("\n".join(rows) + "\n", encoding="utf-8")

    def fill_impact(self, prog: Path, table: dict[str, dict[str, str]]) -> None:
        for domain in DOMAINS:
            self.write_impact(prog, domain, table[domain])

    def status(self, prog: Path) -> str:
        return str(delta._import_orchestrator().read_front_matter(prog / "reassessment.md").get("run_status"))


class RecordAndScaffoldTest(DeltaTestBase):
    def test_program_folder_timestamp_prefix(self) -> None:
        name = delta.program_dir_name("20260401T120000Z", "Taxonomy Fees!")
        self.assertTrue(name.startswith("20260401T120000Z_"))

    def test_meaning_slug_matches_contract_examples(self) -> None:
        self.assertEqual(delta.meaning_slug("Taxonomy flexibility"), "taxonomy_flexibility")
        self.assertEqual(delta.meaning_slug("Offer price & currency"), "offer_price_currency")
        self.assertEqual(
            delta.program_change_filename("PC-20261015-001", "Taxonomy flexibility"),
            "PC-20261015-001_taxonomy_flexibility.md",
        )
        for bad in ("", "  ", "ab", "x" * 49):
            with self.assertRaises(ValueError):
                delta.meaning_slug(bad)

    def test_record_change_suffixes_filename_and_skips_legacy_ids(self) -> None:
        first = delta.record_program_change(
            self.peer, meaning="Taxonomy flexibility", title="T", summary="One.", date="20261015"
        )
        self.assertEqual(first["filename"], "PC-20261015-001_taxonomy_flexibility.md")
        legacy = self.peer / "program_changes" / "changes" / "PC-20261015-002.md"
        legacy.write_text("---\nid: PC-20261015-002\n---\n", encoding="utf-8")
        second = delta.record_program_change(
            self.peer, meaning="geo tax", title="G", summary="Two.", date="20261015"
        )
        self.assertEqual(second["id"], "PC-20261015-003")

    def test_record_change_rejects_duplicate_and_bad_names(self) -> None:
        changes = self.peer / "program_changes" / "changes"
        changes.mkdir(parents=True)
        (changes / "PC-20261015-001.md").write_text("legacy\n", encoding="utf-8")
        (changes / "PC-20261015-001_tax.md").write_text("dup\n", encoding="utf-8")
        with self.assertRaises(ValueError):
            delta.next_change_id(changes, "20261015")

    def test_scaffold_requires_accepted_changes(self) -> None:
        proposed = self.record("stakeholder scope", disposition="proposed")
        with self.assertRaises(ValueError):
            delta.scaffold_program(self.peer, cause="x", change_ids=[proposed])
        with self.assertRaises(ValueError):
            delta.scaffold_program(self.peer, cause="x", change_ids=[])
        with self.assertRaises(ValueError):
            delta.scaffold_program(self.peer, cause="x", change_ids=["PC-20261015-099"])

    def test_scaffold_writes_draft_run_and_change_index(self) -> None:
        pc = self.record("taxonomy flexibility")
        prog = self.scaffold([pc])
        fm = delta._import_orchestrator().read_front_matter(prog / "reassessment.md")
        self.assertEqual(fm["run_status"], "draft")
        self.assertEqual(fm["change_refs"], [pc])
        self.assertEqual(delta._import_orchestrator().as_list(fm["touch_order"]), [])
        pack = (prog / "change_pack.md").read_text(encoding="utf-8")
        self.assertIn(f"| {pc} |", pack)
        self.assertIn("PC-20261015-001_taxonomy_flexibility.md", pack)
        stub = (prog / "impact_by_domain" / "d01_scope.md").read_text(encoding="utf-8")
        self.assertIn(f"| {pc} | TODO_IMPACT", stub)

    def test_scaffold_refuses_existing_run(self) -> None:
        pc = self.record("taxonomy flexibility")
        self.scaffold([pc])
        with self.assertRaises(FileExistsError):
            self.scaffold([pc])

    def test_cli_scaffold_needs_change_id_and_cause(self) -> None:
        pc = self.record("taxonomy flexibility")
        with self.assertRaises(SystemExit):
            delta.main(["--peer-review-root", str(self.peer), "--cause", "demo", "scaffold"])
        code = delta.main(
            [
                "--peer-review-root", str(self.peer), "--cause", "demo", "scaffold",
                "--change-id", pc, "--timestamp", "20260501T010101Z",
            ]
        )
        self.assertEqual(code, 0)
        self.assertTrue((self.peer / "program_changes" / "20260501T010101Z_demo" / "reassessment.md").is_file())


class ImpactAndPlanTest(DeltaTestBase):
    def test_rollup_refuses_incomplete_impact(self) -> None:
        pc = self.record("taxonomy flexibility")
        prog = self.scaffold([pc])
        with self.assertRaises(ValueError):
            delta.rollup_impact(self.peer, prog)

    def test_rollup_promotes_downstream_for_every_change_row(self) -> None:
        pc1 = self.record("taxonomy flexibility")
        pc2 = self.record("geo tax")
        prog = self.scaffold([pc1, pc2])
        self.fill_impact(prog, {
            "d01_scope": {pc1: "touch", pc2: "no-touch"},
            "d03_information_conceptual": {pc1: "no-touch", pc2: "no-touch"},
            "d04a_information_logical": {pc1: "no-touch", pc2: "no-touch"},
        })
        rollup = delta.rollup_impact(self.peer, prog)
        self.assertEqual(rollup["promoted"], ["d03_information_conceptual", "d04a_information_logical"])
        self.assertEqual(rollup["touch_order"], list(DOMAINS))
        self.assertEqual(self.status(prog), "awaiting_plan_approval")
        d03 = delta.parse_impact_file(prog / "impact_by_domain" / "d03_information_conceptual.md")
        self.assertEqual(d03["effects"], {pc1: "touch", pc2: "touch"})
        self.assertIn("promoted_for_upstream_coherence: true", (prog / "impact_by_domain" / "d03_information_conceptual.md").read_text(encoding="utf-8"))

    def test_coherence_ok_skips_promotion(self) -> None:
        pc = self.record("taxonomy flexibility")
        prog = self.scaffold([pc])
        self.fill_impact(prog, {
            "d01_scope": {pc: "touch"},
            "d03_information_conceptual": {pc: "no-touch"},
            "d04a_information_logical": {pc: "no-touch"},
        })
        for name in ("d03_information_conceptual", "d04a_information_logical"):
            path = prog / "impact_by_domain" / f"{name}.md"
            path.write_text(path.read_text(encoding="utf-8") + "\ncoherence_ok: true\n", encoding="utf-8")
        rollup = delta.rollup_impact(self.peer, prog)
        self.assertEqual(rollup["touch_order"], ["d01_scope"])
        self.assertEqual(rollup["promoted"], [])

    def test_approve_freezes_touch_order_and_blocks_rollup(self) -> None:
        pc = self.record("taxonomy flexibility")
        prog = self.scaffold([pc])
        self.fill_impact(prog, {d: {pc: "touch"} for d in DOMAINS})
        result = delta.approve_impact(self.peer, prog)
        self.assertEqual(result["run_status"], "approved")
        self.assertEqual(result["touch_order"], list(DOMAINS))
        fm = delta._import_orchestrator().read_front_matter(prog / "reassessment.md")
        self.assertEqual(fm["touch_order"], list(DOMAINS))
        log = (prog / "execution_log.md").read_text(encoding="utf-8")
        for name in DOMAINS:
            self.assertIn(f"| {name} | pending |", log)
        with self.assertRaises(ValueError):
            delta.rollup_impact(self.peer, prog)
        with self.assertRaises(ValueError):
            delta.approve_impact(self.peer, prog)

    def test_next_action_order_and_change_ids_per_domain(self) -> None:
        pc1 = self.record("taxonomy flexibility")
        pc2 = self.record("geo tax")
        prog = self.scaffold([pc1, pc2])
        self.assertEqual(delta.next_action(self.peer, prog)["next_action"], "dispatch_impact_subagents")
        self.fill_impact(prog, {
            "d01_scope": {pc1: "touch", pc2: "no-touch"},
            "d03_information_conceptual": {pc1: "no-touch", pc2: "touch"},
            "d04a_information_logical": {pc1: "no-touch", pc2: "no-touch"},
        })
        self.assertEqual(delta.next_action(self.peer, prog)["next_action"], "rollup_impact")
        delta.rollup_impact(self.peer, prog)
        self.assertEqual(delta.next_action(self.peer, prog)["next_action"], "await_human_impact_approval")
        delta.approve_impact(self.peer, prog)
        action = delta.next_action(self.peer, prog)
        self.assertEqual(action["next_action"], "run_domain_revision")
        self.assertEqual(action["domain"], "d01_scope")
        self.assertEqual(action["round_id"], "20260701T000000Z")
        self.assertEqual(action["change_ids"], [pc1])
        delta.set_domain_status(prog, "d01_scope", "in_progress", round_id="20260701T000000Z")
        self.assertEqual(delta.next_action(self.peer, prog)["next_action"], "resume_domain_round")


class ExecutionTest(DeltaTestBase):
    def _approved(self, ts: str = "20260701T000000Z") -> tuple[Path, str]:
        pc = self.record("taxonomy flexibility")
        prog = self.scaffold([pc], ts=ts)
        self.fill_impact(prog, {d: {pc: "touch"} for d in DOMAINS})
        delta.approve_impact(self.peer, prog)
        return prog, pc

    def test_execution_requires_approval_and_touch_domain(self) -> None:
        pc = self.record("taxonomy flexibility")
        prog = self.scaffold([pc])
        with self.assertRaises(ValueError):
            delta.set_domain_status(prog, "d01_scope", "in_progress")
        self.fill_impact(prog, {
            "d01_scope": {pc: "touch"},
            "d03_information_conceptual": {pc: "no-touch"},
            "d04a_information_logical": {pc: "no-touch"},
        })
        for name in ("d03_information_conceptual", "d04a_information_logical"):
            path = prog / "impact_by_domain" / f"{name}.md"
            path.write_text(path.read_text(encoding="utf-8") + "\ncoherence_ok: true\n", encoding="utf-8")
        delta.approve_impact(self.peer, prog)
        self.assertEqual(delta._import_orchestrator().as_list(
            delta._import_orchestrator().read_front_matter(prog / "reassessment.md")["touch_order"]
        ), ["d01_scope"])
        with self.assertRaises(ValueError):
            delta.set_domain_status(prog, "d03_information_conceptual", "in_progress")
        with self.assertRaises(ValueError):
            delta.set_domain_status(prog, "d01_scope", "skipped")

    def test_accept_requires_awaiting_human_then_run_completes(self) -> None:
        prog, _ = self._approved()
        with self.assertRaises(ValueError):
            delta.accept_domain(self.peer, prog, "d01_scope")
        for name in DOMAINS:
            delta.set_domain_status(prog, name, "in_progress", round_id="20260701T000000Z")
            delta.set_domain_status(prog, name, "awaiting_human", round_id="20260701T000000Z")
            if name == DOMAINS[0]:
                self.assertEqual(self.status(prog), "executing")
            accepted = delta.accept_domain(self.peer, prog, name, round_id="20260701T000000Z")
            current = json.loads((self.peer / name / "current.json").read_text(encoding="utf-8"))
            self.assertEqual(current, {"round_id": "20260701T000000Z", "status": "accepted"})
            self.assertEqual(accepted["execution"]["status"], "accepted")
        self.assertEqual(self.status(prog), "complete")
        self.assertEqual(delta.next_action(self.peer, prog)["next_action"], "done")

    def test_abandon_only_before_execution(self) -> None:
        pc = self.record("taxonomy flexibility")
        prog = self.scaffold([pc], ts="20260601T000000Z")
        self.assertEqual(delta.main(["--peer-review-root", str(self.peer), "--program-dir", str(prog), "abandon", "--reason", "dropped"]), 0)
        self.assertEqual(self.status(prog), "abandoned")
        prog2, _ = self._approved()
        delta.set_domain_status(prog2, DOMAINS[0], "in_progress", round_id="20260701T000000Z")
        self.assertEqual(delta.main(["--peer-review-root", str(self.peer), "--program-dir", str(prog2), "abandon", "--reason", "late"]), 1)


class ApplicationStatusTest(DeltaTestBase):
    def _state(self, cid: str) -> dict:
        rows = {r["change_id"]: r for r in delta.application_status(self.peer)}
        return rows[cid]

    def test_states_follow_governing_run_and_execution(self) -> None:
        proposed = self.record("maybe later", disposition="proposed")
        uncovered = self.record("geo tax")
        self.assertEqual(self._state(proposed)["application"], "n/a")
        self.assertEqual(self._state(uncovered)["application"], "uncovered")

        pc = self.record("taxonomy flexibility")
        prog = self.scaffold([pc])
        # A draft run is not governing, but it is an open recheck, so the change is being assessed.
        self.assertEqual(self._state(pc)["application"], "assessing")
        self.assertEqual(self._state(pc)["open_recheck"], prog.name)
        self.fill_impact(prog, {
            "d01_scope": {pc: "touch"},
            "d03_information_conceptual": {pc: "no-touch"},
            "d04a_information_logical": {pc: "no-touch"},
        })
        delta.approve_impact(self.peer, prog)
        self.assertEqual(self._state(pc)["application"], "planned")
        # d03/d04a have no coherence_ok, so they were promoted to touch by the rollup.
        self.assertEqual(self._state(pc)["required_domains"], list(DOMAINS))

        delta.set_domain_status(prog, "d01_scope", "in_progress", round_id="20260701T000000Z")
        self.assertEqual(self._state(pc)["application"], "in_progress")
        for name in DOMAINS:
            delta.set_domain_status(prog, name, "in_progress", round_id="20260701T000000Z")
            delta.set_domain_status(prog, name, "awaiting_human", round_id="20260701T000000Z")
            delta.accept_domain(self.peer, prog, name, round_id="20260701T000000Z")
            if name == DOMAINS[0]:
                self.assertEqual(self._state(pc)["application"], "partially_applied")
        self.assertEqual(self._state(pc)["application"], "applied")

    def test_partially_applied_when_some_required_domains_accepted(self) -> None:
        pc = self.record("taxonomy flexibility")
        prog = self.scaffold([pc])
        self.fill_impact(prog, {d: {pc: "touch"} for d in DOMAINS})
        delta.approve_impact(self.peer, prog)
        delta.set_domain_status(prog, "d01_scope", "in_progress", round_id="20260701T000000Z")
        delta.set_domain_status(prog, "d01_scope", "awaiting_human", round_id="20260701T000000Z")
        delta.accept_domain(self.peer, prog, "d01_scope", round_id="20260701T000000Z")
        self.assertEqual(self._state(pc)["application"], "partially_applied")

    def test_open_recheck_does_not_downgrade_governing_run(self) -> None:
        pc = self.record("taxonomy flexibility")
        first = self.scaffold([pc], ts="20260701T000000Z")
        self.fill_impact(first, {d: {pc: "touch"} for d in DOMAINS})
        delta.approve_impact(self.peer, first)
        second = self.scaffold([pc], ts="20260702T000000Z")
        row = self._state(pc)
        self.assertEqual(row["governing_run"], first.name)
        self.assertEqual(row["open_recheck"], second.name)
        self.assertEqual(row["application"], "planned")


class RevisionRoundIntegrationTest(DeltaTestBase):
    def test_init_round_accepts_only_touch_changes_of_approved_run(self) -> None:
        orch = delta._import_orchestrator()
        pc1 = self.record("taxonomy flexibility")
        pc2 = self.record("geo tax")
        prog = self.scaffold([pc1, pc2])
        self.fill_impact(prog, {
            "d01_scope": {pc1: "touch", pc2: "no-touch"},
            "d03_information_conceptual": {pc1: "no-touch", pc2: "touch"},
            "d04a_information_logical": {pc1: "no-touch", pc2: "no-touch"},
        })
        delta.approve_impact(self.peer, prog)
        ref = prog / "reassessment.md"
        domain_root = self.peer / "d03_information_conceptual"
        with self.assertRaises(ValueError):
            orch.init_round(domain_root, kind="revision", peer_review_root=self.peer,
                            round_id="20260701T000000Z", reassessment_ref=ref, change_ids=[pc1])
        result = orch.init_round(domain_root, kind="revision", peer_review_root=self.peer,
                                 round_id="20260701T000000Z", reassessment_ref=ref, change_ids=[pc2])
        self.assertEqual(result["change_ids"], [pc2])
        self.assertEqual(result["upstream_pins"]["d01_scope"], ROUND)
        round_md = orch.read_front_matter(Path(result["review_root"]) / "round.md")
        self.assertEqual(round_md["change_ids"], [pc2])


if __name__ == "__main__":
    unittest.main()
