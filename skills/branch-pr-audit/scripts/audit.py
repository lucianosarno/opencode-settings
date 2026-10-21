#!/usr/bin/env python3
"""
Tag branch tips with audit/* refs reflecting GitHub PR state for Git Graph visibility.

Default (no args): dry-run audit against develop (fallback main), print summary table.

Team convention: only refs under audit/* are managed by this tool. Safe to push with --push.
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

TAG_PREFIX = "audit/"
TAG_PATTERN = re.compile(r"^audit/(?:pr-(\d+)-(open|merged|closed)|no-pr-(.+))$")


@dataclass(frozen=True)
class BranchAudit:
    branch: str
    tip: str
    pr_number: int | None
    status: str  # open | merged | closed | no-pr
    tag: str
    action: str


def run_git(*args: str, cwd: Path) -> str:
    result = subprocess.run(
        ["git", *args],
        cwd=cwd,
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != 0:
        raise RuntimeError(result.stderr.strip() or f"git {' '.join(args)} failed")
    return result.stdout.strip()


def run_gh(repo_root: Path) -> list[dict]:
    result = subprocess.run(
        [
            "gh",
            "pr",
            "list",
            "--state",
            "all",
            "--limit",
            "500",
            "--json",
            "number,headRefName,state,mergedAt,closedAt,updatedAt",
        ],
        cwd=repo_root,
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != 0:
        raise RuntimeError(
            result.stderr.strip()
            or "gh pr list failed (install GitHub CLI and run gh auth login)"
        )
    return json.loads(result.stdout or "[]")


def resolve_base_branch(repo_root: Path, requested: str | None) -> str:
    if requested:
        run_git("rev-parse", "--verify", requested, cwd=repo_root)
        return requested
    for candidate in ("develop", "main", "master"):
        try:
            run_git("rev-parse", "--verify", candidate, cwd=repo_root)
            return candidate
        except RuntimeError:
            continue
    raise RuntimeError("Could not resolve base branch (tried develop, main, master)")


def normalize_branch_name(raw: str) -> str:
    name = raw.strip()
    if name.startswith("remotes/origin/"):
        name = name[len("remotes/origin/") :]
    elif name.startswith("origin/"):
        name = name[len("origin/") :]
    return name


def branch_to_slug(branch: str) -> str:
    slug = branch.replace("/", "-").replace("_", "-")
    slug = re.sub(r"[^a-zA-Z0-9-]", "-", slug)
    slug = re.sub(r"-+", "-", slug).strip("-").lower()
    return slug or "branch"


def tag_for_status(branch: str, pr_number: int | None, status: str) -> str:
    if status == "no-pr":
        return f"{TAG_PREFIX}no-pr-{branch_to_slug(branch)}"
    if pr_number is None:
        raise ValueError(f"PR number required for status {status}")
    return f"{TAG_PREFIX}pr-{pr_number}-{status}"


def resolve_branch_tip(repo_root: Path, branch: str) -> str:
    for ref in (branch, f"origin/{branch}"):
        try:
            return run_git("rev-parse", ref, cwd=repo_root)
        except RuntimeError:
            continue
    raise RuntimeError(f"Cannot resolve tip for branch {branch!r}")


def list_unmerged_branches(repo_root: Path, base: str) -> list[str]:
    stdout = run_git("branch", "-a", "--no-merged", base, cwd=repo_root)
    skip = {base, f"origin/{base}", "HEAD", "origin/HEAD", "main", "master"}
    names: set[str] = set()
    for line in stdout.splitlines():
        line = line.strip().lstrip("*").strip()
        if not line or " -> " in line:
            continue
        name = normalize_branch_name(line)
        if name in skip or name.endswith("/HEAD"):
            continue
        if name.startswith("remotes/"):
            continue
        names.add(name)
    return sorted(names)


def list_audit_tags(repo_root: Path) -> dict[str, str]:
    stdout = run_git("tag", "-l", f"{TAG_PREFIX}*", cwd=repo_root)
    tags: dict[str, str] = {}
    for tag in stdout.splitlines():
        tag = tag.strip()
        if not tag:
            continue
        try:
            tip = run_git("rev-list", "-n", "1", tag, cwd=repo_root)
        except RuntimeError:
            continue
        tags[tag] = tip
    return tags


def pick_pr_for_branch(prs: list[dict], branch: str) -> dict | None:
    matches = [p for p in prs if p.get("headRefName") == branch]
    if not matches:
        return None

    def sort_key(p: dict) -> tuple[int, str]:
        state = (p.get("state") or "").upper()
        priority = {"OPEN": 0, "MERGED": 1, "CLOSED": 2}.get(state, 3)
        return (priority, p.get("updatedAt") or "")

    matches.sort(key=sort_key)
    return matches[0]


def pr_status(pr: dict | None) -> tuple[int | None, str]:
    if pr is None:
        return None, "no-pr"
    state = (pr.get("state") or "").upper()
    number = int(pr["number"])
    if state == "OPEN":
        return number, "open"
    if state == "MERGED" or pr.get("mergedAt"):
        return number, "merged"
    return number, "closed"


def suggested_action(status: str) -> str:
    return {
        "open": "keep - PR open",
        "no-pr": "review - no PR opened",
        "merged": "cleanup - delete branch (merged)",
        "closed": "cleanup - delete branch (closed without merge)",
    }[status]


def build_audits(
    repo_root: Path, base: str, prs: list[dict]
) -> tuple[list[BranchAudit], list[str]]:
    branches = list_unmerged_branches(repo_root, base)
    audits: list[BranchAudit] = []
    desired_tags: set[str] = set()

    for branch in branches:
        tip = resolve_branch_tip(repo_root, branch)
        pr = pick_pr_for_branch(prs, branch)
        pr_number, status = pr_status(pr)
        tag = tag_for_status(branch, pr_number, status)
        desired_tags.add(tag)
        audits.append(
            BranchAudit(
                branch=branch,
                tip=tip,
                pr_number=pr_number,
                status=status,
                tag=tag,
                action=suggested_action(status),
            )
        )

    existing = list_audit_tags(repo_root)
    stale_tags = sorted(tag for tag in existing if tag not in desired_tags)
    return audits, stale_tags


def apply_tags(
    repo_root: Path,
    audits: list[BranchAudit],
    stale_tags: list[str],
    *,
    dry_run: bool,
) -> None:
    for tag in stale_tags:
        if dry_run:
            print(f"  [dry-run] delete tag {tag}")
            continue
        run_git("tag", "-d", tag, cwd=repo_root)

    for audit in audits:
        existing_tip = None
        try:
            existing_tip = run_git("rev-list", "-n", "1", audit.tag, cwd=repo_root)
        except RuntimeError:
            pass

        if existing_tip == audit.tip:
            continue

        if dry_run:
            print(f"  [dry-run] tag {audit.tag} -> {audit.tip[:8]} ({audit.branch})")
            continue
        run_git("tag", "-f", audit.tag, audit.tip, cwd=repo_root)


def push_audit_tags(repo_root: Path, *, dry_run: bool) -> None:
    tags = sorted(list_audit_tags(repo_root))
    if not tags:
        print("No audit/* tags to push.")
        return
    for tag in tags:
        if dry_run:
            print(f"  [dry-run] push --force origin {tag}")
            continue
        subprocess.run(
            ["git", "push", "origin", f"refs/tags/{tag}", "--force"],
            cwd=repo_root,
            check=True,
        )


def delete_remote_audit_tags(repo_root: Path, tags: list[str], *, dry_run: bool) -> None:
    for tag in tags:
        if dry_run:
            print(f"  [dry-run] push --delete origin {tag}")
            continue
        subprocess.run(
            ["git", "push", "origin", "--delete", tag],
            cwd=repo_root,
            check=False,
        )


def print_table(audits: list[BranchAudit], base: str) -> None:
    print(f"\nBranch PR audit (not merged into {base})\n")
    if not audits:
        print("  (no unmerged branches)")
        return
    print(f"{'BRANCH':<40} {'PR':>6} {'STATUS':<8} {'TAG'}")
    print("-" * 90)
    for a in audits:
        pr = str(a.pr_number) if a.pr_number is not None else "-"
        print(f"{a.branch:<40} {pr:>6} {a.status:<8} {a.tag}")
    print()
    for a in audits:
        if a.status in ("merged", "closed", "no-pr"):
            print(f"  * {a.branch}: {a.action}")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Tag unmerged branch tips with audit/* refs from GitHub PR state.",
    )
    parser.add_argument(
        "--base",
        help="Integration branch (default: develop, else main, else master)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print actions without creating/deleting tags",
    )
    parser.add_argument(
        "--apply",
        action="store_true",
        help="Create/update/delete local audit/* tags",
    )
    parser.add_argument(
        "--push",
        action="store_true",
        help="Force-push audit/* tags to origin (team visibility)",
    )
    parser.add_argument(
        "--clean",
        action="store_true",
        help="Remove all local audit/* tags (use with --push to remove from origin)",
    )
    parser.add_argument(
        "--fetch",
        action="store_true",
        help="Run git fetch --prune before audit",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    repo_root = Path.cwd()
    if not (repo_root / ".git").exists():
        print("Not a git repository.", file=sys.stderr)
        return 1

    dry_run = args.dry_run or not (args.apply or args.clean or args.push)

    try:
        if args.fetch:
            if dry_run and not args.apply:
                print("[dry-run] git fetch --prune")
            else:
                run_git("fetch", "--prune", cwd=repo_root)

        if args.clean:
            existing = sorted(list_audit_tags(repo_root))
            if dry_run:
                print(f"Would remove {len(existing)} local audit/* tag(s)")
                for tag in existing:
                    print(f"  [dry-run] delete tag {tag}")
            else:
                for tag in existing:
                    run_git("tag", "-d", tag, cwd=repo_root)
            if args.push:
                delete_remote_audit_tags(repo_root, existing, dry_run=dry_run)
            return 0

        base = resolve_base_branch(repo_root, args.base)
        prs = run_gh(repo_root)
        audits, stale_tags = build_audits(repo_root, base, prs)
        print_table(audits, base)

        if stale_tags:
            print(f"\nStale audit/* tags to remove: {len(stale_tags)}")
            for tag in stale_tags:
                print(f"  - {tag}")

        if args.apply:
            apply_tags(repo_root, audits, stale_tags, dry_run=dry_run)
            if not dry_run:
                print(f"\nApplied {len(audits)} tag(s) locally.")

        if args.push:
            if not args.apply and dry_run:
                print("\nNote: --push without --apply only pushes existing local tags.")
            push_audit_tags(repo_root, dry_run=dry_run)
            if not dry_run:
                print("Pushed audit/* tags to origin.")

    except RuntimeError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1

    if dry_run and not args.clean:
        print("\nDry run. Re-run with --apply to write tags, --push to share with team.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
