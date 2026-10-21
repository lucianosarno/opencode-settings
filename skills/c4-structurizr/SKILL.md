---
name: c4-structurizr
description: Standardizes C4 architecture diagrams authored in Structurizr DSL. Use automatically when creating, editing, validating, viewing, exporting, or reviewing workspace.dsl, C4 diagrams, Structurizr, PlantUML-derived C4 images, or C4 documentation in any repository.
---

# C4 with Structurizr

## Required convention

1. Treat the accepted package's root `workspace.dsl` as the single source of truth for the C4 model. `overview.md` and `adr/` stay the narrative and decision sources; the DSL imports them with `!docs .` and `!adrs adr`.
2. Put a self-contained `render.ps1` beside it:
   - no arguments: native browser viewer;
   - `-Mode export`: browser-rendered PNG fallbacks;
   - `-Mode validate`: DSL validation.
3. Use version-pinned `structurizr/structurizr` images.
4. Give each workspace a path-derived Docker container name.
5. Select the first free port from 8080 unless the user supplies `-Port`.
6. Open the browser only after the new container responds successfully and identifies as Structurizr.
7. Export PNGs with the version-matched `*-playwright` image, not PlantUML.
8. Discover and export all view keys; do not hardcode project-specific view names.
9. Color-code by hosting service/technology: tag each element with its concrete hosting
   service (e.g. `tags "Cloud Run"`, `tags "BigQuery"`, `tags "Secret Manager"`) and bind one
   distinct background color per tag in the `styles` block. Structurizr renders the tag→color
   mapping natively as each view's `*-key.png` legend — no external tools needed.
10. Commit the `*-key.png` legends alongside the diagram PNGs whenever service-color tags are
    used (readers of static fallbacks need the legend); otherwise commit only non-legend PNGs.
11. Ignore `.structurizr/` and derived `workspace.json`.

## Why

- Native and PNG paths use the same browser renderer, preserving DSL styles and edge-label behavior.
- Service-colored tags make container views self-explanatory: readers see at a glance which
  elements are Cloud Run vs BigQuery vs Pub/Sub etc., and the auto-generated key doubles as the legend.
- Project-specific names plus free ports allow multiple repository viewers to run simultaneously.
- The repository-local script makes the workflow available to teammates without this personal skill.

## Workflow

1. Find the accepted/canonical `workspace.dsl`; do not accidentally operate on peer-review drafts.
2. Read the local C4 README and renderer script before changing conventions.
3. Validate after DSL edits.
4. Run native PNG export and inspect generated files.
5. Start the viewer while another repository viewer occupies port 8080; verify automatic isolation.
6. Check `git diff --check` and repository status.
7. Update nearby architecture documentation to identify PNGs as static fallbacks.

## Rendering caveat

Manual drag layouts are stored in derived workspace state, not automatically in DSL. Keep DSL as
the source of truth unless the project deliberately adopts committed Structurizr JSON for manual
layout. Do not claim that a dragged layout is reproducible from DSL alone.
