# Referência — modelos e exemplos para peer review genérica

Os textos entre chaves são campos a preencher. Os artefatos do processo ficam em inglês, conforme `process/standards/language.md`; preserve citações curtas no idioma do documento-fonte. Remova campos que não façam sentido para a revisão em vez de preenchê-los com valores artificiais.

## Esqueleto de `phase0_setup.md`

```markdown
# Peer review setup

## Process profile
- **Route:** generic topic; no applicable formalized D0X or fallback profile
- **Run ID (UTC):** {YYYYMMDDTHHMMSSZ}
- **Automated domain guard:** not applicable; no matching domain ownership catalog
- **Phase-5 independent audit:** required

## Review object
- **Subject:** {artifact or question}
- **Exact source/version:** {path, revision, date, page range, or supplied item identifier}
- **Requested outcome:** {what the user needs from the review}
- **Language:** English for process artifacts; source quotations remain in their original language

## Scope and criteria
- **In scope:** {specific questions, sections, or checks}
- **Out of scope:** {what this review must not decide}
- **Acceptance criteria:** {observable conditions for a useful result}
- **Applicable jurisdiction / standard / date:** {when relevant; otherwise not applicable}

## Roles and decision authority
- **Human decision owner:** {person or role}
- **Human expert required for:** {professional decisions the LLMs cannot accept}
- **LLM role:** {reviewers / analysts / other}
- **Final acceptance:** {human authority; never an LLM}

## Sources and evidence ownership
- **User-provided evidence:** {path/version or secure in-session reference}
- **External source hierarchy:** {official sources first; note currency requirements}
- **Intent or preference owned by:** {human role}
- **Facts to research:** {LLM responsibility}
- **Expert judgments reserved for:** {human specialist}

## Confidentiality
- **Sensitivity:** {classification or brief note}
- **Persistence rule:** {in-session / sanitized artifacts / approved secure path}
- **Identifiers to omit or redact:** {list, or none}

## Participants and availability
| Participant (llmN) | Model dispatch ID | Provider | Availability | Failure class | Checked (UTC) |
| --- | --- | --- | --- | --- | --- |
| llm1 | {resolved slug} | {provider} | available | none | {YYYYMMDDTHHMMSSZ} |
| llm2 | {resolved slug} | {provider} | available | none | {YYYYMMDDTHHMMSSZ} |
| llm3 | {resolved slug} | {provider} | available | none | {YYYYMMDDTHHMMSSZ} |

- **Phase-5 leader:** {participant ID, such as llmN; record selection basis}
- **Roster approved by user:** {date or reference}

## Open human decisions
- {question ID, owner, whether it blocks phase 2; or none}

## Notes
- {important constraints, assumptions, and transfers of responsibility}
```

Keep this setup specific to the artifact. For a prescription or contract, do not paste the source contents into it; record an approved path or a sanitized reference and the exact version reviewed.

## Resolver de participantes

No Windows PowerShell (terminal de comandos do Windows), o comando sem argumentos devolve a lista genérica de fase 2 com o dimensionamento automático configurado. Leia a quantidade de participantes e os `model_slug` do resultado e congele essa lista no setup; o número exato segue a configuração local, não um valor fixo neste exemplo.

```powershell
python "$HOME/.config/opencode/skills/peer-review-orchestrator/scripts/orchestrator.py"
```

Para escolher o líder entre os mesmos participantes, passe a quantidade aprovada no setup à resolução da fase 5:

```powershell
python "$HOME/.config/opencode/skills/peer-review-orchestrator/scripts/orchestrator.py" resolve-shortlist --domain generic --phase 5 --slots N
```

Substitua `N` pelo total de posições de participante congelado na fase 0; confirme que `llmN` continua sendo um dos modelos aprovados. O primeiro comando pode receber `resolve-shortlist --domain generic --phase 2 --slots N` quando o usuário tiver escolhido manualmente a quantidade de participantes.

## Phase 1 question record

Use `phase1_questions/decisions.md` as one consolidated list. Each question may use this shape; do not force options when the human needs to answer in their own words.

```markdown
# Phase 1 — consolidated questions

## Q-01 — {short, plain-language title}
- **Owner:** {human role, source research, or specialist}
- **Blocks phase 2:** {yes/no and why}
- **Status:** {awaiting human / answered / deferred / resolved by research}

### Question
{One atomic question in language the owner can answer.}

### Why it remains open
{What was checked already and why reading/research did not resolve it.}

### Examples or options
{Only when needed to make the subject and consequences clear.}

### Evidence and sources
{Exact input locations and citations, or a note that no external claim is involved.}

### Human answer
{Leave empty until the human responds; record their meaning faithfully.}

### Analyst reading
{Optional interpretation, explicitly separate from the human's words.}
```

`phase1_questions/answers.md` may hold the response log if many questions exist. An empty answer is pending, not approval. A material question resolved by research stays visible with its source and uncertainty; trivial lookups do not need a record.

## Participant prompt wrapper

Use the wrapper below for each assigned role. Pass the generic process prompt by path and require the participant to read it; the wrapper identifies the assignment but does not replace the phase prompt.

```text
You are {PARTICIPANT_LABEL} in a multi-model peer review.

Review root: {REVIEW_ROOT}
Phase and role: {PHASE_NUMBER} — {ROLE}
Resolved model: {MODEL_SLUG}
Subject and exact source version: {SUBJECT_AND_VERSION}
Your output path: {OUTPUT_PATH}

Read before working:
1. {LLMS_PEER_REVIEW_ROOT}/overview.md
2. {LLMS_PEER_REVIEW_ROOT}/phases/{GENERIC_PHASE_PROMPT}
3. {LLMS_PEER_REVIEW_ROOT}/standards/roles.md
4. {LLMS_PEER_REVIEW_ROOT}/standards/relevant_questions.md and self_answered_questions.md, when phase 1
5. {LLMS_PEER_REVIEW_ROOT}/standards/sources.md and language.md
6. {LLMS_PEER_REVIEW_ROOT}/standards/client_deliverables.md, for phases 2, 4, and 5
7. {LLMS_PEER_REVIEW_ROOT}/standards/boundary_guard.md, for phase-5 audit principles only; do not invent a D0X manifest or run process_guard
8. {REVIEW_ROOT}/phase0_setup.md and the listed source version
9. {PRIOR_ARTIFACTS}, only when the assigned phase requires them

Task: {PHASE_SPECIFIC_ASSIGNMENT}

Rules:
- Use only the generic phase prompt; do not import a D0X-specific override.
- Do not ask the user questions in this task. Mark a real blocker NEEDS_USER.
- Do not invent missing facts, professional authority, or acceptance.
- Write only to the assigned output path and use verifiable references for material claims.
- Do not treat peer agreement or majority vote as evidence.

When finished, respond with exactly these lines:
STATUS: DONE | NEEDS_USER | BLOCKED
SUMMARY: <one line>
FILES_WRITTEN:
- <path or none>
PENDING_USER:
- <question id or none>
NOTES: <optional one line>
```

Launch one participant per assignment in parallel when the phase permits it. In phase 1, complete the single propose → critique → revise → consolidate cycle once for the whole review. Stop the phase if any participant returns `NEEDS_USER` or `BLOCKED`.

## Phase 3 critique format

```markdown
# Crossed critique — {critic participant} vs {proposal participant}

## Review target
- **Proposal:** {path and version}
- **Source version reviewed:** {exact input version}

## Findings
### R-01 — {short title}
- **Kind:** factual error | omission | contradiction | risk | ambiguity | complement
- **Location:** {section, clause, page, field, or paragraph}
- **Observation:** {specific statement or missing item}
- **Why it matters:** {consequence for the requested outcome}
- **Evidence:** {source citation; required when contesting a factual claim}
- **Suggested disposition:** {investigate, clarify, revise, retain with caveat}

## Correlated assumptions
- {shared unsupported assumption and evidence needed, or none}
```

Critiques are not votes. A factual assertion must be tied to the source that supports or contradicts it; disagreement about preference must stay labeled as preference.

## Phase 4 revision log

```markdown
# Post-critique revision log

| Finding | Disposition | Change in final proposal | Rationale / evidence |
| --- | --- | --- | --- |
| R-01 | accepted / partly accepted / rejected / unresolved | {what changed or stayed} | {why, with source if factual} |
```

Every material critique gets a disposition. An unresolved item remains visible in the proposal and is handed to the phase-5 leader; do not silently remove it from the record.

## Phase 5 consolidation matrix

```markdown
# Consolidation matrix

| Issue or criterion | Proposal A | Proposal B | Proposal C | Unified disposition | Reason / evidence |
| --- | --- | --- | --- | --- | --- |
| {R-01 or criterion} | {position} | {position} | {position} | {what the final answer says} | {reason and source} |
```

Use participant IDs only in this internal file. The client-facing `overview.md` contains the unified result, not a transcript, ranking, or model attribution.

## Phase 5 independent audit

```markdown
# Independent audit

- **Auditor:** {separate reviewer; never the phase-5 leader; prefer someone who did not draft a proposal}
- **Leader:** {participant ID}
- **Status:** PASS | BLOCKED | NEEDS_HUMAN
- **Source/version checked:** {exact source version}

## Checks
- [ ] Scope and requested outcome match phase0_setup.md
- [ ] Every material claim is supported by the cited source or labeled reasoning
- [ ] Source quotations, clause/page references, and versions are accurate
- [ ] Important omissions, contradictions, and correlated assumptions are surfaced
- [ ] Human-owned and specialist-owned decisions remain with the right person
- [ ] No recommendation exceeds the authority or safety limits in phase0_setup.md
- [ ] Sensitive source details are minimized or redacted

## Findings
- {ID, severity: block / needs_human / note, evidence, required action; or none}

## Exit decision
- **Blocking findings resolved:** {yes/no}
- **Human decisions still pending:** {list or none}
- **Audit rationale:** {short explanation of status}
```

The `PASS` label means the report passed this review's stated completeness and traceability checks. It does not grant legal, clinical, regulatory, or other professional approval.

## Example routing and application

### Contract

First distinguish a legal agreement from an interface/data contract. A legal agreement with no applicable domain profile uses this skill; an OpenAPI/AsyncAPI/Avro deliverable that matches `d04b` or `d13b` uses that existing profile and its prerequisites. In phase 0, pin the exact draft and jurisdiction if relevant, name the requested review goals, and state which legal interpretations require counsel. Phase 2 can use a findings matrix with clause, observed wording, ambiguity or risk, evidence, consequence, and a question or drafting option for counsel. The final answer must distinguish what the text says from legal conclusions that need qualified review.

### Medical prescription

Use this skill only for a bounded review that does not ask the models to diagnose, prescribe, change a dose, or declare a patient-specific therapy safe. Minimize patient data and identify the exact image/text version. The output can list a faithful transcription, missing or unreadable fields, and discrepancies against explicitly supplied authoritative information, each tied to its source location. Any clinical uncertainty or possible discrepancy goes to a pharmacist or prescriber before action; the independent audit cannot turn the report into clinical clearance.

### New D0X for the current repository

Use this skill to review a candidate domain profile that has no accepted phase prompts yet. Read the catalog and neighboring domains first, then compare the candidate's purpose, trigger, owner, boundaries, dependencies, evidence direction, deliverable precision, file structure, and need for phase overrides. The candidate package may include `methodology.md`, `deliverables.md`, `file_structure.md`, source guidance, and generic-compatible phase overrides as appropriate. Keep it under the peer-review proposal round until phase 5 is accepted; only then integrate it into `process/domains/` and update the catalog with the user's authorization. Never apply the candidate's own phase prompt to its review.

### Cases routed elsewhere

- An existing formalized D0X or an applicable fallback profile already defines the requested deliverable: use `peer-review-orchestrator`.
- A changed requirement reopens one accepted D0X deliverable: use `peer-review-orchestrator` for a new revision round; a material change that affects several accepted D0X deliverables uses `peer-review-delta-reassessment`.
- A topic merely contains words such as “contract” or “security” but requests a different kind of work: route by the actual artifact and desired outcome, not the keyword.
