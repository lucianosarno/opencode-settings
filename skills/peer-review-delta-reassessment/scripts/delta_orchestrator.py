#!/usr/bin/env python3
"""Product-wide peer-review delta reassessment — program_changes, impact, execution.

Layout:
  {PEER_REVIEW_ROOT}/program_changes/changes/PC-YYYYMMDD-NNN_{meaning}.md
  {PEER_REVIEW_ROOT}/program_changes/{YYYYMMDDTHHMMSSZ}_{cause}/
    change_pack.md
    impact_assessment.md
    impact_by_domain/{domain}.md
    execution_log.md

The change id is `PC-YYYYMMDD-NNN`. `{meaning}` is a short slug (same idea as `{cause}`
on the run folder) so the filename shows what the change is about. Slug rules:
llms_peer_review `process/standards/revision_rounds.md`.

Examples:
  python delta_orchestrator.py --peer-review-root path/to/peer_review record-change --meaning "taxonomy flexibility" --title "Taxonomy flexibility" --summary "Allow more than one taxonomy."
  python delta_orchestrator.py --peer-review-root path/to/peer_review scaffold --cause taxonomy
  python delta_orchestrator.py --peer-review-root … --program-dir … status
  python delta_orchestrator.py --peer-review-root … --program-dir … list-domains
  python delta_orchestrator.py --peer-review-root … --program-dir … rollup-impact
  python delta_orchestrator.py --peer-review-root … --program-dir … next-action
  python delta_orchestrator.py --peer-review-root … --program-dir … accept-domain --domain d01_scope
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

SKILL_DIR = Path(__file__).resolve().parent.parent
CONFIG_DIR = SKILL_DIR / "config"
TEMPLATES_DIR = SKILL_DIR / "templates"

PROGRAM_CHANGES_DIRNAME = "program_changes"
TOUCH_RE = re.compile(r"(?im)^\s*(?:-\s*)?(?:\*\*)?verdict(?:\*\*)?\s*[:=]\s*(touch|no-touch)\b")
SEVERITY_RE = re.compile(
    r"(?im)^\s*(?:-\s*)?(?:\*\*)?severity(?:\*\*)?\s*[:=]\s*(critical|high|medium|low|none)\b"
)


def _load_json(path: Path) -> Any:
    with path.open(encoding="utf-8") as f:
        return json.load(f)


def load_settings() -> dict[str, Any]:
    path = CONFIG_DIR / "settings.json"
    return _load_json(path) if path.is_file() else {}


def orch_root() -> Path:
    settings = load_settings()
    configured = settings.get("orchestrator_skill_root")
    if configured:
        return Path(configured)
    return Path.home() / ".config" / "opencode" / "skills" / "peer-review-orchestrator"


def _import_orchestrator():
    scripts = orch_root() / "scripts"
    if str(scripts) not in sys.path:
        sys.path.insert(0, str(scripts))
    import orchestrator as orch  # type: ignore

    return orch


def utc_now_ts() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def program_dir_name(timestamp: str, cause: str) -> str:
    slug = re.sub(r"[^a-z0-9_]+", "_", cause.strip().lower()).strip("_") or "change"
    return f"{timestamp}_{slug}"


# Filename suffix for one stakeholder change. Contract: revision_rounds.md
# ("Meaning slug"). The id stays PC-YYYYMMDD-NNN; the slug is not part of the id.
MEANING_RE = re.compile(r"^[a-z0-9]+(?:_[a-z0-9]+)*$")
PC_ID_RE = re.compile(r"^PC-(\d{8})-(\d{3})$")
PC_FILE_RE = re.compile(
    r"^PC-(?P<date>\d{8})-(?P<seq>\d{3})"
    r"(?:_(?P<meaning>[a-z0-9]+(?:_[a-z0-9]+)*))?\.md$"
)
DISPOSITIONS = ("proposed", "accepted", "rejected", "superseded")


def meaning_slug(text: str) -> str:
    """Normalize a short change label to the filename suffix.

    Trim, lowercase, turn each run of characters outside ``a-z0-9_`` into one
    underscore, collapse repeated underscores, strip edges. Reject empty,
    shorter than 3, or longer than 48. Do not invent a default and do not cut.
    """
    slug = re.sub(r"[^a-z0-9_]+", "_", text.strip().lower())
    slug = re.sub(r"_+", "_", slug).strip("_")
    if not MEANING_RE.fullmatch(slug):
        raise ValueError(
            "meaning slug is empty after normalization; pass a short label of the change"
        )
    if len(slug) < 3 or len(slug) > 48:
        raise ValueError(
            f"meaning slug must be 3–48 characters after normalization (got {len(slug)}: {slug!r})"
        )
    return slug


def program_change_filename(change_id: str, meaning: str) -> str:
    if not PC_ID_RE.fullmatch(change_id):
        raise ValueError(f"change id must be PC-YYYYMMDD-NNN (got {change_id!r})")
    return f"{change_id}_{meaning_slug(meaning)}.md"


def changes_dir(peer_review_root: Path) -> Path:
    return peer_review_root / PROGRAM_CHANGES_DIRNAME / "changes"


def scan_change_files(changes: Path) -> dict[str, dict[str, Any]]:
    """Map ``PC-YYYYMMDD-NNN`` → file info. Reject a bad ``PC-*`` name or two files for one id."""
    found: dict[str, dict[str, Any]] = {}
    if not changes.is_dir():
        return found
    for path in sorted(p for p in changes.iterdir() if p.is_file()):
        if not path.name.startswith("PC-"):
            continue
        match = PC_FILE_RE.fullmatch(path.name)
        if not match:
            raise ValueError(f"unrecognized program change filename: {path.name}")
        change_id = f"PC-{match.group('date')}-{match.group('seq')}"
        if change_id in found:
            other = found[change_id]["path"].name
            raise ValueError(
                f"duplicate program change id {change_id}: {other} and {path.name}"
            )
        found[change_id] = {
            "path": path,
            "meaning": match.group("meaning"),
            "date": match.group("date"),
            "seq": int(match.group("seq")),
        }
    return found


def next_change_id(changes: Path, date: str) -> str:
    if not re.fullmatch(r"\d{8}", date):
        raise ValueError("date must be YYYYMMDD")
    found = scan_change_files(changes)
    seq = max((row["seq"] for row in found.values() if row["date"] == date), default=0)
    if seq >= 999:
        raise ValueError(f"no free program change sequence on {date}")
    return f"PC-{date}-{seq + 1:03d}"


def _yaml_double_quote(value: str) -> str:
    return '"' + value.replace("\\", "\\\\").replace('"', '\\"') + '"'


def record_program_change(
    peer_review_root: Path,
    *,
    meaning: str,
    title: str,
    summary: str,
    body: str | None = None,
    date: str | None = None,
    disposition: str = "proposed",
    when: datetime | None = None,
) -> dict[str, Any]:
    """Write ``changes/PC-YYYYMMDD-NNN_{meaning}.md`` and return its id and path."""
    if disposition not in DISPOSITIONS:
        raise ValueError(f"disposition must be one of {', '.join(DISPOSITIONS)}")
    title = title.strip()
    summary = summary.strip()
    if not title:
        raise ValueError("title is required")
    if not summary:
        raise ValueError("summary is required")
    slug = meaning_slug(meaning)
    now = when or datetime.now(timezone.utc)
    if date is None:
        date = now.strftime("%Y%m%d")
        requested_at = now.strftime("%Y-%m-%dT%H:%M:%SZ")
    else:
        if not re.fullmatch(r"\d{8}", date):
            raise ValueError("date must be YYYYMMDD")
        requested_at = f"{date[0:4]}-{date[4:6]}-{date[6:8]}T00:00:00Z"
    dest_dir = changes_dir(peer_review_root)
    dest_dir.mkdir(parents=True, exist_ok=True)
    change_id = next_change_id(dest_dir, date)
    filename = program_change_filename(change_id, slug)
    path = dest_dir / filename
    statement = (summary if body is None else body).strip() + "\n"
    text = "\n".join(
        [
            "---",
            f"id: {_yaml_double_quote(change_id)}",
            f"meaning: {_yaml_double_quote(slug)}",
            f"title: {_yaml_double_quote(title)}",
            f"requested_at: {_yaml_double_quote(requested_at)}",
            f"disposition: {_yaml_double_quote(disposition)}",
            f"summary: {_yaml_double_quote(summary)}",
            "---",
            "",
            statement,
        ]
    )
    path.write_text(text, encoding="utf-8")
    return {
        "id": change_id,
        "meaning": slug,
        "filename": filename,
        "path": str(path.resolve()),
        "disposition": disposition,
    }


def resolve_program_dir(
    peer_review_root: Path,
    *,
    program_dir: Path | None = None,
    cause: str | None = None,
) -> Path | None:
    if program_dir is not None:
        return program_dir
    base = peer_review_root / PROGRAM_CHANGES_DIRNAME
    if not base.is_dir():
        return None
    dirs = sorted(
        [p for p in base.iterdir() if p.is_dir()],
        key=lambda p: p.name,
        reverse=True,
    )
    if cause:
        slug = re.sub(r"[^a-z0-9_]+", "_", cause.strip().lower()).strip("_")
        for d in dirs:
            if d.name.endswith(f"_{slug}") or f"_{slug}" in d.name:
                return d
    return dirs[0] if dirs else None


def list_consumer_domains(peer_review_root: Path) -> list[str]:
    orch = _import_orchestrator()
    return orch.list_peer_review_domains(peer_review_root)


def scaffold_program(
    peer_review_root: Path,
    *,
    cause: str,
    timestamp: str | None = None,
    change_summary: str | None = None,
) -> dict[str, Any]:
    ts = timestamp or utc_now_ts()
    name = program_dir_name(ts, cause)
    prog = peer_review_root / PROGRAM_CHANGES_DIRNAME / name
    prog.mkdir(parents=True, exist_ok=True)
    (prog / "impact_by_domain").mkdir(exist_ok=True)

    pack = prog / "change_pack.md"
    if not pack.is_file():
        tmpl = TEMPLATES_DIR / "change_pack.md"
        body = tmpl.read_text(encoding="utf-8") if tmpl.is_file() else "# Change pack\n"
        if change_summary:
            body = body.replace("{{SUMMARY}}", change_summary)
        else:
            body = body.replace("{{SUMMARY}}", "(fill in)")
        body = body.replace("{{CAUSE}}", cause)
        body = body.replace("{{TIMESTAMP}}", ts)
        pack.write_text(body, encoding="utf-8")

    for fname, tmpl_name in (
        ("impact_assessment.md", "impact_assessment.md"),
        ("execution_log.md", "execution_log.md"),
    ):
        dest = prog / fname
        if not dest.is_file():
            tmpl = TEMPLATES_DIR / tmpl_name
            text = tmpl.read_text(encoding="utf-8") if tmpl.is_file() else f"# {fname}\n"
            text = text.replace("{{CAUSE}}", cause).replace("{{TIMESTAMP}}", ts)
            dest.write_text(text, encoding="utf-8")

    domains = list_consumer_domains(peer_review_root)
    impact_tmpl = TEMPLATES_DIR / "impact_by_domain" / "_template.md"
    impact_body = (
        impact_tmpl.read_text(encoding="utf-8")
        if impact_tmpl.is_file()
        else "# Impact — {{DOMAIN}}\n\nverdict: no-touch\nseverity: none\n"
    )
    for domain in domains:
        dest = prog / "impact_by_domain" / f"{domain}.md"
        if not dest.is_file():
            dest.write_text(
                impact_body.replace("{{DOMAIN}}", domain)
                .replace("{{CAUSE}}", cause)
                .replace("{{TIMESTAMP}}", ts),
                encoding="utf-8",
            )

    return {
        "program_dir": str(prog.resolve()),
        "timestamp": ts,
        "cause": cause,
        "domains": domains,
        "change_pack": str(pack.resolve()),
    }


def parse_impact_file(path: Path) -> dict[str, Any]:
    text = path.read_text(encoding="utf-8") if path.is_file() else ""
    verdict_m = TOUCH_RE.search(text)
    sev_m = SEVERITY_RE.search(text)
    verdict = (verdict_m.group(1).lower() if verdict_m else "no-touch").replace(
        "no-touch", "no-touch"
    )
    if verdict not in ("touch", "no-touch"):
        verdict = "no-touch"
    return {
        "path": str(path),
        "verdict": verdict,
        "severity": (sev_m.group(1).lower() if sev_m else "none"),
        "filled": bool(text.strip()) and "verdict:" in text.lower(),
    }


def read_execution_statuses(program_dir: Path) -> dict[str, str]:
    """Parse execution_log.md table rows: | domain | status | …"""
    path = program_dir / "execution_log.md"
    text = path.read_text(encoding="utf-8") if path.is_file() else ""
    statuses: dict[str, str] = {}
    for line in text.splitlines():
        m = re.match(
            r"^\|\s*(d\d+[a-z]?_[a-z0-9_]+)\s*\|\s*"
            r"(pending|in_progress|awaiting_human|accepted|skipped)\s*\|",
            line,
            re.I,
        )
        if m:
            statuses[m.group(1)] = m.group(2).lower()
    return statuses


def write_execution_log(
    program_dir: Path,
    rows: list[dict[str, str]],
    *,
    cause: str,
    timestamp: str,
    coherence_note: str | None = None,
    extra_body: str | None = None,
) -> None:
    lines = [
        f"# Execution log — `{timestamp}_{cause}`",
        "",
        "| domain | status | round_id | notes |",
        "| --- | --- | --- | --- |",
    ]
    for row in rows:
        lines.append(
            f"| {row['domain']} | {row['status']} | {row.get('round_id', '')} | {row.get('notes', '')} |"
        )
    lines.append("")
    if coherence_note:
        lines.extend(["## Coherence note", "", coherence_note, ""])
    if extra_body and extra_body.strip():
        lines.extend(["", extra_body.strip(), ""])
    (program_dir / "execution_log.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def ensure_execution_rows(
    program_dir: Path,
    domains_touch: list[str],
    *,
    cause: str,
    timestamp: str,
) -> list[dict[str, str]]:
    existing = read_execution_statuses(program_dir)
    # Preserve notes/round from prior file if present
    prior_rows: dict[str, dict[str, str]] = {}
    path = program_dir / "execution_log.md"
    if path.is_file():
        for line in path.read_text(encoding="utf-8").splitlines():
            m = re.match(
                r"^\|\s*(d\d+[a-z]?_[a-z0-9_]+)\s*\|\s*([\w-]+)\s*\|\s*([^|]*)\|\s*(.*)\|\s*$",
                line,
                re.I,
            )
            if m:
                prior_rows[m.group(1)] = {
                    "domain": m.group(1),
                    "status": m.group(2).lower(),
                    "round_id": m.group(3).strip(),
                    "notes": m.group(4).strip(),
                }
    rows: list[dict[str, str]] = []
    for d in domains_touch:
        if d in prior_rows:
            rows.append(prior_rows[d])
        else:
            rows.append(
                {
                    "domain": d,
                    "status": existing.get(d, "pending"),
                    "round_id": "",
                    "notes": "",
                }
            )
    write_execution_log(program_dir, rows, cause=cause, timestamp=timestamp)
    return rows


def rollup_impact(
    peer_review_root: Path,
    program_dir: Path,
) -> dict[str, Any]:
    orch = _import_orchestrator()
    domains = list_consumer_domains(peer_review_root)
    by_domain: dict[str, dict[str, Any]] = {}
    for d in domains:
        path = program_dir / "impact_by_domain" / f"{d}.md"
        by_domain[d] = parse_impact_file(path)

    # Promote no-touch → touch when an earlier catalog domain is touch
    promoted: list[str] = []
    ordered = sorted(domains, key=orch.catalog_index)
    touch_seen = False
    for d in ordered:
        info = by_domain[d]
        if info["verdict"] == "touch":
            touch_seen = True
        elif touch_seen and info["verdict"] == "no-touch":
            # Coherence force: if any upstream touch, later domains must be re-checked;
            # promote unless impact file explicitly says coherence_ok: true
            text = Path(info["path"]).read_text(encoding="utf-8") if Path(info["path"]).is_file() else ""
            if re.search(r"(?im)coherence_ok\s*:\s*true", text):
                continue
            info["verdict"] = "touch"
            info["promoted"] = True
            promoted.append(d)
            # rewrite file marker
            path = Path(info["path"])
            if path.is_file():
                body = path.read_text(encoding="utf-8")
                body = re.sub(
                    r"(?im)^(\s*(?:-\s*)?(?:\*\*)?verdict(?:\*\*)?\s*[:=]\s*)no-touch\b",
                    r"\1touch",
                    body,
                    count=1,
                )
                if "promoted_for_upstream_coherence: true" not in body:
                    body += "\n\npromoted_for_upstream_coherence: true\n"
                path.write_text(body, encoding="utf-8")

    touch_list = [d for d in ordered if by_domain[d]["verdict"] == "touch"]
    lines = [
        "# Impact assessment (rollup)",
        "",
        "Aggregated from `impact_by_domain/`. Order follows `process/standards/domains.md`.",
        "",
        "| domain | verdict | severity | promoted |",
        "| --- | --- | --- | --- |",
    ]
    for d in ordered:
        info = by_domain[d]
        lines.append(
            f"| {d} | {info['verdict']} | {info.get('severity', 'none')} | "
            f"{'yes' if info.get('promoted') else ''} |"
        )
    lines.extend(
        [
            "",
            "## Touch order (execution)",
            "",
        ]
    )
    for d in touch_list:
        lines.append(f"1. `{d}`")
    if not touch_list:
        lines.append("_None — no domains marked touch._")
    lines.append("")
    if promoted:
        lines.append("## Promotions")
        lines.append("")
        lines.append(
            "The following were promoted `no-touch` → `touch` because an upstream domain "
            "in this program is `touch` and `coherence_ok: true` was not set:"
        )
        for d in promoted:
            lines.append(f"- `{d}`")
        lines.append("")

    (program_dir / "impact_assessment.md").write_text("\n".join(lines), encoding="utf-8")

    # Seed execution log for touch domains
    name = program_dir.name
    ts, _, cause = name.partition("_")
    ensure_execution_rows(
        program_dir,
        touch_list,
        cause=cause or "change",
        timestamp=ts or utc_now_ts(),
    )

    return {
        "domains": ordered,
        "by_domain": by_domain,
        "touch_order": touch_list,
        "promoted": promoted,
        "impact_assessment": str((program_dir / "impact_assessment.md").resolve()),
    }


def impact_plan_approved(program_dir: Path) -> bool:
    path = program_dir / "impact_assessment.md"
    if not path.is_file():
        return False
    text = path.read_text(encoding="utf-8")
    return bool(
        re.search(r"(?im)^\s*impact_plan_approved\s*:\s*true\b", text)
        or re.search(r"(?im)status\s*:\s*approved\b", text)
    )


def mark_impact_approved(program_dir: Path) -> None:
    path = program_dir / "impact_assessment.md"
    text = path.read_text(encoding="utf-8") if path.is_file() else "# Impact assessment\n"
    if not re.search(r"(?im)^\s*impact_plan_approved\s*:", text):
        text = text.rstrip() + "\n\nimpact_plan_approved: true\n"
    else:
        text = re.sub(
            r"(?im)^\s*impact_plan_approved\s*:\s*\w+",
            "impact_plan_approved: true",
            text,
        )
    path.write_text(text, encoding="utf-8")


def next_action(peer_review_root: Path, program_dir: Path) -> dict[str, Any]:
    orch = _import_orchestrator()
    domains = list_consumer_domains(peer_review_root)
    impact_dir = program_dir / "impact_by_domain"
    missing_impact = [
        d
        for d in domains
        if not (impact_dir / f"{d}.md").is_file()
        or not parse_impact_file(impact_dir / f"{d}.md")["filled"]
    ]
    # Consider "filled" if file exists with verdict line — scaffold creates stubs with verdict
    stub_unreviewed = []
    for d in domains:
        p = impact_dir / f"{d}.md"
        if not p.is_file():
            stub_unreviewed.append(d)
            continue
        text = p.read_text(encoding="utf-8")
        if "PENDING_IMPACT_SUBAGENT" in text or "TODO_IMPACT" in text:
            stub_unreviewed.append(d)

    if stub_unreviewed:
        return {
            "next_action": "dispatch_impact_subagents",
            "domains": stub_unreviewed,
            "detail": "Run one impact subagent per domain; write impact_by_domain/{domain}.md",
        }

    rollup_path = program_dir / "impact_assessment.md"
    if not rollup_path.is_file() or "Touch order" not in rollup_path.read_text(encoding="utf-8"):
        return {
            "next_action": "rollup_impact",
            "detail": "Run rollup-impact after all impact_by_domain files are filled",
        }

    if not impact_plan_approved(program_dir):
        return {
            "next_action": "await_human_impact_approval",
            "detail": "Ask steward to approve; then approve-impact or set impact_plan_approved: true",
        }

    statuses = read_execution_statuses(program_dir)
    rollup = rollup_impact(peer_review_root, program_dir)
    touch_order = rollup["touch_order"]
    review_round_id = program_dir.name.partition("_")[0]

    for d in touch_order:
        st = statuses.get(d, "pending")
        if st in ("pending", "in_progress"):
            return {
                "next_action": "run_domain_revision",
                "domain": d,
                "status": st,
                "round_id": review_round_id,
                "detail": (
                    f"init-round revision for {d} with --round-id {review_round_id} "
                    "(same id for every touch domain; refresh upstream_pins), "
                    "then peer-review-orchestrator phases 0–5"
                ),
                "domain_root": str((peer_review_root / d).resolve()),
            }
        if st == "awaiting_human":
            return {
                "next_action": "await_human_domain_approval",
                "domain": d,
                "detail": f"Steward must accept round for {d}; then accept-domain",
            }

    return {
        "next_action": "done",
        "detail": "All touch domains accepted; write coherence note in execution_log if missing",
        "touch_order": touch_order,
    }


def set_domain_status(
    program_dir: Path,
    domain: str,
    status: str,
    *,
    round_id: str | None = None,
    notes: str = "",
) -> dict[str, Any]:
    name = program_dir.name
    ts, _, cause = name.partition("_")
    statuses = read_execution_statuses(program_dir)
    # rebuild rows
    path = program_dir / "execution_log.md"
    prior: dict[str, dict[str, str]] = {}
    trailing: list[str] = []
    seen_row = False
    if path.is_file():
        for line in path.read_text(encoding="utf-8").splitlines():
            m = re.match(
                r"^\|\s*(d\d+[a-z]?_[a-z0-9_]+)\s*\|\s*([\w-]+)\s*\|\s*([^|]*)\|\s*(.*)\|\s*$",
                line,
                re.I,
            )
            if m:
                seen_row = True
                prior[m.group(1)] = {
                    "domain": m.group(1),
                    "status": m.group(2).lower(),
                    "round_id": m.group(3).strip(),
                    "notes": m.group(4).strip(),
                }
                continue
            if seen_row and line.strip() and not line.strip().startswith("|"):
                trailing.append(line)
    if domain not in prior:
        prior[domain] = {
            "domain": domain,
            "status": status,
            "round_id": round_id or "",
            "notes": notes,
        }
    else:
        prior[domain]["status"] = status
        if round_id is not None:
            prior[domain]["round_id"] = round_id
        if notes:
            prior[domain]["notes"] = notes

    orch = _import_orchestrator()
    ordered = sorted(prior.keys(), key=orch.catalog_index)
    rows = [prior[d] for d in ordered]
    write_execution_log(
        program_dir,
        rows,
        cause=cause or "change",
        timestamp=ts or utc_now_ts(),
        extra_body="\n".join(trailing).strip() or None,
    )
    return prior[domain]


def accept_domain(
    peer_review_root: Path,
    program_dir: Path,
    domain: str,
    *,
    round_id: str | None = None,
) -> dict[str, Any]:
    orch = _import_orchestrator()
    domain_root = peer_review_root / domain
    rid = round_id
    if not rid:
        current = orch.read_current_json(domain_root) or {}
        rid = str(current.get("round_id") or "")
    if not rid:
        raise ValueError(f"No round_id for {domain}")
    orch.write_current_json(domain_root, rid, "accepted")
    row = set_domain_status(
        program_dir,
        domain,
        "accepted",
        round_id=rid,
        notes="human accepted",
    )
    return {"domain": domain, "round_id": rid, "execution": row}


def cmd_scaffold(args: argparse.Namespace) -> int:
    peer = Path(args.peer_review_root)
    result = scaffold_program(
        peer,
        cause=args.cause,
        timestamp=args.timestamp,
        change_summary=args.summary,
    )
    print(json.dumps(result, indent=2))
    return 0


def cmd_list_domains(args: argparse.Namespace) -> int:
    peer = Path(args.peer_review_root)
    print(json.dumps({"domains": list_consumer_domains(peer)}, indent=2))
    return 0


def cmd_rollup(args: argparse.Namespace) -> int:
    peer = Path(args.peer_review_root)
    prog = resolve_program_dir(peer, program_dir=Path(args.program_dir) if args.program_dir else None, cause=args.cause)
    if not prog:
        print(json.dumps({"error": "program_dir not found"}), file=sys.stderr)
        return 1
    print(json.dumps(rollup_impact(peer, prog), indent=2, default=str))
    return 0


def cmd_status(args: argparse.Namespace) -> int:
    peer = Path(args.peer_review_root)
    prog = resolve_program_dir(
        peer,
        program_dir=Path(args.program_dir) if args.program_dir else None,
        cause=args.cause,
    )
    if not prog:
        print(json.dumps({"error": "program_dir not found", "hint": "run scaffold"}, indent=2))
        return 1
    action = next_action(peer, prog)
    payload = {
        "peer_review_root": str(peer.resolve()),
        "program_dir": str(prog.resolve()),
        "execution": read_execution_statuses(prog),
        "impact_plan_approved": impact_plan_approved(prog),
        **action,
    }
    print(json.dumps(payload, indent=2, default=str))
    return 0


def cmd_record_change(args: argparse.Namespace) -> int:
    peer = Path(args.peer_review_root)
    try:
        result = record_program_change(
            peer,
            meaning=args.meaning,
            title=args.title,
            summary=args.summary,
            body=args.body,
            date=args.date,
            disposition=args.disposition,
        )
    except ValueError as exc:
        print(json.dumps({"error": str(exc)}), file=sys.stderr)
        return 1
    print(json.dumps(result, indent=2))
    return 0


def cmd_next_action(args: argparse.Namespace) -> int:
    return cmd_status(args)


def cmd_approve_impact(args: argparse.Namespace) -> int:
    peer = Path(args.peer_review_root)
    prog = resolve_program_dir(
        peer,
        program_dir=Path(args.program_dir) if args.program_dir else None,
        cause=args.cause,
    )
    if not prog:
        print(json.dumps({"error": "program_dir not found"}), file=sys.stderr)
        return 1
    rollup_impact(peer, prog)
    mark_impact_approved(prog)
    print(json.dumps({"program_dir": str(prog), "impact_plan_approved": True}, indent=2))
    return 0


def cmd_set_domain_status(args: argparse.Namespace) -> int:
    peer = Path(args.peer_review_root)
    prog = resolve_program_dir(
        peer,
        program_dir=Path(args.program_dir) if args.program_dir else None,
        cause=args.cause,
    )
    if not prog:
        print(json.dumps({"error": "program_dir not found"}), file=sys.stderr)
        return 1
    row = set_domain_status(
        prog,
        args.domain,
        args.status,
        round_id=args.round_id,
        notes=args.notes or "",
    )
    print(json.dumps(row, indent=2))
    return 0


def cmd_accept_domain(args: argparse.Namespace) -> int:
    peer = Path(args.peer_review_root)
    prog = resolve_program_dir(
        peer,
        program_dir=Path(args.program_dir) if args.program_dir else None,
        cause=args.cause,
    )
    if not prog:
        print(json.dumps({"error": "program_dir not found"}), file=sys.stderr)
        return 1
    try:
        result = accept_domain(peer, prog, args.domain, round_id=args.round_id)
    except ValueError as exc:
        print(json.dumps({"error": str(exc)}), file=sys.stderr)
        return 1
    print(json.dumps(result, indent=2))
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Product-wide delta reassessment — program_changes + impact + execution."
    )
    parser.add_argument(
        "--peer-review-root",
        required=True,
        help="Consumer peer_review root (contains d0X folders)",
    )
    parser.add_argument(
        "--program-dir",
        default=None,
        help="Path to program_changes/{ts}_{cause}/ (default: latest or match --cause)",
    )
    parser.add_argument(
        "--cause",
        default=None,
        help="Cause slug (required for scaffold; optional filter when resolving program dir)",
    )

    sub = parser.add_subparsers(dest="command", required=True)

    p_rc = sub.add_parser(
        "record-change",
        help="Write program_changes/changes/PC-YYYYMMDD-NNN_{meaning}.md",
    )
    p_rc.add_argument("--meaning", required=True, help="Short label; stored as the filename slug")
    p_rc.add_argument("--title", required=True)
    p_rc.add_argument("--summary", required=True)
    p_rc.add_argument("--body", default=None, help="Statement body (default: summary)")
    p_rc.add_argument("--date", default=None, help="UTC date YYYYMMDD (default: today)")
    p_rc.add_argument(
        "--disposition",
        default="proposed",
        choices=DISPOSITIONS,
    )

    p_sc = sub.add_parser("scaffold", help="Create program_changes/{ts}_{cause}/")
    p_sc.add_argument("--timestamp", default=None)
    p_sc.add_argument("--summary", default=None)
    p_sc.set_defaults(_require_cause=True)

    sub.add_parser("list-domains", help="List d0X folders under peer-review-root")
    sub.add_parser("status", help="Program status + next_action")
    sub.add_parser("next-action", help="Alias for status")
    sub.add_parser("rollup-impact", help="Aggregate impact_by_domain → impact_assessment")
    sub.add_parser("approve-impact", help="Mark impact plan approved after human gate")

    p_set = sub.add_parser("set-domain-status", help="Update execution_log row")
    p_set.add_argument("--domain", required=True)
    p_set.add_argument(
        "--status",
        required=True,
        choices=("pending", "in_progress", "awaiting_human", "accepted", "skipped"),
    )
    p_set.add_argument("--round-id", default=None)
    p_set.add_argument("--notes", default="")

    p_acc = sub.add_parser("accept-domain", help="Accept domain round + update current.json")
    p_acc.add_argument("--domain", required=True)
    p_acc.add_argument("--round-id", default=None)

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    if getattr(args, "_require_cause", False) and not args.cause:
        print("error: --cause is required for scaffold", file=sys.stderr)
        return 2
    handlers = {
        "record-change": cmd_record_change,
        "scaffold": cmd_scaffold,
        "list-domains": cmd_list_domains,
        "status": cmd_status,
        "next-action": cmd_next_action,
        "rollup-impact": cmd_rollup,
        "approve-impact": cmd_approve_impact,
        "set-domain-status": cmd_set_domain_status,
        "accept-domain": cmd_accept_domain,
    }
    return handlers[args.command](args)


if __name__ == "__main__":
    sys.exit(main())
