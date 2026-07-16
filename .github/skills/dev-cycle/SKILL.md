---
name: dev-cycle
argument-hint: "Describe the SDK task, desired outcome, and any constraints for the development loop."
description: "Use when running a short human-in-the-loop Teardrop SDK development cycle that needs scoped research, a concrete plan, implementation, and strict verification with high token efficiency."
disable-model-invocation: false
metadata: teardrop-sdk, dev-cycle, coordinator, token-efficiency, workflow, research, planning, implementation, verification, human-in-the-loop, python client library
user-invocable: true
---

You are the coordinator for a short development loop on `teardrop-sdk`, the Python client library for the Teardrop API. Your job is not to be autonomous for long stretches. Your job is to minimize wasted context, route work to the right specialist skill, and stop at explicit human review points when the task meaningfully changes.

## Goal

Run a bounded loop for SDK work:

SCOPE -> RESEARCH -> PLAN -> IMPLEMENT -> VERIFY

Use existing repo skills instead of recreating them:
- `deep-researcher` for targeted repo or API-contract research
- `speedy-coder` for implementation
- `ruthless-critic-verifier` for strict review

## Operating Rules

- Keep the loop short. Prefer one pass per phase.
- Keep the user as the decision maker. Escalate when scope changes or when VERIFY blocks with non-local findings.
- Load only the files, repo-memory notes, and symbols needed for the current phase.
- Treat live repo code as primary truth. Treat `/memories/repo/` as secondary and verify before relying on it.
- Treat `spec/openapi.json` and `spec/events.schema.json` as the authoritative remote API contract, not of this repo's own code — verify names/shapes against this repo's client and models (snake_case) before trusting any spec detail, since the spec is JSON-schema, not prose.
- Treat `README.md` as a lightweight index (Quick Start + links); the actual usage documentation for each feature domain lives under `docs/*.md` — update the matching `docs/<topic>.md` file for behavior changes, and only touch `README.md` if a new topic/file is introduced (add a row to its documentation table).
- Do not reload broad architecture notes once a local code path is identified.
- Stop after one VERIFY -> PLAN retry unless the user asks for another iteration.

## Session Memory Schema

Maintain these fields in `/memories/session/` and update only the fields needed for the current phase:

```text
task: original user request
domain_flags: touched areas such as client_core, client_async, client_sync, auth, billing, marketplace, mcp, schedules, event_triggers, streaming, models, exceptions, webhook_verify, tests, docs
affected_files: up to 10 likely files
research_summary: <= 500 tokens
plan_ref: /memories/session/plan.md
verify_status: PENDING | PASS | BLOCK
block_findings: empty or concrete blocking findings
```

Use short bullet points or one-line values. Do not store full transcripts.

## Phase 1: SCOPE

Purpose: identify the narrowest slice of the SDK that actually controls the requested behavior.

Actions:
- Extract the requested outcome, constraints, and success signal.
- Identify domain flags from the task (which client mixin, model module, or streaming helper is involved).
- Name up to 10 likely files, preferring the owning module (e.g. `client/billing.py`, `models/billing.py`) over broad surrounding surfaces.
- Load at most 2 targeted repo-memory notes or note sections if they are relevant (`/memories/repo/testing-notes.md` is usually the first check).
- Record the task, domain flags, and affected files in session memory.

Exit criteria:
- You can state one falsifiable local hypothesis.
- You can name one cheap discriminating check.
- You know which nearby file or function to inspect first.

Token budget:
- 0 to 2 repo-memory files or sections
- 1 to 3 targeted file reads or searches

## Phase 2: RESEARCH

Purpose: gather only the evidence needed to make a correct plan.

Use `deep-researcher` when:
- the behavior crosses the async/sync boundary or multiple client mixins
- repo memory or `docs/*.md` makes a claim that needs checking against live code or `spec/openapi.json`
- external docs (httpx, pydantic, JWT/SIWE specs) are required

Actions:
- Search specific symbols, methods, models, or tests.
- Prefer targeted reads over broad scans.
- Cross-check any repo-memory or handoff-doc claims against live code before citing them.
- Produce a concise summary with known facts, assumptions, risks, and unresolved points.

Hard limits:
- no more than 2 research rounds
- no more than 4 targeted searches
- no more than 5 file reads unless a local ambiguity remains

Output:
- `research_summary` in session memory, capped at 500 tokens

## Phase 3: PLAN

Purpose: convert research into a small, testable edit plan.

Actions:
- Name the exact methods, mixins, models, or exceptions to change.
- Keep the plan additive and minimal.
- Include the first focused validation step immediately after the first substantive edit.
- Include sync/async parity and public-export checks if the change adds or renames a public method or model.
- If the change touches a real API endpoint's request/response shape, add a follow-up to check `tests/integration/` coverage.

Plan requirements:
- concrete edit target
- falsifiable hypothesis
- validation command or check
- rollback or retry path if VERIFY blocks

Output:
- write the plan to `/memories/session/plan.md`

## Phase 4: IMPLEMENT

Purpose: apply the smallest correct change.

Use `speedy-coder` for implementation.

Actions:
- Read only the files named in the plan unless validation disproves the hypothesis.
- Make the smallest plausible edit first.
- Always run validation using the project virtual environment: `venv\Scripts\python -m pytest ...` (Windows) or `venv/bin/python -m pytest ...` (Unix). Never use a global/system Python, which may be missing `httpx`/`pydantic`/`anyio` or use the wrong version.
- After the first substantive edit, run the narrowest available validation before further patching (e.g. `venv\Scripts\python -m pytest tests/test_<module>.py -q`).
- Preserve SDK invariants and existing style (see `speedy-coder`'s Operating Map and Do-Not-Conflate rules).

If the touched area includes:
- `client/_core.py` or `client/_async.py`/`_sync.py`: preserve error-mapping (`_raise_for_status`) and sync/async parity
- `auth.py` or `client/auth.py`: preserve token refresh buffer and the three supported auth modes
- `webhook_verify.py` or `event_triggers.py`: preserve constant-time HMAC comparison and signature format
- `streaming/`: preserve atomic-USDC integer handling and existing `EVENT_*` contract
- any barrel (`teardrop/__init__.py`, `client/__init__.py`, `models/__init__.py`): preserve existing exported names (published-package compatibility)

## Phase 5: VERIFY

Purpose: try to block bad changes before they spread.

Use `ruthless-critic-verifier` for this phase.

Validation tiering:
- **Fast-Track Verification (Always)**: Run pytest on the immediate local test file (e.g. `tests/test_<slice>.py`) using the project venv wrapper first. Do not sweep the full test suite on the first execution.
- **Slow-Track Verification (Conditional)**: If the change touches a real endpoint's request/response shape or the public API surface, run the full unit suite (`venv\Scripts\python -m pytest -q`) and `ruff check` / `ruff format --check` before declaring PASS. Only run `tests/integration/` if the user has integration credentials configured (`TEARDROP_TEST_URL`/`EMAIL`/`SECRET`) — otherwise those tests skip cleanly and prove nothing.

Always check:
- correctness against the requested behavior
- edge cases exposed by the local code path
- test coverage for the changed slice
- assumptions that were inferred rather than proven

Additional checks by domain:
- public API/model/exception changes, auth, billing, x402, webhooks: load `ruthless-critic-verifier`'s SDK review checklist in full
- sync/async parity: confirm `client/_sync.py` was updated alongside any new `AsyncTeardropClient` method

VERIFY output must be one of:
- `PASS`: no blocking findings, validation is sufficient for current scope
- `BLOCK`: concrete findings with impact, confidence, and next edit target
- `PENDING`: validation could not run or evidence is incomplete

If BLOCK:
- write findings into `block_findings` using this format:
    - error_type: (test_fail | invariant_violation | logic_error | missing_test)
    - snippet: (specific traceback line, assertion, or exact failing test name)
    - edit_target: (the specific file, function, module, or line range)
- retry PLAN once using those findings as the new constraint set
- if the second VERIFY still blocks, stop and ask the user to re-scope or choose a direction

## Token Economy Rules

- Never carry full phase outputs forward when a short summary or file list is enough.
- Prefer session memory fields over replaying prior chat context.
- Prefer line-range reads over whole-file reads.
- Prefer one nearby validation command over broad test sweeps until the edit stabilizes.
- Do not use full-repo exploration after SCOPE unless the current hypothesis is falsified.

## SDK-Specific Triggers

Give extra scrutiny (slower, more thorough VERIFY) when the task touches:
- `src/teardrop/client/_core.py` (transport, error mapping, response parsing helpers)
- `src/teardrop/client/_async.py` / `src/teardrop/client/_sync.py` (client composition, sync/async parity)
- `src/teardrop/auth.py` (token lifecycle) or `src/teardrop/client/auth.py` (SIWE/login flows)
- `src/teardrop/webhook_verify.py` or `src/teardrop/client/event_triggers.py` (signature verification)
- `src/teardrop/streaming/` (SSE event contract, USDC formatting)
- any `__init__.py` barrel (public export surface)

## What Good Looks Like

A good loop for this repo usually has these properties:
- 1 narrow hypothesis
- 1 cheap check
- 1 small edit
- 1 focused validation
- 1 strict review pass

Anything broader should be broken into multiple user-guided loops.