---
name: automations-recent-changes
description: >-
  Automations should prioritize files changed since the last similar run. Use when
  running or re-running automations like "Quality Assurance", "Find critical bugs"
  and similar ones, to focus attention on the recent delta instead of re-reviewing
  everything from scratch.
---

# Automations pay more attention to recent changes

Whenever running automations like "Quality Assurance", "Find critical bugs" and similar ones, pay special attention for files changed after the last time when the same automation ran (check specific branches created for each automation run in the repo).
