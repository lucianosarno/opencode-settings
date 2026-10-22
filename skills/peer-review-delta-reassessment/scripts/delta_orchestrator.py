#!/usr/bin/env python3
"""Product-wide peer-review delta reassessment — program_changes, impact, execution.

Layout (llms_peer_review process/standards/revision_rounds.md):
  {PEER_REVIEW_ROOT}/program_changes/changes/PC-YYYYMMDD-NNN_{meaning}.md
  {PEER_REVIEW_ROOT}/program_changes/{YYYYMMDDTHHMMSSZ}_{cause}/
    reassessment.md        change_refs, run_status, touch_order (frozen at approval)
    change_pack.md         index of the change ids of this run
    impact_by_domain/{domain}.md   one `| PC-… | touch|no-touch | reason |` row per change id
    impact_assessment.md   rollup written by rollup-impact
    execution_log.md       one row per touch domain

The timestamp prefix of the run folder is the review round id of every touch domain.
Run status: draft → awaiting_plan_approval → approved → executing → complete (or abandoned).

Examples:
  python delta_orchestrator.py --peer-review-root PEER record-change --meaning "taxonomy flexibility" --title "Taxonomy flexibility" --summary "Allow more than one taxonomy." --disposition accepted
  python delta_orchestrator.py --peer-review-root PEER --cause taxonomy scaffold --change-id PC-20261015-001
  python delta_orchestrator.py --peer-review-root PEER --program-dir PROG status
  python delta_orchestrator.py --peer-review-root PEER --program-dir PROG rollup-impact
  python delta_orchestrator.py --peer-review-root PEER --program-dir PROG approve-impact
  python delta_orchestrator.py --peer-review-root PEER --program-dir PROG set-domain-status --domain d01_scope --status in_progress --round-id ROUND
  python delta_orchestrator.py --peer-review-root PEER --program-dir PROG accept-domain --domain d01_scope
  python delta_orchestrator.py --peer-review-root PEER changes-status
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


FM_ORDER = ("reassessment_id", "cause", "run_status", "change_refs", "touch_order")
LIST_FM_KEYS = ("change_refs", "touch_order")
RUN_STATUSES = ("draft", "awaiting_plan_approval", "approved", "executing", "complete", "abandoned")
RUN_ACTIVE = ("approved", "executing", "complete")


def _fm_scalar(value: Any) -> str:
    text = str(value)
    if text == "" or text != text.strip() or re.search(r"[:#'\"\[\]{},&*!|>%@`]", text):
        return json.dumps(text)
    return text


def render_front_matter(fields: dict[str, Any]) -> str:
    """Write reassessment.md front matter in a fixed key order (read back by read_front_matter)."""
    keys = [k for k in FM_ORDER if k in fields] + [k for k in fields if k not in FM_ORDER]
    lines = ["---"]
    for key in keys:
        value = fields[key]
        if key in LIST_FM_KEYS:
            if not value:
                lines.append(f"{key}: []")
            else:
                lines.append(f"{key}:")
                lines.extend(f"  - {_fm_scalar(item)}" for item in value)
        elif value is None:
            lines.append(f"{key}: null")
        else:
            lines.append(f"{key}: {_fm_scalar(value)}")
    lines.append("---")
    return "\n".join(lines)


def update_reassessment(path: Path, **updates: Any) -> dict[str, Any]:
    """Merge fields into reassessment.md front matter; the Markdown body is kept as written."""
    orch = _import_orchestrator()
    if updates.get("run_status") not in (None, *RUN_STATUSES):
        raise ValueError(f"run_status must be one of {', '.join(RUN_STATUSES)}")
    fields = orch.read_front_matter(path)
    fields.update(updates)
    for key in LIST_FM_KEYS:
        fields[key] = orch.as_list(fields.get(key))
    lines = path.read_text(encoding="utf-8").split("\n")
    end = next((i for i in range(1, len(lines)) if lines[i].strip() == "---"), None)
    if end is None:
        raise ValueError(f"reassessment.md has no front matter: {path}")
    body = "\n".join(lines[end + 1 :])
    path.write_text(render_front_matter(fields) + "\n" + body, encoding="utf-8")
    return fields


def scaffold_program(
    peer_review_root: Path,
    *,
    cause: str,
    change_ids: list[str],
    timestamp: str | None = None,
    change_summary: str | None = None,
) -> dict[str, Any]:
    """Open one reassessment run that covers accepted program changes (revision_rounds.md)."""
    orch = _import_orchestrator()
    if not change_ids:
        raise ValueError("pass at least one --change-id: a run covers explicit program changes")
    changes = scan_change_files(changes_dir(peer_review_root))
    refs: list[str] = []
    for cid in change_ids:
        if cid not in changes:
            raise ValueError(f"unknown program change {cid} under program_changes/changes/")
        disposition = str(orch.read_front_matter(changes[cid]["path"]).get("disposition") or "")
        if disposition != "accepted":
            raise ValueError(
                f"{cid} is {disposition or 'without disposition'}; only accepted changes can be reassessed"
            )
        if cid not in refs:
            refs.append(cid)

    ts = timestamp or utc_now_ts()
    name = program_dir_name(ts, cause)
    prog = peer_review_root / PROGRAM_CHANGES_DIRNAME / name
    if (prog / "reassessment.md").exists():
        raise FileExistsError(f"reassessment already exists: {prog}")
    prog.mkdir(parents=True, exist_ok=True)
    (prog / "impact_by_domain").mkdir(exist_ok=True)

    fields = {
        "reassessment_id": name,
        "cause": cause,
        "run_status": "draft",
        "change_refs": refs,
        "touch_order": [],
    }
    body = (
        f"\n# Reassessment `{name}`\n\n"
        "Covers the change ids in front matter. Contract: `process/standards/revision_rounds.md`.\n"
    )
    (prog / "reassessment.md").write_text(render_front_matter(fields) + "\n" + body, encoding="utf-8")

    index_rows = []
    for cid in refs:
        meta = orch.read_front_matter(changes[cid]["path"])
        index_rows.append(
            f"| {cid} | {meta.get('title') or cid} | {changes[cid]['path'].resolve()} |"
        )
    pack_tmpl = TEMPLATES_DIR / "change_pack.md"
    pack_body = pack_tmpl.read_text(encoding="utf-8") if pack_tmpl.is_file() else "# Change pack\n"
    table = "\n".join(["| change_id | micro-reminder | statement |", "| --- | --- | --- |", *index_rows])
    pack_body = (
        pack_body.replace("{{SUMMARY}}", change_summary or "(fill in)")
        .replace("{{CAUSE}}", cause)
        .replace("{{TIMESTAMP}}", ts)
        .replace("{{CHANGE_TABLE}}", table)
    )
    (prog / "change_pack.md").write_text(pack_body, encoding="utf-8")

    rollup_tmpl = TEMPLATES_DIR / "impact_assessment.md"
    rollup_body = rollup_tmpl.read_text(encoding="utf-8") if rollup_tmpl.is_file() else "# Impact assessment\n"
    (prog / "impact_assessment.md").write_text(
        rollup_body.replace("{{CAUSE}}", cause).replace("{{TIMESTAMP}}", ts), encoding="utf-8"
    )
    exec_tmpl = TEMPLATES_DIR / "execution_log.md"
    exec_body = exec_tmpl.read_text(encoding="utf-8") if exec_tmpl.is_file() else "# Execution log\n"
    (prog / "execution_log.md").write_text(
        exec_body.replace("{{CAUSE}}", cause).replace("{{TIMESTAMP}}", ts), encoding="utf-8"
    )

    domains = list_consumer_domains(peer_review_root)
    impact_tmpl = TEMPLATES_DIR / "impact_by_domain" / "_template.md"
    impact_body = (
        impact_tmpl.read_text(encoding="utf-8")
        if impact_tmpl.is_file()
        else "# Impact — {{DOMAIN}}\n\nTODO_IMPACT\n\n{{IMPACT_ROWS}}\n"
    )
    rows = "\n".join(f"| {cid} | TODO_IMPACT | TODO_IMPACT |" for cid in refs)
    for domain in domains:
        dest = prog / "impact_by_domain" / f"{domain}.md"
        if not dest.is_file():
            dest.write_text(
                impact_body.replace("{{DOMAIN}}", domain)
                .replace("{{CAUSE}}", cause)
                .replace("{{TIMESTAMP}}", ts)
                .replace("{{IMPACT_ROWS}}", rows),
                encoding="utf-8",
            )

    return {
        "program_dir": str(prog.resolve()),
        "reassessment_id": name,
        "timestamp": ts,
        "cause": cause,
        "change_refs": refs,
        "run_status": "draft",
        "domains": domains,
        "change_pack": str((prog / "change_pack.md").resolve()),
    }


def parse_impact_file(path: Path) -> dict[str, Any]:
    """Read one domain's impact file: per-change effect rows and the domain verdict.

    Effect rows are `| PC-… | touch|no-touch | reason |` (revision_rounds.md, "Impact and
    execution"). The domain verdict is `touch` when any row is touch, else `no-touch`.
    """
    orch = _import_orchestrator()
    text = path.read_text(encoding="utf-8") if path.is_file() else ""
    effects = orch.impact_effects(path)
    sev_m = SEVERITY_RE.search(text)
    return {
        "path": str(path),
        "verdict": "touch" if "touch" in effects.values() else "no-touch",
        "effects": effects,
        "severity": (sev_m.group(1).lower() if sev_m else "none"),
        "filled": bool(effects),
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


def _promote_domain(path: Path) -> None:
    """Set every change row of a domain to touch (upstream coherence; revision_rounds.md)."""
    body = path.read_text(encoding="utf-8")
    body = re.sub(
        r"(?im)^(\s*\|\s*PC-\d{8}-\d{3}\s*\|\s*)no-touch(\s*\|)", r"\1touch\2", body
    )
    if "promoted_for_upstream_coherence: true" not in body:
        body = body.rstrip() + "\n\npromoted_for_upstream_coherence: true\n"
    path.write_text(body, encoding="utf-8")


def rollup_impact(
    peer_review_root: Path,
    program_dir: Path,
) -> dict[str, Any]:
    """Aggregate the per-change impact rows, promote for upstream coherence, write the rollup.

    Allowed only while the plan is still a draft or awaiting approval. After approval the
    touch list is frozen (process/standards/question_pyramid.md).
    """
    orch = _import_orchestrator()
    ref = program_dir / "reassessment.md"
    if not ref.is_file():
        raise ValueError(f"missing reassessment.md in {program_dir}")
    fm = orch.read_front_matter(ref)
    status = str(fm.get("run_status") or "")
    if status not in ("draft", "awaiting_plan_approval"):
        raise ValueError(
            f"run_status is {status}: the touch list is frozen; open a new reassessment instead"
        )
    ids = orch.as_list(fm.get("change_refs"))
    domains = list_consumer_domains(peer_review_root)
    by_domain = {
        d: parse_impact_file(program_dir / "impact_by_domain" / f"{d}.md") for d in domains
    }
    incomplete = {
        d: [c for c in ids if c not in info["effects"]]
        for d, info in by_domain.items()
    }
    incomplete = {d: missing for d, missing in incomplete.items() if missing}
    if incomplete:
        detail = "; ".join(f"{d} missing {', '.join(m)}" for d, m in incomplete.items())
        raise ValueError(
            "impact incomplete: each domain needs one touch|no-touch row per change id (" + detail + ")"
        )

    ordered = sorted(domains, key=orch.catalog_index)
    promoted: list[str] = []
    touch_seen = False
    for d in ordered:
        info = by_domain[d]
        if info["verdict"] == "touch":
            touch_seen = True
            continue
        if not touch_seen:
            continue
        text = Path(info["path"]).read_text(encoding="utf-8")
        if re.search(r"(?im)coherence_ok\s*:\s*true", text):
            continue
        _promote_domain(Path(info["path"]))
        info["effects"] = {c: "touch" for c in info["effects"]}
        info["verdict"] = "touch"
        info["promoted"] = True
        promoted.append(d)

    touch_list = [d for d in ordered if by_domain[d]["verdict"] == "touch"]
    header = ["domain"] + ids + ["verdict", "severity", "promoted"]
    lines = [
        "# Impact assessment (rollup)",
        "",
        "Aggregated from `impact_by_domain/`. Order follows `process/standards/domains.md`.",
        "",
        "| " + " | ".join(header) + " |",
        "| " + " | ".join("---" for _ in header) + " |",
    ]
    for d in ordered:
        info = by_domain[d]
        cells = [info["effects"].get(c, "") for c in ids]
        lines.append(
            "| "
            + " | ".join(
                [d, *cells, info["verdict"], info.get("severity", "none"), "yes" if info.get("promoted") else ""]
            )
            + " |"
        )
    lines.extend(["", "## Touch order (execution)", ""])
    lines.extend(f"1. `{d}`" for d in touch_list)
    if not touch_list:
        lines.append("_None — no domains marked touch._")
    lines.append("")
    if promoted:
        lines.extend(
            [
                "## Promotions",
                "",
                "Promoted `no-touch` → `touch` because an earlier domain in this run is touch and "
                "`coherence_ok: true` was not set. Every change row of a promoted domain is touch.",
                "",
            ]
        )
        lines.extend(f"- `{d}`" for d in promoted)
        lines.append("")
    (program_dir / "impact_assessment.md").write_text("\n".join(lines), encoding="utf-8")

    if status == "draft":
        update_reassessment(ref, run_status="awaiting_plan_approval")

    return {
        "domains": ordered,
        "by_domain": by_domain,
        "change_refs": ids,
        "touch_order": touch_list,
        "promoted": promoted,
        "impact_assessment": str((program_dir / "impact_assessment.md").resolve()),
    }


def approve_impact(peer_review_root: Path, program_dir: Path) -> dict[str, Any]:
    """Human approval of the plan: freeze touch_order and seed the execution log.

    Process rule: after `approved`, do not add, drop, or reorder touch domains
    (question_pyramid.md). This function is therefore the only writer of touch_order.
    """
    orch = _import_orchestrator()
    ref = program_dir / "reassessment.md"
    status = str(orch.read_front_matter(ref).get("run_status") or "")
    if status in RUN_ACTIVE or status == "abandoned":
        raise ValueError(f"run_status is {status}: the plan cannot be approved again")
    rollup = rollup_impact(peer_review_root, program_dir)
    touch_order = rollup["touch_order"]
    update_reassessment(ref, run_status="approved", touch_order=touch_order)
    name = program_dir.name
    ts, _, cause = name.partition("_")
    ensure_execution_rows(
        program_dir, touch_order, cause=cause or "change", timestamp=ts or utc_now_ts()
    )
    run_status = sync_run_status(program_dir)
    return {
        "program_dir": str(program_dir.resolve()),
        "run_status": run_status,
        "touch_order": touch_order,
        "promoted": rollup["promoted"],
    }


def sync_run_status(program_dir: Path) -> str:
    """Derive approved / executing / complete from the execution log (revision_rounds.md)."""
    orch = _import_orchestrator()
    ref = program_dir / "reassessment.md"
    fm = orch.read_front_matter(ref)
    status = str(fm.get("run_status") or "")
    if status not in ("approved", "executing", "complete"):
        return status
    order = orch.as_list(fm.get("touch_order"))
    statuses = read_execution_statuses(program_dir)
    values = [statuses.get(d, "pending") for d in order]
    if all(v == "accepted" for v in values):
        new_status = "complete"
    elif any(v != "pending" for v in values):
        new_status = "executing"
    else:
        new_status = "approved"
    if new_status != status:
        update_reassessment(ref, run_status=new_status)
    return new_status


def touch_change_ids(program_dir: Path, domain: str) -> list[str]:
    orch = _import_orchestrator()
    effects = orch.impact_effects(program_dir / "impact_by_domain" / f"{domain}.md")
    return [c for c, e in sorted(effects.items()) if e == "touch"]


def next_action(peer_review_root: Path, program_dir: Path) -> dict[str, Any]:
    orch = _import_orchestrator()
    ref = program_dir / "reassessment.md"
    status = str(orch.read_front_matter(ref).get("run_status") or "")
    round_id = program_dir.name.partition("_")[0]

    if status == "abandoned":
        return {"next_action": "abandoned", "detail": "This run was abandoned; open a new reassessment."}

    if status in ("draft", "awaiting_plan_approval"):
        domains = list_consumer_domains(peer_review_root)
        impact_dir = program_dir / "impact_by_domain"
        stubs = []
        for d in domains:
            path = impact_dir / f"{d}.md"
            if not path.is_file() or "TODO_IMPACT" in path.read_text(encoding="utf-8"):
                stubs.append(d)
        if status == "draft" and stubs:
            return {
                "next_action": "dispatch_impact_subagents",
                "domains": stubs,
                "detail": "Run one impact subagent per domain; fill one effect row per change id",
            }
        if status == "draft":
            return {
                "next_action": "rollup_impact",
                "detail": "Run rollup-impact (sets run_status to awaiting_plan_approval)",
            }
        return {
            "next_action": "await_human_impact_approval",
            "detail": "Steward reviews impact_assessment.md; then approve-impact freezes the touch order",
        }

    if status == "complete":
        return {"next_action": "done", "detail": "Run complete; coherence note in execution_log.md"}

    order = orch.as_list(orch.read_front_matter(ref).get("touch_order"))
    statuses = read_execution_statuses(program_dir)
    for d in order:
        st = statuses.get(d, "pending")
        common = {
            "domain": d,
            "status": st,
            "round_id": round_id,
            "change_ids": touch_change_ids(program_dir, d),
            "domain_root": str((peer_review_root / d).resolve()),
        }
        if st == "pending":
            return {
                "next_action": "run_domain_revision",
                "detail": (
                    f"Mark {d} in_progress, then init-round --kind revision --round-id {round_id} "
                    "--reassessment-ref <run>/reassessment.md --change-id <each change_ids entry>, "
                    "then peer-review-orchestrator phases 0–5"
                ),
                **common,
            }
        if st == "in_progress":
            return {
                "next_action": "resume_domain_round",
                "detail": f"Round of {d} is open; resume peer-review-orchestrator on it (do not init again)",
                **common,
            }
        if st == "awaiting_human":
            return {
                "next_action": "await_human_domain_approval",
                "detail": f"Steward accepts the round of {d}; then accept-domain",
                **common,
            }

    run_status = sync_run_status(program_dir)
    if run_status == "complete":
        return {"next_action": "done", "detail": "All touch domains accepted; coherence note in execution_log.md"}
    return {"next_action": "check_run_status", "detail": f"run_status is {run_status}"}


def set_domain_status(
    program_dir: Path,
    domain: str,
    status: str,
    *,
    round_id: str | None = None,
    notes: str = "",
) -> dict[str, Any]:
    orch = _import_orchestrator()
    fm = orch.read_front_matter(program_dir / "reassessment.md")
    run_status = str(fm.get("run_status") or "")
    order = orch.as_list(fm.get("touch_order"))
    if run_status not in ("approved", "executing"):
        raise ValueError(f"run_status is {run_status}; execution starts only after approve-impact")
    if domain not in order:
        raise ValueError(f"{domain} is not in the frozen touch_order of this run")
    if status == "skipped":
        raise ValueError(f"{domain} is a touch domain; a touch domain is never skipped")

    name = program_dir.name
    ts, _, cause = name.partition("_")
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
        prior[domain] = {"domain": domain, "status": status, "round_id": round_id or "", "notes": notes}
    else:
        prior[domain]["status"] = status
        if round_id is not None:
            prior[domain]["round_id"] = round_id
        if notes:
            prior[domain]["notes"] = notes

    ordered = sorted(prior.keys(), key=orch.catalog_index)
    write_execution_log(
        program_dir,
        [prior[d] for d in ordered],
        cause=cause or "change",
        timestamp=ts or utc_now_ts(),
        extra_body="\n".join(trailing).strip() or None,
    )
    sync_run_status(program_dir)
    return prior[domain]


def accept_domain(
    peer_review_root: Path,
    program_dir: Path,
    domain: str,
    *,
    round_id: str | None = None,
) -> dict[str, Any]:
    orch = _import_orchestrator()
    current_status = read_execution_statuses(program_dir).get(domain, "pending")
    if current_status != "awaiting_human":
        raise ValueError(
            f"{domain} must be awaiting_human before accept (current: {current_status})"
        )
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
    return {"domain": domain, "round_id": rid, "execution": row, "run_status": sync_run_status(program_dir)}


def _runs(peer_review_root: Path) -> list[dict[str, Any]]:
    orch = _import_orchestrator()
    base = peer_review_root / PROGRAM_CHANGES_DIRNAME
    runs: list[dict[str, Any]] = []
    if not base.is_dir():
        return runs
    for d in sorted(p for p in base.iterdir() if p.is_dir()):
        ref = d / "reassessment.md"
        if ref.is_file():
            fm = orch.read_front_matter(ref)
            runs.append(
                {
                    "dir": d,
                    "name": d.name,
                    "run_status": str(fm.get("run_status") or ""),
                    "change_refs": orch.as_list(fm.get("change_refs")),
                }
            )
    return runs


def _execution_state(prog: Path, cid: str) -> tuple[str, list[str]]:
    """Application state of one change inside its governing run (rows 4–8 of the table)."""
    orch = _import_orchestrator()
    impact_dir = prog / "impact_by_domain"
    effects = {
        f.stem: orch.impact_effects(f)
        for f in sorted(impact_dir.glob("*.md"))
    } if impact_dir.is_dir() else {}
    if not effects or any(cid not in eff for eff in effects.values()):
        return "assessing", []
    required = [d for d, eff in sorted(effects.items()) if eff.get(cid) == "touch"]
    if not required:
        return "applied", []
    statuses = read_execution_statuses(prog)
    if any(d not in statuses for d in required):
        return "assessing", required
    values = [statuses[d] for d in required]
    if all(v == "accepted" for v in values):
        return "applied", required
    if any(v == "accepted" for v in values):
        return "partially_applied", required
    if any(v in ("in_progress", "awaiting_human") for v in values):
        return "in_progress", required
    return "planned", required


def application_status(peer_review_root: Path) -> list[dict[str, Any]]:
    """Derive each change's application status. Nothing is stored in the change file."""
    orch = _import_orchestrator()
    runs = _runs(peer_review_root)
    rows: list[dict[str, Any]] = []
    changes = scan_change_files(changes_dir(peer_review_root))
    for cid, info in sorted(changes.items()):
        meta = orch.read_front_matter(info["path"])
        disposition = str(meta.get("disposition") or "")
        governing = [r for r in runs if cid in r["change_refs"] and r["run_status"] in RUN_ACTIVE]
        gov = governing[-1] if governing else None
        recheck = [
            r
            for r in runs
            if cid in r["change_refs"]
            and r["run_status"] in ("draft", "awaiting_plan_approval")
            and (gov is None or r["name"] > gov["name"])
        ]
        open_recheck = recheck[-1]["name"] if recheck else None
        required: list[str] = []
        if disposition in ("proposed", "rejected", "superseded"):
            state = "n/a"
        elif gov is None:
            state = "assessing" if recheck else "uncovered"
        else:
            state, required = _execution_state(gov["dir"], cid)
        rows.append(
            {
                "change_id": cid,
                "meaning": info["meaning"],
                "title": meta.get("title"),
                "disposition": disposition,
                "application": state,
                "governing_run": gov["name"] if gov else None,
                "open_recheck": open_recheck,
                "required_domains": required,
            }
        )
    return rows


def cmd_scaffold(args: argparse.Namespace) -> int:
    peer = Path(args.peer_review_root)
    try:
        result = scaffold_program(
            peer,
            cause=args.cause,
            change_ids=args.change_ids or [],
            timestamp=args.timestamp,
            change_summary=args.summary,
        )
    except (ValueError, FileExistsError) as exc:
        print(json.dumps({"error": str(exc)}, indent=2), file=sys.stderr)
        return 1
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
    try:
        result = rollup_impact(peer, prog)
    except ValueError as exc:
        print(json.dumps({"error": str(exc)}, indent=2), file=sys.stderr)
        return 1
    print(json.dumps(result, indent=2, default=str))
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
        "run_status": str(_import_orchestrator().read_front_matter(prog / "reassessment.md").get("run_status") or ""),
        "execution": read_execution_statuses(prog),
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


def cmd_changes_status(args: argparse.Namespace) -> int:
    peer = Path(args.peer_review_root)
    print(json.dumps({"changes": application_status(peer)}, indent=2))
    return 0


def cmd_abandon(args: argparse.Namespace) -> int:
    peer = Path(args.peer_review_root)
    prog = resolve_program_dir(
        peer,
        program_dir=Path(args.program_dir) if args.program_dir else None,
        cause=args.cause,
    )
    if not prog:
        print(json.dumps({"error": "program_dir not found"}), file=sys.stderr)
        return 1
    ref = prog / "reassessment.md"
    status = str(_import_orchestrator().read_front_matter(ref).get("run_status") or "")
    if status in ("executing", "complete"):
        print(json.dumps({"error": f"run_status is {status}; a running or finished run is not abandoned"}), file=sys.stderr)
        return 1
    update_reassessment(ref, run_status="abandoned")
    with ref.open("a", encoding="utf-8") as f:
        f.write(f"\nAbandoned: {args.reason.strip()}\n")
    print(json.dumps({"program_dir": str(prog.resolve()), "run_status": "abandoned"}, indent=2))
    return 0


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
    try:
        result = approve_impact(peer, prog)
    except ValueError as exc:
        print(json.dumps({"error": str(exc)}, indent=2), file=sys.stderr)
        return 1
    print(json.dumps(result, indent=2, default=str))
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
    try:
        row = set_domain_status(
            prog,
            args.domain,
            args.status,
            round_id=args.round_id,
            notes=args.notes or "",
        )
    except ValueError as exc:
        print(json.dumps({"error": str(exc)}, indent=2), file=sys.stderr)
        return 1
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

    p_sc = sub.add_parser(
        "scaffold",
        help="Open program_changes/{ts}_{cause}/reassessment.md covering accepted change ids",
    )
    p_sc.add_argument(
        "--change-id",
        dest="change_ids",
        action="append",
        required=True,
        help="PC-YYYYMMDD-NNN covered by this run (repeat for several; must be accepted)",
    )
    p_sc.add_argument("--timestamp", default=None)
    p_sc.add_argument("--summary", default=None)
    p_sc.set_defaults(_require_cause=True)

    sub.add_parser("list-domains", help="List d0X folders under peer-review-root")
    sub.add_parser("status", help="Run status + next_action")
    sub.add_parser("next-action", help="Alias for status")
    sub.add_parser("rollup-impact", help="Aggregate impact rows into impact_assessment.md")
    sub.add_parser("approve-impact", help="Human approval: freezes touch_order, run_status approved")
    sub.add_parser(
        "changes-status",
        help="Derived application status of every program change (no stored status)",
    )
    p_ab = sub.add_parser("abandon", help="Abandon a run that is not executing or complete")
    p_ab.add_argument("--reason", required=True)

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
        "changes-status": cmd_changes_status,
        "abandon": cmd_abandon,
        "set-domain-status": cmd_set_domain_status,
        "accept-domain": cmd_accept_domain,
    }
    return handlers[args.command](args)


if __name__ == "__main__":
    sys.exit(main())
