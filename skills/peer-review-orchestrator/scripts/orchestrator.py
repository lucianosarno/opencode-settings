#!/usr/bin/env python3
"""Peer review orchestrator helpers — status, gates, prompt resolution, rounds.

Default (no subcommand): print JSON status for --review-root / --domain-root.

Examples:
  python orchestrator.py init-round --domain-root path/to/d06_… --kind initial
  python orchestrator.py --review-root path/to/d06_…/20260601T100000Z
  python orchestrator.py --domain-root path/to/d06_…
  python orchestrator.py phase1-gate --review-root ... --slot llm1_composer
  python orchestrator.py resolve-prompt --review-root ... --phase 2
  python orchestrator.py resolve-shortlist --review-root ... --phase 2
  python orchestrator.py list-participants --review-root ...
"""

from __future__ import annotations

import argparse
import json
import re
import shutil
import sys
from dataclasses import dataclass, asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

SKILL_DIR = Path(__file__).resolve().parent.parent
CONFIG_DIR = SKILL_DIR / "config"

PHASE_PROMPT_FILES = {
    0: "phase0_setup.md",
    1: "phase1_questions.md",
    2: "phase2_initial_proposal.md",
    3: "phase3_crossed_scrutiny.md",
    4: "phase4_individual_final_answer.md",
    5: "phase5_final_answer.md",
}

PHASE_NAMES = {
    0: "setup",
    1: "questions",
    2: "initial_proposals",
    3: "crossed_scrutiny",
    4: "final_proposals",
    5: "unified_answer",
}

# Formalized domain sequence (process/standards/domains.md). Earlier = upstream.
DOMAIN_CATALOG_ORDER = [
    "d01_scope",
    "d02_security_context",
    "d03_information_conceptual",
    "d04a_information_logical",
    "d04b_contracts_draft",
    "d05_knowledge_schema",
    "d06_cloud_foundation",
    "d07_product_behavior",
    "d08_llm_grounding_policy",
    "d09_ux_interaction_drivers",
    "d10_architecture_decision_drivers",
    "d11_architecture_definition",
    "d12_security_technical",
    "d13a_information_physical",
    "d13b_contracts",
    "d14_product_behavior_binding",
    "d15_llm_grounding_binding",
    "d16_ux_interaction_definition",
    "d17_verification_assurance",
    "d18_design_definition",
]

ROUND_ID_RE = re.compile(r"^\d{8}T\d{6}Z$")


@dataclass
class Participant:
    slot: str
    alias: str
    folder_suffix: str


def _load_json(path: Path) -> Any:
    with path.open(encoding="utf-8") as f:
        return json.load(f)


def load_skill_settings() -> dict[str, Any]:
    path = CONFIG_DIR / "settings.json"
    if path.is_file():
        return _load_json(path)
    return {}


def load_task_model_map() -> dict[str, Any]:
    path = CONFIG_DIR / "task_model_map.json"
    if path.is_file():
        return _load_json(path)
    return {
        "task_allow_list": [],
        "llm_code_to_task": {},
        "task_family": {},
    }


def default_llms_root() -> Path:
    settings = load_skill_settings()
    configured = settings.get("llms_peer_review_process_root")
    if configured:
        return Path(configured)
    return Path(r"C:/Users/LucianoSoares/Projects/llms_peer_review/process")


DEFAULT_LLMS_ROOT = default_llms_root()


def repo_root_from_llms_root(llms_root: Path) -> Path:
    """process/ → llms_peer_review repo root (works across consumer repos)."""
    return llms_root.resolve().parent


def default_shortlist_path(llms_root: Path) -> Path:
    settings = load_skill_settings()
    rel = (
        (settings.get("shortlist") or {}).get("relative_to_repo")
        or "tools/llm_selection/reports/ranking_shortlist_cursor_capability_weighted_latest.json"
    )
    return repo_root_from_llms_root(llms_root) / rel


def load_leader_selection_settings() -> dict[str, Any]:
    """Phase-5 leader pick: pure quality vs shortlist value; optional among-roster filter."""
    settings = load_skill_settings()
    cfg = dict(settings.get("leader_selection") or {})
    return {
        "score_basis": str(cfg.get("score_basis") or "quality").strip().lower(),
        "among_participants_only": bool(
            cfg.get("among_participants_only")
            if cfg.get("among_participants_only") is not None
            else True
        ),
        "calculation_relative_to_repo": str(
            cfg.get("calculation_relative_to_repo")
            or "tools/llm_selection/reports/ranking_calculation_latest.json"
        ),
    }


def default_calculation_path(llms_root: Path) -> Path:
    cfg = load_leader_selection_settings()
    return repo_root_from_llms_root(llms_root) / cfg["calculation_relative_to_repo"]


def _quality_value_from_calc_row(row: dict[str, Any]) -> float | None:
    """Extract pure quality (no /cost) from a ranking_calculation LLM row."""
    calc = row.get("calculation") or {}
    q = calc.get("quality")
    if isinstance(q, dict) and q.get("value") is not None:
        try:
            return float(q["value"])
        except (TypeError, ValueError):
            return None
    if row.get("quality_score") is not None:
        try:
            return float(row["quality_score"])
        except (TypeError, ValueError):
            return None
    return None


def load_quality_ranked_rows(
    calculation_path: Path,
    application_key: str,
) -> dict[str, Any]:
    """Read ranking_calculation and return [[llm_code, quality], ...] sorted desc.

    This is a skill-side re-rank: llms_peer_review does not ship a quality-only
    shortlist; quality lives on calculation.quality.value beside value_score*.
    """
    data = _load_json(calculation_path)
    apps = data.get("applications") or {}
    app = apps.get(application_key) or {}
    llms = list(app.get("llms") or [])
    ranked: list[tuple[str, float]] = []
    for row in llms:
        if not isinstance(row, dict):
            continue
        code = row.get("llm_code")
        q = _quality_value_from_calc_row(row)
        if not code or q is None:
            continue
        ranked.append((str(code), float(q)))
    ranked.sort(key=lambda t: (-t[1], t[0]))
    return {
        "fv": data.get("formula_version") or data.get("fv"),
        "application_key": application_key,
        "rows": [[code, score] for code, score in ranked],
        "path": str(calculation_path),
        "llm_count": len(ranked),
    }


def filter_quality_rows_to_families(
    rows: list[list[Any]],
    allowed_families: set[str],
    *,
    task_map: dict[str, Any] | None = None,
) -> list[list[Any]]:
    """Keep highest-quality llm_code per allowed Task family; drop unmapped/others."""
    task_map = task_map or load_task_model_map()
    best_by_family: dict[str, tuple[str, float]] = {}
    for row in rows:
        if not isinstance(row, (list, tuple)) or len(row) < 2:
            continue
        llm_code = str(row[0])
        try:
            score = float(row[1])
        except (TypeError, ValueError):
            continue
        slug = map_llm_code_to_task(llm_code, task_map)
        if not slug:
            continue
        family = task_family_of(slug, task_map)
        if family not in allowed_families:
            continue
        prev = best_by_family.get(family)
        if prev is None or score > prev[1]:
            best_by_family[family] = (llm_code, score)
    ordered = sorted(best_by_family.values(), key=lambda t: (-t[1], t[0]))
    return [[code, score] for code, score in ordered]


def _parse_models_yaml(path: Path) -> dict[str, str]:
    """Parse llmN: model-slug lines from a models config file."""
    if not path.is_file():
        return {}
    slots: dict[str, str] = {}
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.split("#", 1)[0].strip()
        if not line or line.endswith(":"):
            continue
        match = re.match(r"^(llm\d+):\s*(.+)$", line, re.I)
        if match:
            slots[match.group(1).lower()] = match.group(2).strip().strip("'\"")
    return slots


def _merge_slots(base: dict[str, str], overlay: dict[str, str]) -> dict[str, str]:
    merged = dict(base)
    merged.update(overlay)
    return merged


def load_yaml_overrides(review_root: Path | None = None) -> dict[str, Any]:
    """Explicit YAML overlays only (review + local). Used above shortlist."""
    configs: list[tuple[str, Path]] = [
        ("local", SKILL_DIR / "peer_review.models.local.yaml"),
    ]
    if review_root:
        configs.append(("review", review_root / "peer_review.models.yaml"))

    merged: dict[str, str] = {}
    sources: list[str] = []
    for label, path in configs:
        parsed = _parse_models_yaml(path)
        if parsed:
            merged = _merge_slots(merged, parsed)
            sources.append(f"{label}:{path}")
    return {"slots": merged, "sources": sources}


def load_fallback_models_yaml() -> dict[str, Any]:
    path = SKILL_DIR / "models.yaml"
    parsed = _parse_models_yaml(path)
    sources = [f"fallback:{path}"] if parsed else []
    return {"slots": parsed, "sources": sources}


def load_models_config(review_root: Path | None = None) -> dict[str, Any]:
    """Legacy merge: default yaml < local < review (no shortlist)."""
    base = load_fallback_models_yaml()
    overlays = load_yaml_overrides(review_root)
    merged = _merge_slots(base.get("slots", {}), overlays.get("slots", {}))
    sources = list(base.get("sources", [])) + list(overlays.get("sources", []))
    return {"slots": merged, "sources": sources}


def map_llm_code_to_task(llm_code: str, task_map: dict[str, Any] | None = None) -> str | None:
    task_map = task_map or load_task_model_map()
    code = (llm_code or "").strip()
    direct = (task_map.get("llm_code_to_task") or {}).get(code)
    allow = set(task_map.get("task_allow_list") or [])
    if direct and (not allow or direct in allow):
        return direct
    # Already a Task slug?
    if code in allow:
        return code
    return None


def task_family_of(slug: str, task_map: dict[str, Any] | None = None) -> str:
    task_map = task_map or load_task_model_map()
    return (task_map.get("task_family") or {}).get(slug, slug)


def provider_of_family(
    family: str, task_map: dict[str, Any] | None = None
) -> str:
    """Vendor for a Task family (OpenAI, Anthropic, …). Unknown → family string."""
    task_map = task_map or load_task_model_map()
    mapped = (task_map.get("family_provider") or {}).get(family)
    if mapped:
        return str(mapped)
    return str(family or "unknown")


def provider_of_slug(
    slug: str, task_map: dict[str, Any] | None = None
) -> str:
    task_map = task_map or load_task_model_map()
    return provider_of_family(task_family_of(slug, task_map), task_map)


def unique_provider_required() -> bool:
    settings = load_skill_settings()
    return bool((settings.get("dispatch") or {}).get("unique_provider", True))


def load_roster_sizing() -> dict[str, Any]:
    """min/max slots + tau/rho thresholds for auto roster size."""
    settings = load_skill_settings()
    cfg = dict(settings.get("roster_sizing") or {})
    dispatch = settings.get("dispatch") or {}
    min_slots = int(cfg.get("min_slots") or 4)
    max_slots = int(
        cfg.get("max_slots")
        or dispatch.get("proposer_slots")
        or max(min_slots, 8)
    )
    if max_slots < min_slots:
        max_slots = min_slots
    return {
        "min_slots": min_slots,
        "max_slots": max_slots,
        "tau_vs_leader": float(cfg.get("tau_vs_leader") or 0.15),
        "rho_vs_prev": float(cfg.get("rho_vs_prev") or 0.40),
    }


def choose_roster_size(
    scores: list[float],
    *,
    min_slots: int = 4,
    max_slots: int = 8,
    tau_vs_leader: float = 0.15,
    rho_vs_prev: float = 0.40,
) -> dict[str, Any]:
    """Pick how many unique-provider seats to keep from ranked scores.

    Always keeps ``min_slots`` (or fewer if not enough scored rows — caller may
    still pad with unscored fallback up to min). Retention (tau) and cliff
    (rho) apply only when considering seat ``min_slots + 1`` and beyond.
    """
    if min_slots < 1:
        min_slots = 1
    if max_slots < min_slots:
        max_slots = min_slots

    clean: list[float] = []
    for raw in scores:
        if raw is None:
            break
        try:
            val = float(raw)
        except (TypeError, ValueError):
            break
        if val < 0:
            break
        clean.append(val)

    n = len(clean)
    base: dict[str, Any] = {
        "min_slots": min_slots,
        "max_slots": max_slots,
        "tau_vs_leader": tau_vs_leader,
        "rho_vs_prev": rho_vs_prev,
        "scored_count": n,
        "scores": clean,
    }

    if n == 0:
        return {
            **base,
            "chosen_k": min_slots,
            "stop_reason": "no_scores_use_min",
            "stop_at_index": None,
        }

    # Floor: never apply cliff/retention inside the minimum band
    k = min(min_slots, n)
    if n <= min_slots:
        return {
            **base,
            "chosen_k": min_slots,
            "stop_reason": "at_min_floor",
            "stop_at_index": None,
        }

    s1 = clean[0]
    if s1 <= 0:
        return {
            **base,
            "chosen_k": min_slots,
            "stop_reason": "non_positive_leader_score",
            "stop_at_index": None,
        }

    # Extend past min_slots only; cliff between seats 1..min is ignored
    while k < min(max_slots, n):
        s_next = clean[k]  # 0-based index of candidate for seat k+1
        s_prev = clean[k - 1]
        ratio_leader = s_next / s1
        ratio_prev = s_next / s_prev if s_prev > 0 else 0.0
        if ratio_leader < tau_vs_leader:
            return {
                **base,
                "chosen_k": k,
                "stop_reason": "tau_vs_leader",
                "stop_at_index": k + 1,
                "rejected_score": s_next,
                "ratio_vs_leader": ratio_leader,
                "ratio_vs_prev": ratio_prev,
            }
        if ratio_prev < rho_vs_prev:
            return {
                **base,
                "chosen_k": k,
                "stop_reason": "rho_vs_prev",
                "stop_at_index": k + 1,
                "rejected_score": s_next,
                "ratio_vs_leader": ratio_leader,
                "ratio_vs_prev": ratio_prev,
            }
        k += 1

    if k >= max_slots:
        stop_reason = "max_slots"
    else:
        stop_reason = "no_more_scored"
    return {
        **base,
        "chosen_k": k,
        "stop_reason": stop_reason,
        "stop_at_index": None,
    }


def folder_alias_for_family(
    family: str, task_map: dict[str, Any] | None = None
) -> str:
    """Stable phase0 folder alias for a Task family (e.g. gpt-5.6-luna → gpt56_luna)."""
    task_map = task_map or load_task_model_map()
    aliases = task_map.get("folder_alias") or {}
    if family in aliases:
        return str(aliases[family])
    # Deterministic fallback: strip dots, keep underscores
    return re.sub(r"[^a-z0-9_]+", "_", family.lower()).strip("_")


def suggested_folder_suffix(
    slot: str, family: str, task_map: dict[str, Any] | None = None
) -> str:
    """llm1 + gpt-5.6-luna → llm1_gpt56_luna."""
    alias = folder_alias_for_family(family, task_map)
    return f"{slot.lower()}_{alias}"


def _normalize_alias_token(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "", (value or "").lower())


def alias_matches_family(
    alias: str, family: str, task_map: dict[str, Any] | None = None
) -> bool:
    """True when phase0 alias/folder label matches the resolved Task family."""
    task_map = task_map or load_task_model_map()
    expected = folder_alias_for_family(family, task_map)
    a = _normalize_alias_token(alias)
    e = _normalize_alias_token(expected)
    f = _normalize_alias_token(family)
    if not a:
        return False
    if a == e or a == f:
        return True
    # Tolerate short forms (luna ↔ gpt56_luna, fable ↔ claude_fable)
    if len(a) >= 4 and (a in e or e in a or a in f or f in a):
        return True
    return False


def detect_participant_model_mismatches(
    participants: list[Participant],
    roster_slots: dict[str, dict[str, Any]],
    *,
    task_map: dict[str, Any] | None = None,
) -> list[dict[str, Any]]:
    """Flag phase0 folder aliases that disagree with shortlist-resolved families."""
    task_map = task_map or load_task_model_map()
    mismatches: list[dict[str, Any]] = []
    for p in participants:
        entry = roster_slots.get(p.slot) or {}
        family = entry.get("family")
        slug = entry.get("model_slug")
        if not family or not slug:
            continue
        expected_alias = folder_alias_for_family(str(family), task_map)
        expected_folder = suggested_folder_suffix(p.slot, str(family), task_map)
        alias_ok = alias_matches_family(p.alias, str(family), task_map)
        folder_ok = alias_matches_family(
            p.folder_suffix.split("_", 1)[-1] if "_" in p.folder_suffix else p.folder_suffix,
            str(family),
            task_map,
        )
        if alias_ok and folder_ok:
            continue
        mismatches.append(
            {
                "slot": p.slot,
                "phase0_alias": p.alias,
                "phase0_folder_suffix": p.folder_suffix,
                "resolved_family": family,
                "resolved_model_slug": slug,
                "resolved_llm_code": entry.get("llm_code"),
                "expected_alias": expected_alias,
                "expected_folder_suffix": expected_folder,
                "severity": (
                    "phase0_alias_or_folder_diverges_from_resolved_model"
                ),
                "action": (
                    "Before writing artifacts for this slot: update phase0_setup.md "
                    f"alias/folder to '{expected_alias}' / '{expected_folder}' and "
                    "use that path. Do not write under the stale folder name. "
                    "If artifacts already exist under the stale name, pause and ask "
                    "the steward whether to rename or keep paths."
                ),
            }
        )
    return mismatches


def load_shortlist(path: Path) -> dict[str, Any]:
    if not path.is_file():
        raise FileNotFoundError(
            f"Shortlist not found: {path}. "
            "Regenerate in llms_peer_review with: "
            "python tools/llm_selection/llm_selection_tool.py rank --log"
        )
    data = _load_json(path)
    if not isinstance(data, dict) or "applications" not in data:
        raise ValueError(f"Invalid shortlist shape in {path}")
    return data


def _domain_prefix(domain_code: str) -> str:
    """d06_verification_assurance → d06; d06 → d06."""
    if not domain_code:
        return ""
    m = re.match(r"^(d\d+)", domain_code, re.I)
    return m.group(1).lower() if m else domain_code.lower()


def resolve_application_key(
    shortlist: dict[str, Any],
    *,
    domain_code: str,
    phase: int,
    project_code: str | None = None,
) -> dict[str, Any]:
    """Pick best shortlist application key for domain × peer-review phase."""
    settings = load_skill_settings()
    phase_map = (settings.get("dispatch") or {}).get("phase_to_application_phase") or {}
    app_phase = str(phase_map.get(str(phase), str(phase)))
    apps = shortlist.get("applications") or {}
    keys = list(apps.keys())
    dpref = _domain_prefix(domain_code)
    project = (project_code or "").strip().lower()

    candidates: list[str] = []

    def _add(pred) -> None:
        for k in keys:
            if pred(k) and k not in candidates:
                candidates.append(k)

    # Exact project overlay first
    if dpref and project and project not in ("", "generic", "*"):
        _add(lambda k: k.startswith(f"{dpref}_") and f"_phase{app_phase}_" in k and k.endswith(f"_{project}"))
        _add(lambda k: k.startswith(f"{dpref}_") and k.endswith(f"_phase{app_phase}_{project}"))

    # Domain + phase (no project suffix)
    if dpref:
        if app_phase == "5":
            _add(
                lambda k: k.startswith(f"{dpref}_")
                and f"_phase{app_phase}" in k
                and not re.search(r"_phase5_.+", k)  # prefer bare phase5 over project overlay
            )
            _add(lambda k: k.startswith(f"{dpref}_") and f"_phase{app_phase}" in k)
        elif app_phase == "3":
            _add(lambda k: k.startswith(f"{dpref}_") and f"_phase{app_phase}" in k)
            _add(lambda k: k == "generic_phase3_critique")
            # critiques fall back to domain phase2 ranking
            _add(lambda k: k.startswith(f"{dpref}_") and "_phase2" in k and not re.search(r"_phase2_.+", k))
        else:
            _add(
                lambda k: k.startswith(f"{dpref}_")
                and f"_phase{app_phase}" in k
                and not re.search(rf"_phase{app_phase}_.+", k)
            )
            _add(lambda k: k.startswith(f"{dpref}_") and f"_phase{app_phase}" in k)

    # Generic fallbacks
    if app_phase == "5":
        _add(lambda k: k == "generic_phase5_leader")
    elif app_phase == "3":
        _add(lambda k: k == "generic_phase3_critique")
        _add(lambda k: k == "generic_phase2_proposal")
    else:
        _add(lambda k: k == "generic_phase2_proposal")

    chosen = candidates[0] if candidates else None
    return {
        "application_key": chosen,
        "application_phase": app_phase,
        "candidates_considered": candidates,
        "resolved": chosen is not None,
    }


def shortlist_task_candidates(
    shortlist: dict[str, Any],
    application_key: str,
    *,
    task_map: dict[str, Any] | None = None,
    enforce_unique_provider: bool | None = None,
) -> dict[str, Any]:
    """Walk ranked shortlist rows → Task-dispatchable unique families/providers."""
    task_map = task_map or load_task_model_map()
    if enforce_unique_provider is None:
        enforce_unique_provider = unique_provider_required()
    rows = list((shortlist.get("applications") or {}).get(application_key) or [])
    selected: list[dict[str, Any]] = []
    skipped: list[dict[str, Any]] = []
    seen_families: set[str] = set()
    seen_providers: set[str] = set()

    for rank, row in enumerate(rows, start=1):
        if not isinstance(row, (list, tuple)) or len(row) < 1:
            continue
        llm_code = str(row[0])
        score = row[1] if len(row) > 1 else None
        slug = map_llm_code_to_task(llm_code, task_map)
        if not slug:
            skipped.append(
                {
                    "rank": rank,
                    "llm_code": llm_code,
                    "score": score,
                    "reason": "not_in_task_map",
                }
            )
            continue
        family = task_family_of(slug, task_map)
        provider = provider_of_family(family, task_map)
        if family in seen_families:
            skipped.append(
                {
                    "rank": rank,
                    "llm_code": llm_code,
                    "score": score,
                    "task_slug": slug,
                    "family": family,
                    "provider": provider,
                    "reason": f"duplicate_family:{family}",
                }
            )
            continue
        if enforce_unique_provider and provider in seen_providers:
            skipped.append(
                {
                    "rank": rank,
                    "llm_code": llm_code,
                    "score": score,
                    "task_slug": slug,
                    "family": family,
                    "provider": provider,
                    "reason": f"duplicate_provider:{provider}",
                }
            )
            continue
        seen_families.add(family)
        seen_providers.add(provider)
        selected.append(
            {
                "rank": rank,
                "llm_code": llm_code,
                "score": score,
                "task_slug": slug,
                "family": family,
                "provider": provider,
            }
        )

    return {
        "application_key": application_key,
        "selected": selected,
        "skipped": skipped,
        "fv": shortlist.get("fv"),
        "unique_provider": enforce_unique_provider,
    }


def build_dispatch_roster(
    *,
    llms_root: Path,
    review_root: Path | None,
    domain_code: str,
    phase: int,
    slot_count: int | None = None,
    project_code: str | None = None,
    shortlist_path: Path | None = None,
    _leader_inner: bool = False,
) -> dict[str, Any]:
    """Resolve llm1..llmN Task slugs from shortlist + YAML precedence.

    Phase 5 (leader): by default re-ranks from ranking_calculation pure quality
    among the phase-2 proposer families (see leader_selection in settings.json),
    ignoring cost/benefit value_score. Proposer/critic phases keep the
    capability_weighted shortlist.
    """
    sizing_cfg = load_roster_sizing()
    explicit_slot_count = slot_count is not None
    leader_cfg = load_leader_selection_settings()
    leader_meta: dict[str, Any] = {
        "score_basis": leader_cfg["score_basis"],
        "among_participants_only": leader_cfg["among_participants_only"],
        "applied": False,
    }

    path = shortlist_path or default_shortlist_path(llms_root)
    shortlist_error: str | None = None
    shortlist_data: dict[str, Any] | None = None
    try:
        shortlist_data = load_shortlist(path)
    except (OSError, ValueError) as exc:
        shortlist_error = str(exc)

    app_info: dict[str, Any] = {
        "application_key": None,
        "application_phase": None,
        "candidates_considered": [],
        "resolved": False,
    }
    candidates: dict[str, Any] = {"selected": [], "skipped": [], "fv": None}
    if shortlist_data is not None:
        app_info = resolve_application_key(
            shortlist_data,
            domain_code=domain_code,
            phase=phase,
            project_code=project_code,
        )
        if app_info.get("application_key"):
            candidates = shortlist_task_candidates(
                shortlist_data, app_info["application_key"]
            )

    # Phase 5: optional pure-quality leader ranking (skill-only; no llms_peer_review change)
    app_phase_early = str(app_info.get("application_phase") or "")
    if (
        not _leader_inner
        and app_phase_early == "5"
        and leader_cfg["score_basis"] == "quality"
        and app_info.get("application_key")
    ):
        calc_path = default_calculation_path(llms_root)
        try:
            quality_pack = load_quality_ranked_rows(
                calc_path, str(app_info["application_key"])
            )
            quality_rows = list(quality_pack.get("rows") or [])
            allowed_families: set[str] | None = None
            participant_source = None

            if leader_cfg["among_participants_only"]:
                # Roster families from phase-2 value shortlist (proposers), same seat count.
                proposer = build_dispatch_roster(
                    llms_root=llms_root,
                    review_root=review_root,
                    domain_code=domain_code,
                    phase=2,
                    slot_count=slot_count,
                    project_code=project_code,
                    shortlist_path=shortlist_path,
                    _leader_inner=True,
                )
                allowed_families = {
                    str(s["family"])
                    for s in (proposer.get("slots") or {}).values()
                    if s.get("resolved") and s.get("family")
                }
                participant_source = "phase2_proposer_roster"
                # If phase0 already names participants, prefer those aliases' families.
                if review_root is not None:
                    try:
                        parts = parse_participants(Path(review_root))
                    except Exception:
                        parts = []
                    if parts:
                        task_map_pre = load_task_model_map()
                        alias_to_family = {
                            str(v).lower(): k
                            for k, v in (task_map_pre.get("folder_alias") or {}).items()
                        }
                        from_phase0: set[str] = set()
                        for p in parts:
                            fam = alias_to_family.get(p.alias.lower())
                            if fam:
                                from_phase0.add(fam)
                            # also try folder suffix llmN_alias → alias
                            m = re.match(r"llm\d+_(.+)$", p.folder_suffix, re.I)
                            if m:
                                fam2 = alias_to_family.get(m.group(1).lower())
                                if fam2:
                                    from_phase0.add(fam2)
                        if from_phase0:
                            allowed_families = from_phase0
                            participant_source = "phase0_participants"

                quality_rows = filter_quality_rows_to_families(
                    quality_rows, allowed_families
                )

            if quality_rows:
                synthetic = {
                    "fv": quality_pack.get("fv")
                    or (shortlist_data or {}).get("fv"),
                    "applications": {
                        app_info["application_key"]: quality_rows,
                    },
                }
                candidates = shortlist_task_candidates(
                    synthetic, str(app_info["application_key"])
                )
                leader_meta.update(
                    {
                        "applied": True,
                        "calculation_path": quality_pack.get("path"),
                        "quality_llm_count": quality_pack.get("llm_count"),
                        "candidate_count_after_filter": len(quality_rows),
                        "participant_source": participant_source,
                        "allowed_families": sorted(allowed_families or []),
                        "leader_llm_code": quality_rows[0][0] if quality_rows else None,
                        "leader_quality": quality_rows[0][1] if quality_rows else None,
                    }
                )
            else:
                leader_meta["error"] = (
                    "quality_ranking_empty_after_filter"
                    if leader_cfg["among_participants_only"]
                    else "quality_ranking_empty"
                )
                leader_meta["calculation_path"] = str(calc_path)
        except (OSError, ValueError, KeyError, TypeError) as exc:
            leader_meta["error"] = str(exc)
            leader_meta["calculation_path"] = str(calc_path)
            # Keep capability_weighted shortlist candidates as fallback

    overrides = load_yaml_overrides(review_root)
    fallback = load_fallback_models_yaml()
    fallback_slots = fallback.get("slots") or {}
    override_slots = overrides.get("slots") or {}

    task_map = load_task_model_map()
    enforce_unique_provider = unique_provider_required()

    # Size from unique-provider shortlist scores (overrides do not change the curve)
    sizing_scores: list[float] = []
    for row in candidates.get("selected") or []:
        score = row.get("score")
        if score is None:
            break
        try:
            sizing_scores.append(float(score))
        except (TypeError, ValueError):
            break

    sizing = choose_roster_size(
        sizing_scores,
        min_slots=sizing_cfg["min_slots"],
        max_slots=sizing_cfg["max_slots"],
        tau_vs_leader=sizing_cfg["tau_vs_leader"],
        rho_vs_prev=sizing_cfg["rho_vs_prev"],
    )

    if explicit_slot_count:
        slot_count = int(slot_count)  # type: ignore[arg-type]
        sizing = {
            **sizing,
            "applied": False,
            "override_slot_count": slot_count,
            "note": "explicit --slots / slot_count bypasses auto sizing for seat count",
        }
    else:
        slot_count = int(sizing["chosen_k"])
        sizing = {**sizing, "applied": True}

    # When leader is quality-among-participants, seat count should match that set
    # (do not auto-expand beyond the filtered participant families).
    if (
        leader_meta.get("applied")
        and leader_cfg["among_participants_only"]
        and not explicit_slot_count
    ):
        n_leader_cands = len(candidates.get("selected") or [])
        if n_leader_cands > 0:
            slot_count = n_leader_cands
            sizing = {
                **sizing,
                "applied": True,
                "chosen_k": n_leader_cands,
                "stop_reason": "leader_among_participants",
                "note": "phase5 seat count = quality-ranked participant families",
            }

    # Phase 5 leader apps: prefer highest slot (llmN) for the top pick
    # (phase0 usually marks llmN as leader). Proposer phases fill llm1..llmN.
    app_phase = str(app_info.get("application_phase") or "")
    slot_indices = (
        list(range(slot_count, 0, -1))
        if app_phase == "5"
        else list(range(1, slot_count + 1))
    )

    claimed_families: set[str] = set()
    claimed_providers: set[str] = set()
    override_rejected: dict[str, dict[str, Any]] = {}
    for i in slot_indices:
        slot = f"llm{i}"
        if slot not in override_slots:
            continue
        slug = override_slots[slot]
        fam = task_family_of(slug, task_map)
        prov = provider_of_family(fam, task_map)
        if fam in claimed_families:
            override_rejected[slot] = {
                "reason": f"duplicate_family:{fam}",
                "family": fam,
                "provider": prov,
                "model_slug": slug,
            }
            continue
        if enforce_unique_provider and prov in claimed_providers:
            override_rejected[slot] = {
                "reason": f"duplicate_provider:{prov}",
                "family": fam,
                "provider": prov,
                "model_slug": slug,
            }
            continue
        claimed_families.add(fam)
        claimed_providers.add(prov)

    shortlist_queue = [
        row
        for row in candidates.get("selected") or []
        if row["family"] not in claimed_families
        and (
            not enforce_unique_provider
            or provider_of_family(row["family"], task_map) not in claimed_providers
        )
    ]

    fallback_ordered: list[str] = []
    for i in range(1, 20):
        slug = fallback_slots.get(f"llm{i}")
        if slug:
            fallback_ordered.append(slug)

    slots_out: dict[str, dict[str, Any]] = {}
    shortlist_idx = 0
    fallback_idx = 0
    used_families: set[str] = set(claimed_families)
    used_providers: set[str] = set(claimed_providers)
    provider_collisions: list[dict[str, Any]] = []
    source_label = (
        "quality_among_participants"
        if leader_meta.get("applied") and leader_cfg["among_participants_only"]
        else "quality_ranking"
        if leader_meta.get("applied")
        else "shortlist"
    )

    for i in slot_indices:
        slot = f"llm{i}"
        if slot in override_rejected:
            rej = override_rejected[slot]
            provider_collisions.append({"slot": slot, **rej})
            slots_out[slot] = {
                "slot": slot,
                "model_slug": None,
                "resolved": False,
                "source": "yaml_override_rejected",
                "family": rej.get("family"),
                "provider": rej.get("provider"),
                "rejected_model_slug": rej.get("model_slug"),
                "reason": rej.get("reason"),
            }
            continue

        if slot in override_slots:
            slug = override_slots[slot]
            fam = task_family_of(slug, task_map)
            prov = provider_of_family(fam, task_map)
            used_families.add(fam)
            used_providers.add(prov)
            slots_out[slot] = {
                "slot": slot,
                "model_slug": slug,
                "resolved": True,
                "source": "yaml_override",
                "family": fam,
                "provider": prov,
                "folder_alias": folder_alias_for_family(fam, task_map),
                "suggested_folder_suffix": suggested_folder_suffix(slot, fam, task_map),
            }
            continue

        picked = None
        while shortlist_idx < len(shortlist_queue):
            cand = shortlist_queue[shortlist_idx]
            shortlist_idx += 1
            cand_prov = cand.get("provider") or provider_of_family(
                cand["family"], task_map
            )
            if cand["family"] in used_families:
                continue
            if enforce_unique_provider and cand_prov in used_providers:
                continue
            picked = cand
            break

        if picked:
            fam = picked["family"]
            prov = picked.get("provider") or provider_of_family(fam, task_map)
            used_families.add(fam)
            used_providers.add(prov)
            slots_out[slot] = {
                "slot": slot,
                "model_slug": picked["task_slug"],
                "resolved": True,
                "source": source_label,
                "family": fam,
                "provider": prov,
                "llm_code": picked["llm_code"],
                "shortlist_rank": picked["rank"],
                "score": picked["score"],
                "application_key": app_info.get("application_key"),
                "folder_alias": folder_alias_for_family(fam, task_map),
                "suggested_folder_suffix": suggested_folder_suffix(slot, fam, task_map),
            }
            continue

        picked_fb = None
        allow = set(task_map.get("task_allow_list") or [])
        while fallback_idx < len(fallback_ordered):
            fb_raw = fallback_ordered[fallback_idx]
            fallback_idx += 1
            # models.yaml may hold a Task slug or an llm_code (non-Task Cursor models)
            fb_slug = map_llm_code_to_task(fb_raw, task_map) or (
                fb_raw if fb_raw in allow else None
            )
            if not fb_slug:
                continue
            fam = task_family_of(fb_slug, task_map)
            prov = provider_of_family(fam, task_map)
            if fam in used_families:
                continue
            if enforce_unique_provider and prov in used_providers:
                continue
            picked_fb = fb_slug
            used_families.add(fam)
            used_providers.add(prov)
            break

        if picked_fb:
            fam = task_family_of(picked_fb, task_map)
            prov = provider_of_family(fam, task_map)
            slots_out[slot] = {
                "slot": slot,
                "model_slug": picked_fb,
                "resolved": True,
                "source": "fallback_models_yaml",
                "family": fam,
                "provider": prov,
                "folder_alias": folder_alias_for_family(fam, task_map),
                "suggested_folder_suffix": suggested_folder_suffix(slot, fam, task_map),
            }
        else:
            slots_out[slot] = {
                "slot": slot,
                "model_slug": None,
                "resolved": False,
                "source": "unresolved",
                "reason": (
                    "no_unique_provider_candidate"
                    if enforce_unique_provider
                    else "no_candidate"
                ),
            }

    return {
        "shortlist_path": str(path),
        "shortlist_error": shortlist_error,
        "fv": candidates.get("fv"),
        "domain_code": domain_code,
        "phase": phase,
        "application": app_info,
        "shortlist_selected": candidates.get("selected"),
        "shortlist_skipped": candidates.get("skipped"),
        "yaml_override_sources": overrides.get("sources", []),
        "slots": slots_out,
        "slot_count": slot_count,
        "roster_sizing": sizing,
        "unique_provider": enforce_unique_provider,
        "used_providers": sorted(used_providers),
        "provider_collisions": provider_collisions,
        "leader_selection": leader_meta if app_phase == "5" else None,
    }


def resolve_model_for_slot(
    slot: str,
    review_root: Path | None = None,
    *,
    llms_root: Path | None = None,
    phase: int | None = None,
    domain_code: str | None = None,
    project_code: str | None = None,
    shortlist_path: Path | None = None,
    slot_count: int | None = None,
) -> dict[str, Any]:
    slot_key = slot.lower()
    llms_root = Path(llms_root) if llms_root else DEFAULT_LLMS_ROOT
    if review_root is not None:
        review_root = Path(review_root)
        domain_code = domain_code or infer_domain_code(review_root)
    domain_code = domain_code or ""
    if phase is None:
        if review_root is not None:
            phase = _current_phase_only(review_root, llms_root)
        else:
            phase = 2

    roster = build_dispatch_roster(
        llms_root=llms_root,
        review_root=review_root,
        domain_code=domain_code,
        phase=phase,
        slot_count=slot_count,
        project_code=project_code,
        shortlist_path=shortlist_path,
    )
    entry = (roster.get("slots") or {}).get(slot_key) or {
        "slot": slot_key,
        "model_slug": None,
        "resolved": False,
        "source": "unresolved",
    }
    return {
        **entry,
        "config_sources": roster.get("yaml_override_sources", []),
        "shortlist_path": roster.get("shortlist_path"),
        "application_key": (roster.get("application") or {}).get("application_key"),
        "fv": roster.get("fv"),
        "phase": phase,
        "domain_code": domain_code,
    }


def resolve_participant_models(
    participants: list[Participant],
    review_root: Path | None = None,
    *,
    llms_root: Path | None = None,
    phase: int | None = None,
    domain_code: str | None = None,
    project_code: str | None = None,
    shortlist_path: Path | None = None,
) -> list[dict[str, Any]]:
    llms_root = Path(llms_root) if llms_root else DEFAULT_LLMS_ROOT
    if review_root is not None:
        review_root = Path(review_root)
        domain_code = domain_code or infer_domain_code(review_root)
    domain_code = domain_code or ""
    if phase is None:
        if review_root is not None:
            phase = _current_phase_only(review_root, llms_root)
        else:
            phase = 2

    roster = build_dispatch_roster(
        llms_root=llms_root,
        review_root=review_root,
        domain_code=domain_code,
        phase=phase,
        slot_count=len(participants) if participants else None,
        project_code=project_code,
        shortlist_path=shortlist_path,
    )
    rows = []
    for p in participants:
        entry = (roster.get("slots") or {}).get(p.slot) or {
            "slot": p.slot,
            "model_slug": None,
            "resolved": False,
            "source": "unresolved",
        }
        rows.append({**asdict(p), **entry})
    return rows


def _read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8") if path.is_file() else ""


def infer_domain_code(review_root: Path) -> str:
    """Infer domain folder code from review root (round folder or domain folder)."""
    name = review_root.name
    # Timestamped round → domain is parent folder
    if ROUND_ID_RE.match(name):
        parent = review_root.parent.name
        match = re.match(r"^(d\d+[a-z]?_[a-z0-9_]+)", parent)
        if match:
            return match.group(1)
    match = re.match(r"^(d\d+[a-z]?_[a-z0-9_]+)", name)
    if match:
        return match.group(1)
    setup = _read_text(review_root / "phase0_setup.md")
    for pattern in (
        r"domains/(d\d+[a-z]?_[a-z0-9_]+)/",
        r"`(d\d+[a-z]?_[a-z0-9_]+)`",
        r"\(`(d\d+[a-z]?_[a-z0-9_]+)`\)",
    ):
        m = re.search(pattern, setup, re.IGNORECASE)
        if m:
            return m.group(1)
    return name if name.startswith("d") else ""


def utc_now_round_id() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def is_round_id(name: str) -> bool:
    return bool(ROUND_ID_RE.match(name))


def domain_root_for(review_root: Path) -> Path:
    """Domain folder containing the round (or the path itself if legacy flat)."""
    if is_round_id(review_root.name):
        return review_root.parent
    return review_root


def read_current_json(domain_root: Path) -> dict[str, Any] | None:
    path = domain_root / "current.json"
    if not path.is_file():
        return None
    try:
        data = _load_json(path)
    except (json.JSONDecodeError, OSError):
        return None
    return data if isinstance(data, dict) else None


def write_current_json(domain_root: Path, round_id: str, status: str) -> Path:
    domain_root.mkdir(parents=True, exist_ok=True)
    path = domain_root / "current.json"
    path.write_text(
        json.dumps({"round_id": round_id, "status": status}, indent=2) + "\n",
        encoding="utf-8",
    )
    return path


def resolve_review_root(
    *,
    review_root: Path | None = None,
    domain_root: Path | None = None,
) -> Path:
    """Prefer explicit --review-root; else domain_root/current.json round folder."""
    if review_root is not None:
        return review_root
    if domain_root is None:
        raise ValueError("review_root or domain_root required")
    current = read_current_json(domain_root)
    if current and current.get("round_id"):
        candidate = domain_root / str(current["round_id"])
        if candidate.is_dir():
            return candidate
    # Legacy flat: phases live on domain_root
    if (domain_root / "phase0_setup.md").is_file():
        return domain_root
    raise FileNotFoundError(
        f"No current.json round and no legacy phase0 under {domain_root}"
    )


def catalog_index(domain_code: str) -> int:
    try:
        return DOMAIN_CATALOG_ORDER.index(domain_code)
    except ValueError:
        # Unknown / fallback domains sort after formalized ones
        return len(DOMAIN_CATALOG_ORDER) + 100


def list_peer_review_domains(peer_review_root: Path) -> list[str]:
    """Domain folder names under peer_review_root that look like dNN_*."""
    if not peer_review_root.is_dir():
        return []
    found: list[str] = []
    for child in peer_review_root.iterdir():
        if child.is_dir() and re.match(r"^d\d+[a-z]?_[a-z0-9_]+$", child.name):
            found.append(child.name)
    found.sort(key=catalog_index)
    return found


def upstream_domain_codes(domain_code: str) -> list[str]:
    idx = catalog_index(domain_code)
    if domain_code not in DOMAIN_CATALOG_ORDER:
        return list(DOMAIN_CATALOG_ORDER)
    return DOMAIN_CATALOG_ORDER[:idx]


def accepted_round_id(domain_dir: Path) -> str | None:
    """Best accepted (or current) round id for a domain folder."""
    current = read_current_json(domain_dir)
    if current and current.get("round_id"):
        return str(current["round_id"])
    # Legacy flat
    if (domain_dir / "phase0_setup.md").is_file():
        return None  # caller treats as legacy path
    # Newest timestamped round folder if any
    rounds = sorted(
        [p.name for p in domain_dir.iterdir() if p.is_dir() and is_round_id(p.name)],
        reverse=True,
    )
    return rounds[0] if rounds else None


def resolve_upstream_pins(
    peer_review_root: Path,
    domain_code: str,
) -> dict[str, str]:
    """Map earlier catalog domains present in consumer → pinned round_id (or 'legacy')."""
    pins: dict[str, str] = {}
    for up in upstream_domain_codes(domain_code):
        domain_dir = peer_review_root / up
        if not domain_dir.is_dir():
            continue
        rid = accepted_round_id(domain_dir)
        pins[up] = rid if rid else "legacy"
    return pins


def upstream_artifact_paths(
    peer_review_root: Path,
    pins: dict[str, str],
) -> list[str]:
    """Concrete paths for phase5 / acceptance under pinned upstream rounds."""
    paths: list[str] = []
    for domain, rid in pins.items():
        domain_dir = peer_review_root / domain
        root = domain_dir if rid == "legacy" else domain_dir / rid
        if not root.is_dir():
            continue
        # Prefer phase5 unified or acceptance
        for child in sorted(root.iterdir()):
            if child.is_dir() and (
                child.name.startswith("phase5_unified_answer_")
                or child.name.startswith("phase5_acceptance_check_")
            ):
                overview = child / "overview.md"
                signoff = child / "signoff.md"
                if overview.is_file():
                    paths.append(str(overview.resolve()))
                elif signoff.is_file():
                    paths.append(str(signoff.resolve()))
        setup = root / "phase0_setup.md"
        if setup.is_file():
            paths.append(str(setup.resolve()))
    return paths


def write_round_md(
    round_dir: Path,
    *,
    kind: str,
    round_id: str,
    baseline_round_id: str | None,
    change_pack_ref: str | None,
    summary: str,
    upstream_pins: dict[str, str],
) -> Path:
    pins_yaml = "\n".join(f"  {k}: {v}" for k, v in upstream_pins.items()) or "  {}"
    body = (
        "---\n"
        f"kind: {kind}\n"
        f"round_id: {round_id}\n"
        f"baseline_round_id: {baseline_round_id or 'null'}\n"
        f"change_pack_ref: {change_pack_ref or 'null'}\n"
        f"summary: |\n  {summary}\n"
        f"upstream_pins:\n{pins_yaml}\n"
        "---\n\n"
        f"# Round `{round_id}`\n\n"
        f"**Kind:** {kind}\n\n"
        f"{summary}\n"
    )
    path = round_dir / "round.md"
    path.write_text(body, encoding="utf-8")
    return path


OPEN_ROUND_STATUSES = ("in_progress", "awaiting_human")


def open_rounds_with_other_id(
    peer_review_root: Path,
    domain_root: Path,
    rid: str,
) -> dict[str, str]:
    """Domains (other than domain_root) whose open round uses a different round id.

    One review uses one round id across all its domains (process/standards/git_flow.md).
    An open round with another id means two reviews would be mixed in the same tree.
    """
    conflicts: dict[str, str] = {}
    for name in list_peer_review_domains(peer_review_root):
        if name == domain_root.name:
            continue
        current = read_current_json(peer_review_root / name)
        if not current:
            continue
        other = str(current.get("round_id") or "")
        if other and other != rid and current.get("status") in OPEN_ROUND_STATUSES:
            conflicts[name] = other
    return conflicts


def init_round(
    domain_root: Path,
    *,
    kind: str = "initial",
    peer_review_root: Path | None = None,
    baseline_round_id: str | None = None,
    change_pack: Path | None = None,
    summary: str | None = None,
    round_id: str | None = None,
    status: str = "in_progress",
) -> dict[str, Any]:
    """Create a round folder under domain_root.

    Pass the review's shared round id via round_id. Without it, a new timestamp is
    generated, which is only correct for the first domain of a review.
    """
    peer_review_root = peer_review_root or domain_root.parent
    domain_code = infer_domain_code(domain_root)
    if not domain_code:
        domain_code = domain_root.name
    rid = round_id or utc_now_round_id()
    conflicts = open_rounds_with_other_id(peer_review_root, domain_root, rid)
    if conflicts:
        detail = ", ".join(f"{d}={r}" for d, r in sorted(conflicts.items()))
        raise ValueError(
            f"Open round(s) with a different round id: {detail}. "
            f"Use round id {rid} only for the same review; close or accept the other review first."
        )
    round_dir = domain_root / rid
    if round_dir.exists():
        raise FileExistsError(f"Round already exists: {round_dir}")
    round_dir.mkdir(parents=True)

    if kind == "revision":
        if not baseline_round_id:
            current = read_current_json(domain_root)
            if current and current.get("round_id"):
                baseline_round_id = str(current["round_id"])
            elif (domain_root / "phase0_setup.md").is_file():
                baseline_round_id = "legacy"
        if baseline_round_id and baseline_round_id != "legacy":
            baseline_dir = domain_root / baseline_round_id
            src = baseline_dir / "phase0_setup.md"
            if src.is_file():
                shutil.copy2(src, round_dir / "phase0_setup.md")
        elif baseline_round_id == "legacy":
            src = domain_root / "phase0_setup.md"
            if src.is_file():
                shutil.copy2(src, round_dir / "phase0_setup.md")

    pins = resolve_upstream_pins(peer_review_root, domain_code)
    summary_text = summary or (
        f"Initial round for {domain_code}"
        if kind == "initial"
        else f"Revision round for {domain_code}"
    )
    change_ref = str(change_pack.resolve()) if change_pack else None
    write_round_md(
        round_dir,
        kind=kind,
        round_id=rid,
        baseline_round_id=baseline_round_id,
        change_pack_ref=change_ref,
        summary=summary_text,
        upstream_pins=pins,
    )
    write_current_json(domain_root, rid, status)
    return {
        "domain_code": domain_code,
        "domain_root": str(domain_root.resolve()),
        "peer_review_root": str(peer_review_root.resolve()),
        "round_id": rid,
        "review_root": str(round_dir.resolve()),
        "kind": kind,
        "baseline_round_id": baseline_round_id,
        "change_pack_ref": change_ref,
        "upstream_pins": pins,
        "upstream_artifact_paths": upstream_artifact_paths(peer_review_root, pins),
        "current_status": status,
    }


def domain_standards_root(llms_root: Path, domain_code: str) -> Path:
    """Prefer process/domains/{code}; fall back to legacy standards/domains/{code}."""
    if not domain_code:
        return llms_root / "domains" / "_missing"
    primary = llms_root / "domains" / domain_code
    if primary.is_dir():
        return primary
    legacy = llms_root / "standards" / "domains" / domain_code
    if legacy.is_dir():
        return legacy
    return primary


def resolve_phase_prompt_paths(
    llms_root: Path, domain_code: str, phase: int
) -> dict[str, str | None]:
    generic_name = PHASE_PROMPT_FILES.get(phase)
    generic = llms_root / "phases" / generic_name if generic_name else None
    domain_phase = (
        domain_standards_root(llms_root, domain_code) / "phases" / generic_name
        if generic_name and domain_code
        else None
    )
    return {
        "generic": str(generic) if generic and generic.is_file() else None,
        "domain_override": (
            str(domain_phase) if domain_phase and domain_phase.is_file() else None
        ),
        "effective": (
            str(domain_phase)
            if domain_phase and domain_phase.is_file()
            else str(generic)
            if generic and generic.is_file()
            else None
        ),
    }


def parse_participants(review_root: Path) -> list[Participant]:
    setup_path = review_root / "phase0_setup.md"
    text = _read_text(setup_path)
    participants: list[Participant] = []

    # Markdown table: | llm1 | composer | `llm1_composer` |
    table_rows = re.findall(
        r"^\|\s*(llm\d+)\s*\|\s*([^|`]+?)\s*\|\s*`?(llm\d+_[a-z0-9_]+)`?\s*\|",
        text,
        re.MULTILINE | re.IGNORECASE,
    )
    for slot, alias, suffix in table_rows:
        slot_l = slot.lower()
        if slot_l.startswith("llm") and suffix.lower().startswith("llm"):
            participants.append(
                Participant(
                    slot=slot_l,
                    alias=alias.strip(),
                    folder_suffix=suffix.strip(),
                )
            )

    if participants:
        # Deduplicate by slot, preserve order
        seen: set[str] = set()
        unique: list[Participant] = []
        for p in participants:
            if p.slot not in seen:
                seen.add(p.slot)
                unique.append(p)
        return sorted(unique, key=lambda p: p.slot)

    # Fallback: scan phase1_questions folders
    phase1 = review_root / "phase1_questions"
    if phase1.is_dir():
        for d in sorted(phase1.glob("llm*_*")):
            if d.is_dir():
                m = re.match(r"(llm\d+)_(.+)", d.name, re.I)
                if m:
                    participants.append(
                        Participant(
                            slot=m.group(1).lower(),
                            alias=m.group(2),
                            folder_suffix=d.name,
                        )
                    )
    return participants


def question_file_complete(path: Path) -> bool:
    name = path.name.lower()
    if name == "q00_no_valid_questions.md":
        return True
    if not name.startswith("q") or not name.endswith(".md"):
        return True  # ignore non-question files

    text = _read_text(path)

    status_match = re.search(r"\*\*Status:\*\*\s*(.+)", text, re.I)
    if status_match:
        status = status_match.group(1).lower()
        if any(k in status for k in ("answered", "closed", "deferred", "no valid")):
            return True

    # ## User answer section with content.
    # Avoid \s* after the heading title (it eats blank lines under DOTALL-ish
    # backtracking) and avoid \n+ before the capture (it can swallow the newline
    # before the next ## heading). Match the next H2 with a lookahead.
    # Next H2 only: ## not followed by # (so ### subsections stay inside the answer).
    answer_match = re.search(
        r"##[ \t]*User answer[ \t]*\r?\n(.*?)(?=\r?\n##(?!#)|\Z)",
        text,
        re.I | re.S,
    )
    if answer_match:
        body = answer_match.group(1).strip()
        body = re.sub(r"^>\s*", "", body, flags=re.M).strip()
        # Strip markdown emphasis / italics wrappers around placeholders.
        normalized = re.sub(r"^[\*_`~\s]+|[\*_`~\s]+$", "", body).strip().lower()
        if body and normalized not in (
            "",
            "tbd",
            "pending",
            "n/a",
            "todo",
            "none",
            "(pending)",
            "[pending]",
        ):
            return True

    return False


def phase1_slot_status(review_root: Path, folder_suffix: str) -> dict[str, Any]:
    folder = review_root / "phase1_questions" / folder_suffix
    if not folder.is_dir():
        return {
            "slot": folder_suffix,
            "state": "not_started",
            "pending_files": [],
            "question_files": [],
        }

    questions = sorted(folder.glob("q*.md"))
    if not questions:
        return {
            "slot": folder_suffix,
            "state": "in_progress",
            "pending_files": [],
            "question_files": [],
            "note": "folder exists but no q*.md yet",
        }

    pending = [str(q) for q in questions if not question_file_complete(q)]
    complete = all(not p for p in pending)

    if any(q.name.lower() == "q00_no_valid_questions.md" for q in questions):
        state = "complete"
        pending = []
    elif complete:
        state = "complete"
    else:
        state = "pending_user"

    return {
        "slot": folder_suffix,
        "state": state,
        "pending_files": pending,
        "question_files": [str(q) for q in questions],
    }


def _has_overview(folder: Path) -> bool:
    return (folder / "overview.md").is_file()


def _has_internal_revision_log(folder: Path) -> bool:
    return (
        folder / "_internal" / "post_critique_revision_log.md"
    ).is_file()


def _has_internal_consolidation_matrix(folder: Path) -> bool:
    return (folder / "_internal" / "consolidation_matrix.md").is_file()


def _phase2_complete(review_root: Path, participants: list[Participant]) -> bool:
    base = review_root / "phase2_initial_proposals"
    return all(_has_overview(base / p.folder_suffix) for p in participants)


def _phase4_complete(review_root: Path, participants: list[Participant]) -> bool:
    base = review_root / "phase4_final_proposals"
    if not participants:
        return False
    for p in participants:
        folder = base / p.folder_suffix
        if not _has_overview(folder):
            return False
        if len(participants) > 1 and not _has_internal_revision_log(folder):
            return False
    return True


def _phase4_missing_internal(
    review_root: Path, participants: list[Participant]
) -> list[str]:
    if len(participants) <= 1:
        return []
    base = review_root / "phase4_final_proposals"
    missing: list[str] = []
    for p in participants:
        folder = base / p.folder_suffix
        if _has_overview(folder) and not _has_internal_revision_log(folder):
            missing.append(
                str(folder / "_internal" / "post_critique_revision_log.md")
            )
    return missing


def _expected_critique_files(participants: list[Participant]) -> list[str]:
    names = [p.folder_suffix for p in participants]
    # llm1_composer -> llm1
    slots = []
    for n in names:
        m = re.match(r"(llm\d+)", n, re.I)
        slots.append(m.group(1).lower() if m else n)

    files: list[str] = []
    for i, si in enumerate(slots):
        for j, sj in enumerate(slots):
            if i != j:
                files.append(f"{si}_vs_{sj}.md")
    return sorted(files)


def _phase3_complete(review_root: Path, participants: list[Participant]) -> bool:
    base = review_root / "phase3_crossed_critiques"
    if not base.is_dir():
        return False
    for fname in _expected_critique_files(participants):
        if not (base / fname).is_file():
            return False
    return True


def _find_phase5_folder(review_root: Path) -> Path | None:
    matches = sorted(review_root.glob("phase5_unified_answer_*"))
    for m in matches:
        if m.is_dir():
            return m
    return None


def _phase5_complete(review_root: Path, participants: list[Participant]) -> bool:
    folder = _find_phase5_folder(review_root)
    if folder is None or not (folder / "overview.md").is_file():
        return False
    if len(participants) > 1 and not _has_internal_consolidation_matrix(folder):
        return False
    return True


def _phase5_missing_internal(
    review_root: Path, participants: list[Participant]
) -> str | None:
    if len(participants) <= 1:
        return None
    folder = _find_phase5_folder(review_root)
    if folder is None:
        return None
    if (folder / "overview.md").is_file() and not _has_internal_consolidation_matrix(
        folder
    ):
        return str(folder / "_internal" / "consolidation_matrix.md")
    return None


def _phase1_all_complete(review_root: Path, participants: list[Participant]) -> bool:
    return all(
        phase1_slot_status(review_root, p.folder_suffix)["state"] == "complete"
        for p in participants
    )


def _next_phase1_slot(
    review_root: Path, participants: list[Participant]
) -> Participant | None:
    for p in participants:
        st = phase1_slot_status(review_root, p.folder_suffix)["state"]
        if st in ("not_started", "in_progress", "pending_user"):
            return p
    return None


def infer_status(
    review_root: Path,
    llms_root: Path,
    *,
    resolve_models: bool = True,
    shortlist_path: Path | None = None,
    project_code: str | None = None,
) -> dict[str, Any]:
    review_root = review_root.resolve()
    domain_code = infer_domain_code(review_root)
    participants = parse_participants(review_root)
    phase0_ok = (review_root / "phase0_setup.md").is_file()

    phase1_slots = {
        p.folder_suffix: phase1_slot_status(review_root, p.folder_suffix)
        for p in participants
    }
    phase1_done = _phase1_all_complete(review_root, participants) if participants else False
    phase2_done = _phase2_complete(review_root, participants) if participants else False
    phase3_done = _phase3_complete(review_root, participants) if participants else False
    phase4_done = _phase4_complete(review_root, participants) if participants else False
    phase5_done = (
        _phase5_complete(review_root, participants) if participants else False
    )
    phase4_missing_internal = _phase4_missing_internal(review_root, participants)
    phase5_missing_internal = _phase5_missing_internal(review_root, participants)

    if not phase0_ok:
        current_phase = 0
        next_action = "Complete or validate phase0_setup.md"
    elif not phase1_done:
        current_phase = 1
        nxt = _next_phase1_slot(review_root, participants)
        if nxt is None:
            next_action = "Phase 1 — dispatch first participant"
        else:
            st = phase1_slots[nxt.folder_suffix]["state"]
            if st == "pending_user":
                pending = phase1_slots[nxt.folder_suffix]["pending_files"]
                next_action = (
                    f"Phase 1 — PAUSE: user answers needed for {nxt.folder_suffix} "
                    f"({len(pending)} file(s))"
                )
            elif st == "not_started":
                next_action = (
                    f"Phase 1 — dispatch subagent for {nxt.slot} ({nxt.folder_suffix})"
                )
            else:
                next_action = (
                    f"Phase 1 — continue {nxt.folder_suffix} (state={st})"
                )
    elif not phase2_done:
        current_phase = 2
        missing = [
            p.folder_suffix
            for p in participants
            if not _has_overview(
                review_root / "phase2_initial_proposals" / p.folder_suffix
            )
        ]
        next_action = f"Phase 2 — parallel subagents; missing: {', '.join(missing) or 'none'}"
    elif not phase3_done:
        current_phase = 3
        expected = _expected_critique_files(participants)
        base = review_root / "phase3_crossed_critiques"
        missing = [f for f in expected if not (base / f).is_file()]
        next_action = f"Phase 3 — parallel critics; missing {len(missing)}/{len(expected)} files"
    elif not phase4_done:
        current_phase = 4
        missing = [
            p.folder_suffix
            for p in participants
            if not _has_overview(
                review_root / "phase4_final_proposals" / p.folder_suffix
            )
        ]
        if missing:
            next_action = (
                f"Phase 4 — parallel subagents; missing overview: {', '.join(missing)}"
            )
        elif phase4_missing_internal:
            next_action = (
                "Phase 4 — add internal revision logs: "
                f"{len(phase4_missing_internal)} file(s)"
            )
        else:
            next_action = "Phase 4 — parallel subagents; missing: none"
    elif not phase5_done:
        current_phase = 5
        if phase5_missing_internal:
            next_action = (
                "Phase 5 — leader must write client overview.md and "
                "_internal/consolidation_matrix.md"
            )
        else:
            next_action = "Phase 5 — dispatch leader subagent"
    else:
        current_phase = 5
        next_action = "Complete — all phases done"

    payload: dict[str, Any] = {
        "review_root": str(review_root),
        "llms_peer_review_root": str(llms_root.resolve()),
        "shortlist_path": str(shortlist_path or default_shortlist_path(llms_root)),
        "domain_code": domain_code,
        "domain_standards_root": str(domain_standards_root(llms_root, domain_code)),
        "phase0_setup_ok": phase0_ok,
        "participants": [asdict(p) for p in participants],
        "current_phase": current_phase,
        "phases": {
            "1": {"complete": phase1_done, "slots": phase1_slots},
            "2": {"complete": phase2_done},
            "3": {
                "complete": phase3_done,
                "expected_critique_count": len(_expected_critique_files(participants)),
            },
            "4": {
                "complete": phase4_done,
                "missing_internal_revision_logs": phase4_missing_internal,
            },
            "5": {
                "complete": phase5_done,
                "folder": str(_find_phase5_folder(review_root) or ""),
                "missing_internal_consolidation_matrix": phase5_missing_internal,
            },
        },
        "next_action": next_action,
    }

    if resolve_models:
        roster = build_dispatch_roster(
            llms_root=llms_root,
            review_root=review_root,
            domain_code=domain_code,
            phase=current_phase if current_phase else 2,
            slot_count=len(participants) if participants else None,
            project_code=project_code,
            shortlist_path=shortlist_path,
        )
        participant_models = []
        for p in participants:
            entry = (roster.get("slots") or {}).get(p.slot) or {
                "slot": p.slot,
                "model_slug": None,
                "resolved": False,
                "source": "unresolved",
            }
            participant_models.append({**asdict(p), **entry})
        mismatches = detect_participant_model_mismatches(
            participants, roster.get("slots") or {}
        )
        payload["participant_models"] = participant_models
        payload["dispatch_roster"] = roster.get("slots")
        payload["alias_mismatches"] = mismatches
        payload["unique_provider"] = roster.get("unique_provider")
        payload["used_providers"] = roster.get("used_providers")
        payload["provider_collisions"] = roster.get("provider_collisions") or []
        if mismatches:
            # Surface before next_action so parent agents cannot miss it
            names = ", ".join(
                f"{m['slot']}({m['phase0_folder_suffix']}≠{m['expected_folder_suffix']})"
                for m in mismatches
            )
            payload["next_action"] = (
                f"ALIAS MISMATCH — update phase0 folders before dispatching: {names}. "
                f"Then: {next_action}"
            )
        elif payload["provider_collisions"]:
            names = ", ".join(
                f"{c['slot']}({c.get('reason')})" for c in payload["provider_collisions"]
            )
            payload["next_action"] = (
                f"PROVIDER COLLISION — fix YAML overrides (one vendor per review): "
                f"{names}. Then: {next_action}"
            )
        payload["shortlist_application"] = roster.get("application")
        payload["shortlist_fv"] = roster.get("fv")
        payload["shortlist_error"] = roster.get("shortlist_error")
        payload["roster_sizing"] = roster.get("roster_sizing")
        payload["models_config_sources"] = roster.get("yaml_override_sources", [])

    return payload


def _current_phase_only(review_root: Path, llms_root: Path) -> int:
    return int(
        infer_status(review_root, llms_root, resolve_models=False).get("current_phase")
        or 2
    )


def cmd_status(args: argparse.Namespace) -> int:
    shortlist = Path(args.shortlist) if getattr(args, "shortlist", None) else None
    review_root = _effective_review_root(args)
    data = infer_status(
        review_root,
        Path(args.llms_root),
        shortlist_path=shortlist,
        project_code=getattr(args, "project", None),
    )
    domain_root = domain_root_for(review_root)
    current = read_current_json(domain_root)
    data["review_root"] = str(review_root.resolve())
    data["domain_root"] = str(domain_root.resolve())
    data["current"] = current
    if (review_root / "round.md").is_file():
        data["round_md"] = str((review_root / "round.md").resolve())
    print(json.dumps(data, indent=2))
    return 0


def _effective_review_root(args: argparse.Namespace) -> Path:
    review = Path(args.review_root) if getattr(args, "review_root", None) else None
    domain = Path(args.domain_root) if getattr(args, "domain_root", None) else None
    if review is None and domain is None:
        raise SystemExit("error: --review-root or --domain-root is required")
    return resolve_review_root(review_root=review, domain_root=domain)


def cmd_init_round(args: argparse.Namespace) -> int:
    domain_root = Path(args.domain_root)
    peer = Path(args.peer_review_root) if args.peer_review_root else domain_root.parent
    change = Path(args.change_pack) if args.change_pack else None
    try:
        result = init_round(
            domain_root,
            kind=args.kind,
            peer_review_root=peer,
            baseline_round_id=args.baseline,
            change_pack=change,
            summary=args.summary,
            round_id=args.round_id,
            status=args.status,
        )
    except (FileExistsError, ValueError) as exc:
        print(json.dumps({"error": str(exc)}, indent=2), file=sys.stderr)
        return 1
    print(json.dumps(result, indent=2))
    return 0


def cmd_resolve_review_root(args: argparse.Namespace) -> int:
    try:
        root = _effective_review_root(args)
    except (FileNotFoundError, ValueError) as exc:
        print(json.dumps({"error": str(exc)}, indent=2), file=sys.stderr)
        return 1
    domain_root = domain_root_for(root)
    print(
        json.dumps(
            {
                "review_root": str(root.resolve()),
                "domain_root": str(domain_root.resolve()),
                "domain_code": infer_domain_code(root),
                "current": read_current_json(domain_root),
                "is_round_folder": is_round_id(root.name),
            },
            indent=2,
        )
    )
    return 0


def cmd_set_current(args: argparse.Namespace) -> int:
    domain_root = Path(args.domain_root)
    path = write_current_json(domain_root, args.round_id, args.status)
    print(
        json.dumps(
            {
                "path": str(path.resolve()),
                "round_id": args.round_id,
                "status": args.status,
            },
            indent=2,
        )
    )
    return 0


def cmd_phase1_gate(args: argparse.Namespace) -> int:
    result = phase1_slot_status(_effective_review_root(args), args.slot)
    print(json.dumps(result, indent=2))
    return 0 if result["state"] == "complete" else 1


def cmd_resolve_prompt(args: argparse.Namespace) -> int:
    review_root = _effective_review_root(args)
    llms_root = Path(args.llms_root)
    domain = getattr(args, "domain", None) or infer_domain_code(review_root)
    paths = resolve_phase_prompt_paths(llms_root, domain, args.phase)
    print(
        json.dumps(
            {
                "domain_code": domain,
                "phase": args.phase,
                "paths": paths,
            },
            indent=2,
        )
    )
    return 0 if paths["effective"] else 1


def cmd_resolve_domain(args: argparse.Namespace) -> int:
    review_root = _effective_review_root(args)
    domain = infer_domain_code(review_root)
    llms_root = Path(args.llms_root)
    print(
        json.dumps(
            {
                "domain_code": domain,
                "domain_standards_root": str(domain_standards_root(llms_root, domain)),
                "review_root": str(review_root.resolve()),
                "shortlist_path": str(default_shortlist_path(llms_root)),
            },
            indent=2,
        )
    )
    return 0


def cmd_list_participants(args: argparse.Namespace) -> int:
    parts = parse_participants(_effective_review_root(args))
    print(json.dumps([asdict(p) for p in parts], indent=2))
    return 0

def cmd_list_models(args: argparse.Namespace) -> int:
    review_root = Path(args.review_root) if args.review_root else None
    llms_root = Path(args.llms_root)
    shortlist = Path(args.shortlist) if getattr(args, "shortlist", None) else None
    phase = getattr(args, "phase", None)
    domain = getattr(args, "domain", None)
    if review_root and not domain:
        domain = infer_domain_code(review_root)
    if phase is None:
        phase = (
            _current_phase_only(review_root, llms_root)
            if review_root
            else 2
        )
    roster = build_dispatch_roster(
        llms_root=llms_root,
        review_root=review_root,
        domain_code=domain or "",
        phase=int(phase),
        project_code=getattr(args, "project", None),
        shortlist_path=shortlist,
    )
    payload: dict[str, Any] = {
        "domain_code": domain,
        "phase": phase,
        "shortlist_path": roster.get("shortlist_path"),
        "shortlist_error": roster.get("shortlist_error"),
        "application": roster.get("application"),
        "fv": roster.get("fv"),
        "slots": roster.get("slots"),
        "yaml_override_sources": roster.get("yaml_override_sources"),
        "fallback_models_yaml": load_fallback_models_yaml().get("slots"),
    }
    if review_root:
        parts = parse_participants(review_root)
        payload["participants"] = resolve_participant_models(
            parts,
            review_root,
            llms_root=llms_root,
            phase=int(phase),
            domain_code=domain or "",
            project_code=getattr(args, "project", None),
            shortlist_path=shortlist,
        )
    print(json.dumps(payload, indent=2))
    return 0 if not roster.get("shortlist_error") else 1


def cmd_resolve_model(args: argparse.Namespace) -> int:
    review_root = Path(args.review_root) if args.review_root else None
    llms_root = Path(args.llms_root)
    shortlist = Path(args.shortlist) if getattr(args, "shortlist", None) else None
    slot = args.slot.lower()
    phase = getattr(args, "phase", None)
    domain = getattr(args, "domain", None)
    result = resolve_model_for_slot(
        slot,
        review_root,
        llms_root=llms_root,
        phase=phase,
        domain_code=domain,
        project_code=getattr(args, "project", None),
        shortlist_path=shortlist,
    )
    if review_root:
        parts = parse_participants(review_root)
        match = next((p for p in parts if p.slot == slot), None)
        if match:
            result["folder_suffix"] = match.folder_suffix
            result["alias"] = match.alias
    print(json.dumps(result, indent=2))
    return 0 if result.get("resolved") else 1


def cmd_resolve_shortlist(args: argparse.Namespace) -> int:
    review_root = Path(args.review_root) if args.review_root else None
    llms_root = Path(args.llms_root)
    shortlist = Path(args.shortlist) if getattr(args, "shortlist", None) else None
    domain = getattr(args, "domain", None) or (
        infer_domain_code(review_root) if review_root else ""
    )
    phase = getattr(args, "phase", None)
    if phase is None:
        phase = (
            _current_phase_only(review_root, llms_root)
            if review_root
            else 2
        )
    roster = build_dispatch_roster(
        llms_root=llms_root,
        review_root=review_root,
        domain_code=domain,
        phase=int(phase),
        slot_count=getattr(args, "slots", None),
        project_code=getattr(args, "project", None),
        shortlist_path=shortlist,
    )
    print(json.dumps(roster, indent=2))
    if roster.get("shortlist_error"):
        return 1
    unresolved = [
        s for s in (roster.get("slots") or {}).values() if not s.get("resolved")
    ]
    return 1 if unresolved else 0


def build_parser() -> argparse.ArgumentParser:
    shared = argparse.ArgumentParser(add_help=False)
    shared.add_argument(
        "--review-root",
        type=str,
        help="Path to the timestamped round folder (…/{domain}/{YYYYMMDDTHHMMSSZ}/)",
    )
    shared.add_argument(
        "--domain-root",
        type=str,
        default=None,
        help="Domain folder; resolves --review-root via current.json when --review-root omitted",
    )
    shared.add_argument(
        "--llms-root",
        type=str,
        default=str(DEFAULT_LLMS_ROOT),
        help=(
            "llms_peer_review process/ root (default from config/settings.json). "
            "Shortlist resolves to <repo>/tools/llm_selection/reports/… "
            "so this skill works from any consumer repo."
        ),
    )
    shared.add_argument(
        "--shortlist",
        type=str,
        default=None,
        help="Override path to ranking_shortlist_cursor_capability_weighted_latest.json",
    )
    shared.add_argument(
        "--project",
        type=str,
        default=None,
        help="Optional project overlay code (e.g. finance, webapp) for application key",
    )
    shared.add_argument(
        "--domain",
        type=str,
        default=None,
        help="Override domain code (default: infer from --review-root)",
    )
    shared.add_argument(
        "--phase",
        type=int,
        choices=range(0, 6),
        default=None,
        help="Peer-review phase for shortlist application selection (default: current)",
    )

    parser = argparse.ArgumentParser(
        description="Peer review orchestrator — status, gates, prompt resolution, rounds.",
        parents=[shared],
    )

    sub = parser.add_subparsers(dest="command")

    sub.add_parser("status", help="Full status JSON (default when --review-root set)", parents=[shared])

    p_gate = sub.add_parser(
        "phase1-gate", help="Check phase 1 slot completion", parents=[shared]
    )
    p_gate.add_argument("--slot", required=True, help="Folder suffix e.g. llm1_composer")

    p_prompt = sub.add_parser(
        "resolve-prompt", help="Resolve phase prompt file paths", parents=[shared]
    )
    p_prompt.set_defaults(_require_phase=True)

    sub.add_parser(
        "resolve-domain", help="Infer domain code from review root", parents=[shared]
    )

    sub.add_parser(
        "resolve-review-root",
        help="Resolve round folder from --review-root or --domain-root/current.json",
        parents=[shared],
    )

    p_init = sub.add_parser(
        "init-round",
        help="Create timestamped round under --domain-root (phases 0–5 live there)",
        parents=[shared],
    )
    p_init.add_argument(
        "--kind",
        choices=("initial", "revision"),
        default="initial",
    )
    p_init.add_argument(
        "--peer-review-root",
        default=None,
        help="Consumer peer_review root (default: parent of domain-root)",
    )
    p_init.add_argument("--baseline", default=None, help="Baseline round_id for revision")
    p_init.add_argument("--change-pack", default=None, help="Path to program change_pack.md")
    p_init.add_argument("--summary", default=None, help="Short round summary for round.md")
    p_init.add_argument(
        "--round-id",
        default=None,
        help=(
            "Shared review round id YYYYMMDDTHHMMSSZ. Pass the same value for every domain "
            "of one review; omitted = new timestamp (first domain only)."
        ),
    )
    p_init.add_argument(
        "--status",
        default="in_progress",
        choices=("in_progress", "awaiting_human", "accepted"),
        help="Value written to current.json",
    )
    p_init.set_defaults(_require_domain_root=True)

    p_cur = sub.add_parser(
        "set-current",
        help="Update domain current.json (round_id + status)",
        parents=[shared],
    )
    p_cur.add_argument("--round-id", required=True)
    p_cur.add_argument(
        "--status",
        required=True,
        choices=("in_progress", "awaiting_human", "accepted"),
    )
    p_cur.set_defaults(_require_domain_root=True)

    sub.add_parser(
        "list-participants",
        help="List participants from phase0_setup.md",
        parents=[shared],
    )

    sub.add_parser(
        "list-models",
        help="Show shortlist-resolved Task slugs for slots",
        parents=[shared],
    )

    p_model = sub.add_parser(
        "resolve-model",
        help="Resolve a slot (llm1, llm2, …) to a Cursor Task model slug via shortlist",
        parents=[shared],
    )
    p_model.add_argument("--slot", type=str, required=True)

    p_short = sub.add_parser(
        "resolve-shortlist",
        help="Build full dispatch roster from cursor capability_weighted shortlist",
        parents=[shared],
    )
    p_short.add_argument(
        "--slots",
        type=int,
        default=None,
        help=(
            "Force proposer slot count (bypasses roster_sizing auto-cut). "
            "Default: auto from unique-provider shortlist scores "
            "(min_slots / tau / rho in config/settings.json)."
        ),
    )

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    # Default with no subcommand:
    # - with --review-root or --domain-root → status
    # - otherwise → resolve-shortlist for generic phase 2 (works from any cwd)
    if args.command is None:
        if args.review_root or getattr(args, "domain_root", None):
            return cmd_status(args)
        args.command = "resolve-shortlist"
        if args.domain is None:
            args.domain = ""
        if args.phase is None:
            args.phase = 2
        if not hasattr(args, "slots"):
            args.slots = None
        return cmd_resolve_shortlist(args)

    if getattr(args, "_require_phase", False) and args.phase is None:
        print("error: --phase is required for resolve-prompt", file=sys.stderr)
        return 2

    if getattr(args, "_require_domain_root", False) and not getattr(args, "domain_root", None):
        print("error: --domain-root is required", file=sys.stderr)
        return 2

    root_optional = args.command in (
        "list-models",
        "resolve-model",
        "resolve-shortlist",
        "init-round",
        "set-current",
    )
    if not args.review_root and not getattr(args, "domain_root", None):
        if not root_optional:
            print("error: --review-root or --domain-root is required", file=sys.stderr)
            return 2
        if args.command == "resolve-shortlist" and not args.domain:
            print(
                "error: --domain is required when --review-root is omitted",
                file=sys.stderr,
            )
            return 2

    handlers = {
        "status": cmd_status,
        "phase1-gate": cmd_phase1_gate,
        "resolve-prompt": cmd_resolve_prompt,
        "resolve-domain": cmd_resolve_domain,
        "resolve-review-root": cmd_resolve_review_root,
        "init-round": cmd_init_round,
        "set-current": cmd_set_current,
        "list-participants": cmd_list_participants,
        "list-models": cmd_list_models,
        "resolve-model": cmd_resolve_model,
        "resolve-shortlist": cmd_resolve_shortlist,
    }
    return handlers[args.command](args)


if __name__ == "__main__":
    sys.exit(main())