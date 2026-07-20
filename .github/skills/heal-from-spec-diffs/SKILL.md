---
name: heal-from-spec-diffs
argument-hint: "Optionally give the base ref to diff against (default origin/main), or paste known backend release notes."
description: "Use when spec/openapi.json and/or spec/events.schema.json changed relative to main branch -- typically after .github/workflows/update-spec.yml opens/updates the actions/spec-update PR -- to diff the spec, summarize what changed, research SDK impact, formulate a plan, and align the SDK's models/client methods/docs/tests with the new contract (patch existing shapes or add new features). Final step of the spec pass-thru workflow: backend spec change -> automated PR -> this skill heals the SDK. Always ends with a single summary (spec changes, what was implemented, business value) under 600 tokens."
disable-model-invocation: true
metadata: teardrop-sdk, spec sync, openapi, spec diff, spec pass-thru, actions/spec-update, contract healing, breaking change detection, codegen, models, client parity, sse events, changelog, backward compatibility
user-invocable: true
---

You are the coordinator for healing the `teardrop-sdk` codebase after its remote API contract (`spec/openapi.json`, `spec/events.schema.json`) changes. You are the **last** stage of the spec pass-thru workflow:

```
Backend `teardrop` repo main changes
  -> repository_dispatch (backend_spec_updated)
  -> .github/workflows/update-spec.yml pulls spec/openapi.json + spec/events.schema.json,
     opens/updates the `actions/spec-update` PR with a raw type-level diff
  -> heal-from-spec-diffs (this skill): DIFF -> SUMMARIZE -> RESEARCH -> PLAN -> IMPLEMENT -> VERIFY -> REPORT
```

Reuse existing repo skills instead of recreating their logic:
- `deep-researcher` for mapping spec changes to affected SDK surface
- `speedy-coder` for implementation
- `ruthless-critic-verifier` for strict review

This skill differs from `dev-cycle` in that it always starts from a concrete, mechanically-detected diff (not a free-form user request) and always ends in a fixed-format, token-capped report.

## When to Use
- The `actions/spec-update` branch/PR exists or `spec/openapi.json`/`spec/events.schema.json` otherwise differ from `main`.
- Asked to "heal", "sync", or "align" the SDK with a new/updated spec.
- Before merging a spec-update PR, to confirm hand-written models/clients/docs/tests still match the contract.

## Hard Rule: Never Read the Full Spec File
`spec/openapi.json` is large (300+ KB, ~12k lines). Never load it whole via file reads. Always go through [scripts/diff_openapi.py](./scripts/diff_openapi.py) first, and only fall back to a `git diff` scoped/grepped around one schema name for the rare case the script can't resolve (e.g. `allOf`/`$ref`-composed schemas with no inline `properties`).

## Phase 0: Locate the Diff Base

- Resolve the base ref: default `origin/main`. Run `git fetch origin main --quiet` first if a remote exists; fall back to local `main` if there is no remote.
- Confirm there is actually something to heal: `git diff --stat <base_ref> -- spec/openapi.json spec/events.schema.json`. If empty, stop and report nothing to do.

## Phase 1: Diff & Summarize

Run the bundled script (pure stdlib, no venv needed):

```
python .github/skills/heal-from-spec-diffs/scripts/diff_openapi.py <base_ref> --events
```

It reports, deterministically and cheaply:
- added/removed paths+operations (method, path)
- added/removed component schemas
- changed common schemas: added/removed properties, added/removed required fields (flags newly-required fields as breaking-for-responses)
- with `--events`: added/removed SSE event names in `events.schema.json`

Classify every reported change as one of:
- **additive** -- new optional field/endpoint/event (safe, no compat risk)
- **tightening** -- new required field on a request or response schema (needs an SDK model update; breaking for the SDK if it's a response the client already parses without that field)
- **removal** -- path/schema/field disappeared (needs deprecation handling, not a silent drop)
- **rename** -- looks like add+remove of similarly-shaped fields; confirm with a scoped `git diff` before treating as two unrelated changes

Record the classified diff in session memory capped at ~300 tokens -- do not carry the raw JSON or script output forward verbatim.

## Session Memory Schema

Maintain these fields in `/memories/session/` and update only what the current phase needs:

```text
task: heal-from-spec-diffs invocation context (base ref, PR if known)
spec_versions: old -> new (openapi.json / events.schema.json)
spec_diff_summary: <= 300 tokens, classified additive/tightening/removal/rename entries
research_summary: <= 400 tokens
plan_ref: /memories/session/plan.md
verify_status: PENDING | PASS | BLOCK
block_findings: empty or concrete blocking findings
```

## Phase 2: Research

Delegate to `deep-researcher` to map each classified change to affected SDK surface:
- changed component schema -> matching `src/teardrop/models/*.py` model(s)
- changed/added operation (method+path) -> matching `src/teardrop/client/*.py` mixin, and whether both `AsyncTeardropClient` and `TeardropClient` already expose it
- changed/added SSE event name -> `streaming/sse.py` `EVENT_*` constants and `streaming/__init__.py` exports

Treat [tests/test_spec_contract.py](tests/test_spec_contract.py) as ground truth, not just documentation: it programmatically asserts SDK operations == OpenAPI operations, response models cover the spec's required fields, and event names have streaming constants. A failing run of this file is proof the SDK is not yet healed for that slice. Note it only checks the SDK-covers-spec direction for required fields -- also check the reverse (SDK model requiring a field the spec doesn't) via `model_fields[k].is_required()` introspection through the project venv, per `/memories/repo/testing-notes.md`.

Also note any change implied only by a field's `description` (e.g. "True when X changed") that needs a docstring or behavior note, not just a type change.

Hard limits (mirrors `dev-cycle`): no more than 2 research rounds, 4 targeted searches, 5 file reads unless a real ambiguity remains.

## Phase 3: Plan

Use the same discipline as `dev-cycle`'s PLAN phase. Name the exact models/methods/mixins/docs/tests to touch; keep the plan additive and minimal; write it to `/memories/session/plan.md`.

Explicitly plan for, as applicable:
- model field additions/changes matching the new spec properties and required-ness
- new client method(s) for new operations, always with an `AsyncTeardropClient` + `TeardropClient` (sync mirror) pair
- new `EVENT_*` constants and barrel export for new SSE events
- doc updates to the matching `docs/<topic>.md` (see the Documentation table in `README.md`)
- `tests/test_spec_contract.py` passing, plus new/updated unit tests using the `mock_http` fixture pattern from `tests/conftest.py`

If a change is a **removal** or **rename**, plan a backward-compatible SDK approach (keep the old field/method working, or clearly deprecated) instead of a silent breaking change. If a true breaking removal on a published field/method is unavoidable, flag it explicitly for human sign-off rather than implementing it silently.

## Phase 4: Implement

Delegate to `speedy-coder`. Follow its Operating Map, Do-Not-Conflate Rules, and Required Co-Changes exactly (sync/async parity, barrel exports, `_raise_for_status` mapping, `_UNSET` vs `None` semantics, TTL cache boundaries, docs).

- Prefer additive/patch changes (new optional fields, new methods) over rewriting existing shapes; only change existing required-ness/types when the classified diff actually demands it.
- After the first substantive edit, run the narrowest relevant test file before continuing further edits.

## Phase 5: Verify

Always run, in this order, using the project venv (`venv\Scripts\python -m pytest ...` on Windows):
1. `tests/test_spec_contract.py` -- the authoritative automated proof the SDK now matches the spec. Must pass before declaring done.
2. Unit tests for every touched domain module (e.g. `tests/test_mcp_servers.py`, `tests/test_a2a.py`).
3. If the public surface changed (new/renamed method, model, exception, or event constant): the full unit suite (`-q`) plus `ruff check` / `ruff format --check`.

Delegate to `ruthless-critic-verifier` for a strict pass using its Teardrop SDK Review Checklist, with extra attention to the Correctness/public-API-contract and Testing sections. Output one of `PASS` / `BLOCK` / `PENDING` exactly as `dev-cycle` does; on `BLOCK`, retry PLAN once with the findings, then stop and ask the user if it blocks again.

## Phase 6: Final Report (always, capped under 600 tokens)

End every run with exactly this three-section Markdown report, regardless of how large the diff was. Keep it tight -- no raw JSON, no full test output, no full plan (those already live in session memory / test output if the user wants detail):

```markdown
## Spec Sync: <old-version> -> <new-version>

### Spec Changes
- <one line per classified change: additive/tightening/removal/rename>

### What Was Implemented
- <one line per concrete SDK edit: file/model/method/doc/test>
- <anything intentionally deferred/flagged for human sign-off, if any>

### Business Value
<1-3 sentences: what capability this unlocks, what breakage or drift it prevents, why it matters to SDK consumers>
```

If a PR (e.g. `actions/spec-update`) is open for this change, you may suggest posting this report as a PR comment, but do not post it yourself -- commenting on PRs requires explicit user confirmation.

## Token Economy Rules

- Never load the full `spec/openapi.json` into context; always go through [scripts/diff_openapi.py](./scripts/diff_openapi.py) or a `git diff` scoped with `grep -n` around one schema name.
- Carry the classified diff summary forward, not the raw script output or JSON.
- Prefer one narrow validation command over broad test sweeps until the touched domain stabilizes.
- Do not re-run full-repo exploration after RESEARCH unless the current mapping (schema -> model, operation -> client method) is proven wrong.
