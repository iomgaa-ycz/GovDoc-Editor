---
name: subagent-driven-development
description: Execute an implementation plan by delegating each task to Codex (via the codex-plugin-cc plugin) and reviewing its work with three-stage Claude Code subagent reviews — spec compliance, functional quality, then code style.
---

# Subagent-Driven Development

## Overview

Execute a plan by delegating each task to a **Codex** session (through the `codex-plugin-cc` plugin) and reviewing every result with three stages of Claude Code subagent review: **spec compliance** first, then **functional quality**, then **code style**.

**Why a cross-provider split:** Claude Code is the controller. Codex is the implementer. Claude Code subagents are the reviewers. The implementer and the reviewer come from different model families and different providers — code is never graded by the same model that wrote it. This eliminates the self-evaluation blind spot that single-model loops suffer from, and it gives the controller a clean, isolated context per task without spending its own context window on implementation details.

**Core principle:** Fresh Codex session per task + three-stage Claude review (spec, functional quality, style) = high quality, fast iteration.

**Continuous execution:** Do not pause to check in with your human partner between tasks. Execute all tasks from the plan without stopping. The only reasons to stop are: BLOCKED status you cannot resolve, ambiguity that genuinely prevents progress, or all tasks complete.

<HARD-GATE>
**Codex-only implementation.** ALL implementation work MUST go through Codex via `/codex:rescue`. Do NOT use the Agent tool, Claude Code subagents, or inline code edits as a substitute for Codex implementation. Claude Code subagents are ONLY permitted as reviewers (steps 5/6/7), NEVER as implementers. If Codex is unavailable or blocked, STOP and escalate to the user — do NOT fall back to alternative implementation methods.
</HARD-GATE>

<HARD-GATE>
**Mandatory three-stage review.** After EVERY task's implementation passes the automated quality gate, ALL THREE review stages MUST execute in order: (1) spec compliance review, (2) functional quality review, (3) code style review. No stage may be skipped, regardless of task size, perceived simplicity, or mechanical nature. "Too simple to review" is not a valid reason — simple tasks are where regressions hide. The only exception is if the user explicitly requests skipping a review stage for a specific task.
</HARD-GATE>

<HARD-GATE>
**Mandatory persistent task tracking.** After reading the plan (Step 1), you MUST call `TaskCreate` for EVERY task extracted from the plan BEFORE dispatching any Codex implementer. After each task passes all reviews (Step 8), you MUST call `TaskUpdate` to mark it `completed`. Violations: dispatching Codex without TaskCreate entries existing, marking a task complete without calling TaskUpdate, skipping TaskCreate because "the plan file already has checkboxes." The plan file is a spec — `TaskCreate` is the persistent execution tracker that survives terminal restarts.
</HARD-GATE>

## When to use

```
digraph when_to_use {
  "Have an implementation plan?" [shape=diamond];
  "Tasks mostly independent?"    [shape=diamond];
  "subagent-driven-development"  [shape=box style=filled fillcolor=lightgreen];
  "Brainstorm or decompose first" [shape=box];

  "Have an implementation plan?" -> "Tasks mostly independent?" [label="yes"];
  "Have an implementation plan?" -> "Brainstorm or decompose first" [label="no"];
  "Tasks mostly independent?"   -> "subagent-driven-development"  [label="yes"];
  "Tasks mostly independent?"   -> "Brainstorm or decompose first" [label="no — tightly coupled"];
}
```

This skill assumes you are running inside **Claude Code** with the `codex-plugin-cc` plugin installed. It is the only supported harness.

## Prerequisites

Before invoking this skill, verify the Codex plugin is installed and ready:

```
/plugin marketplace add openai/codex-plugin-cc
/plugin install codex@openai-codex
/reload-plugins
/codex:setup
```

`/codex:setup` will report "Codex is ready" when authentication and the local Codex CLI are good to go. If it is not ready, stop and tell the user — this skill cannot proceed without a working Codex plugin.

### Recommended Codex configuration

Drop a `.codex/config.toml` at the repository root (or in `~/.codex/config.toml` for user-level defaults) so every dispatched Codex session uses the strongest model and the highest reasoning effort:

```toml
# .codex/config.toml
model = "gpt-5.4"
model_reasoning_effort = "high"
```

You can still override per-dispatch with `--model` and `--effort` flags if a specific task genuinely warrants a different setting, but the default for this skill is **gpt-5.4 at high effort**. Implementer quality is the bottleneck for the whole loop; do not save tokens here.

## tmux execution policy

All experiment scripts, long-running tests, training runs, evaluation runs, and any command expected to take longer than 30 seconds **must** be executed inside a tmux session. This allows the human operator to attach and monitor progress at any time.

**Naming convention**: `sdd-task<N>-<short-description>` (e.g., `sdd-task3-train`, `sdd-task5-eval`)

**How to run**:
```bash
# Create a tmux session and run the command
tmux new-session -d -s sdd-task<N>-<name> "<command>; echo '=== DONE ==='; sleep 86400"

# Poll for status
tmux capture-pane -t sdd-task<N>-<name> -p | tail -20

# Human attaches to inspect
tmux attach -t sdd-task<N>-<name>
```

**Scope — when tmux is required**:
- Experiment scripts (`scripts/*.sh`) run by the Codex implementer: the implementer prompt explicitly requires tmux
- pytest execution in the automated quality gate (Step 4.5) when tests are expected to exceed 30 seconds
- Any global run produced by a sub-task (training, evaluation, etc.)

**Forbidden**: Running long-lived commands directly in the foreground shell without tmux.

**Handoff to harness-eval**: If a sub-task has already completed a global run inside tmux and written results to `results/harness.db`, the subsequent harness-eval (Step 10) will detect the existing record and reuse it — no redundant re-run.

## Workflow

```
digraph workflow {
  "Read plan, extract all tasks with full text, note context, create TaskCreate entries" [shape=box];
  "Build/update knowledge graph\n(graphify . --update)" [shape=box];

  "Dispatch Codex implementer (/codex:rescue --fresh with ./codex-implementer-prompt.md)" [shape=box];
  "Codex reports STATUS"   [shape=diamond];
  "Provide missing context, re-dispatch with --resume" [shape=box];
  "Escalate / re-plan / upgrade effort" [shape=box];

  "Dispatch spec compliance reviewer subagent (./spec-reviewer-prompt.md)" [shape=box];
  "Spec reviewer approves?" [shape=diamond];
  "Fix spec gaps via /codex:rescue --resume" [shape=box];

  "Dispatch code quality reviewer subagent (./code-quality-reviewer-prompt.md)" [shape=box];
  "Quality reviewer approves?" [shape=diamond];
  "Fix quality issues via /codex:rescue --resume" [shape=box];

  "Dispatch code style reviewer subagent (./code-style-reviewer-prompt.md)" [shape=box];
  "Style reviewer approves?" [shape=diamond];
  "Fix style issues via /codex:rescue --resume" [shape=box];

  "Mark task complete via TaskUpdate" [shape=box];
  "More tasks remain?" [shape=diamond];

  "Dispatch final whole-implementation reviewer subagent" [shape=box];
  "Regenerate knowledge graph\n(graphify . --update)" [shape=box];
  "Use superpowers:finishing-a-development-branch" [shape=box style=filled fillcolor=lightgreen];

  "Read plan, extract all tasks with full text, note context, create TaskCreate entries" -> "Build/update knowledge graph\n(graphify . --update)";
  "Build/update knowledge graph\n(graphify . --update)" -> "Dispatch Codex implementer (/codex:rescue --fresh with ./codex-implementer-prompt.md)";
  "Dispatch Codex implementer (/codex:rescue --fresh with ./codex-implementer-prompt.md)" -> "Codex reports STATUS";

  "Automated Quality Gate\n(ruff/pytest/radon)" [shape=box];
  "Gate passes?" [shape=diamond];
  "Fix gate issues via /codex:rescue --resume" [shape=box];

  "Codex reports STATUS" -> "Automated Quality Gate\n(ruff/pytest/radon)" [label="DONE / DONE_WITH_CONCERNS"];
  "Automated Quality Gate\n(ruff/pytest/radon)" -> "Gate passes?";
  "Gate passes?" -> "Dispatch spec compliance reviewer subagent (./spec-reviewer-prompt.md)" [label="yes"];
  "Gate passes?" -> "Fix gate issues via /codex:rescue --resume" [label="no (max 2 retries)"];
  "Fix gate issues via /codex:rescue --resume" -> "Automated Quality Gate\n(ruff/pytest/radon)";
  "Codex reports STATUS" -> "Provide missing context, re-dispatch with --resume" [label="NEEDS_CONTEXT"];
  "Codex reports STATUS" -> "Escalate / re-plan / upgrade effort" [label="BLOCKED"];
  "Provide missing context, re-dispatch with --resume" -> "Codex reports STATUS";

  "Dispatch spec compliance reviewer subagent (./spec-reviewer-prompt.md)" -> "Spec reviewer approves?";
  "Spec reviewer approves?" -> "Fix spec gaps via /codex:rescue --resume" [label="no"];
  "Fix spec gaps via /codex:rescue --resume" -> "Dispatch spec compliance reviewer subagent (./spec-reviewer-prompt.md)";
  "Spec reviewer approves?" -> "Dispatch code quality reviewer subagent (./code-quality-reviewer-prompt.md)" [label="yes"];

  "Dispatch code quality reviewer subagent (./code-quality-reviewer-prompt.md)" -> "Quality reviewer approves?";
  "Quality reviewer approves?" -> "Fix quality issues via /codex:rescue --resume" [label="no"];
  "Fix quality issues via /codex:rescue --resume" -> "Dispatch code quality reviewer subagent (./code-quality-reviewer-prompt.md)";
  "Quality reviewer approves?" -> "Dispatch code style reviewer subagent (./code-style-reviewer-prompt.md)" [label="yes"];

  "Dispatch code style reviewer subagent (./code-style-reviewer-prompt.md)" -> "Style reviewer approves?";
  "Style reviewer approves?" -> "Fix style issues via /codex:rescue --resume" [label="no"];
  "Fix style issues via /codex:rescue --resume" -> "Dispatch code style reviewer subagent (./code-style-reviewer-prompt.md)";
  "Style reviewer approves?" -> "Mark task complete via TaskUpdate" [label="yes"];

  "Mark task complete via TaskUpdate" -> "More tasks remain?";
  "More tasks remain?" -> "Dispatch Codex implementer (/codex:rescue --fresh with ./codex-implementer-prompt.md)" [label="yes"];
  "More tasks remain?" -> "Dispatch final whole-implementation reviewer subagent" [label="no"];
  "Dispatch final whole-implementation reviewer subagent" -> "Regenerate knowledge graph\n(graphify . --update)";
  "Regenerate knowledge graph\n(graphify . --update)" -> "Use superpowers:finishing-a-development-branch";
}
```

### 1. Read the plan once

Read the plan file once. Extract every task's full text and its surrounding context. Call `TaskCreate` for every task — this creates the persistent task list that survives terminal restarts and tracks execution progress. After this, the plan file is not read again — the controller passes full task text into each Codex dispatch (Codex must not be sent a file reference to chase).

### 1.5 Build/update knowledge graph

Before dispatching the first Codex implementer, ensure the knowledge graph is current so Codex can consult it for structural context.

**Prerequisite:** Graphify is installed globally (`pip install graphifyy && graphify install`). If not installed, skip this step and remove the Knowledge Graph section from the implementer prompt.

**Run:**

```bash
# Update graph for code directories (tree-sitter only, no API calls)
graphify . --update
```

`--update` only re-extracts changed files since the last run, so it's fast on subsequent calls. The output goes to `.graphify/` at the project root.

**What Codex gets:** The implementer prompt (§ Project Conventions) tells Codex to check `.graphify/GRAPH_REPORT.md` and use `graphify query` / `graphify path` / `graphify explain` for context. This replaces blind file-reading with structure-aware navigation.

**When to skip:** If the project has no code yet (greenfield first task), skip — there's nothing to graph.

### 2. Dispatch the Codex implementer

For each new task, dispatch with:

```
/codex:rescue --fresh --background <prompt body from ./codex-implementer-prompt.md>
```

- `--fresh` starts a clean Codex session — this is the "fresh subagent per task" principle, now realized as a fresh Codex thread per task. **Always use `--fresh` for the first dispatch of a new task.**
- `--background` is recommended: a high-effort gpt-5.4 implementation can run for many minutes, and the controller should not block on it. Use `/codex:status` to check progress and `/codex:result` to fetch the final output.
- For quick mechanical tasks where you'd rather block and move on, `--wait` is fine.
- Do **not** pass `--model` or `--effort` per-call unless overriding the `.codex/config.toml` defaults on purpose.

The prompt template (`./codex-implementer-prompt.md`) embeds the full task text, scene-setting context, the self-review checklist, escalation guidance, and the required structured-output footer that produces the STATUS signal described in §4.

### 3. Iterate on the same task with `--resume`

When the spec reviewer or quality reviewer finds something to fix, dispatch the fix back to **the same Codex session**:

```
/codex:rescue --resume --background <fix instructions + reviewer feedback>
```

`--resume` preserves the session that did the original implementation, so Codex still has all the context about what it built and why. Switching back to `--fresh` mid-task wastes tokens and invites regressions.

Only switch to `--fresh` when starting the **next** task in the plan.

### 4. Handle Codex status signals

Codex is instructed (by `./codex-implementer-prompt.md`) to terminate its output with a structured `STATUS` block. The four statuses, and how to handle each:

- **DONE** — Proceed to spec compliance review.
- **DONE_WITH_CONCERNS** — Codex completed the work but flagged doubts. Read the concerns before proceeding.
  - If the concerns are about correctness or scope, address them (via `--resume`) before review.
  - If they're observations (e.g., "this file is getting large"), note them and proceed to review.
- **NEEDS_CONTEXT** — Codex needs information that wasn't provided. Supply the missing context and re-dispatch with `--resume`.
- **BLOCKED** — Codex cannot complete the task. Assess the blocker:
  - Context problem → provide more context, re-dispatch with `--resume`.
  - Insufficient reasoning → re-dispatch with `--resume --effort xhigh` (or override `--model` upward).
  - Task too large → break it into smaller pieces, restart with `--fresh`.
  - Plan is wrong → escalate to the human.

If Codex's output is missing the structured `STATUS` block (e.g., it errored out, hit a usage limit, or just forgot), treat the missing status as `BLOCKED` and inspect `/codex:result` for the partial output.

### 4.5 Automated Quality Gate

After Codex reports `DONE` or `DONE_WITH_CONCERNS`, run automated tools on the changed files **before** dispatching any AI reviewer. This catches objective violations cheaply (seconds, no tokens) so reviewers can focus on judgment calls.

**Gate checklist (Controller runs these):**

```bash
# 1. Format check
ruff format --check <changed_files>

# 2. Lint check
ruff check <changed_files>

# 3. Cyclomatic complexity (block on grade C or worse)
radon cc <changed_files> -n C -s

# 4. Tests pass
pytest tests/ -x -q

# 5. Structural checks (grep-based)
# - No bare except: grep -rn 'except\s*:' or 'except Exception.*pass'
# - No files > 200 lines in core changes

# 6. Metrics regression check
# - Read Wiki schemas/ to find tables affected by changed files
# - If relevant tables exist in results/harness.db:
#   Query current metrics vs baseline from Wiki metrics/
#   Any regression = gate failure
```

**If any check fails:**
1. Collect all tool outputs into a single fix instruction.
2. Dispatch `/codex:rescue --resume --background <fix instruction with tool outputs>`.
3. Re-run the gate on the result.
4. Maximum 2 retries. If still failing after 2 retries, escalate to user.

**If all checks pass:** Proceed to spec compliance review.

**Note:** The format check (`ruff format --check`) can often be auto-fixed. If only formatting fails, the controller MAY run `ruff format <files>` directly and commit, skipping the round-trip to Codex.

### 5. Spec compliance review

After the quality gate passes, dispatch a Claude Code subagent using the `Task` tool (general-purpose) with the prompt template at `./spec-reviewer-prompt.md`. This reviewer:

- Reads the actual code Codex wrote (via `git diff` and direct file reads) — **does not trust** Codex's self-report.
- Verifies the implementation matches the spec exactly: nothing missing, nothing extra, no misunderstandings.

If the reviewer flags issues, send them back to Codex via `/codex:rescue --resume` and re-run spec review on the result. Loop until approved. Do not accept "close enough."

### 6. Functional quality review

Only after spec compliance passes, dispatch a second Claude Code subagent with `./code-quality-reviewer-prompt.md`. This reviewer:

- Examines architecture, decomposition, plan conformance, file growth, naming, error handling, test quality, and obvious smells.
- Returns Strengths and Issues categorized as Critical / Important / Minor.

If issues are raised, send them back to Codex via `/codex:rescue --resume` and re-run quality review. Loop until approved.

### 7. Code style review

Only after functional quality review passes, dispatch a third Claude Code subagent with `./code-style-reviewer-prompt.md`. This reviewer:

- Evaluates code form and style: over-engineering, YAGNI violations, naming clarity, comment quality, unnecessary abstraction.
- Does NOT re-check architecture or functional correctness (already verified).
- Returns Important and Minor issues only (no Critical category — that's for the functional reviewer).

If issues are raised, send them back to Codex via `/codex:rescue --resume` and re-run style review. Loop until approved.

### 8. Mark the task complete and continue

Once all required reviewers approve, call `TaskUpdate` to mark the task `completed` and move to the next task — back to step 2 with `--fresh`.

### 9. Final whole-implementation review

After **all** tasks pass, dispatch one more Claude Code subagent: a whole-implementation reviewer. Give it the full set of git SHAs from this branch plus the original plan, and have it look across task boundaries for:

- Integration mistakes that no per-task review could catch (interfaces that drift between tasks, duplicated logic across files, dead code from earlier tasks).
- Plan coverage as a whole: are there any spec requirements that landed in no task?
- Cross-cutting concerns (logging, config, error paths, test layout) consistency.

You can reuse `./code-quality-reviewer-prompt.md` for this pass, but expand the scope from "this task's commits" to "the entire branch since plan execution started."

Then proceed to Step 10.

### 10. Harness evaluation

After the final whole-implementation review passes, invoke the `harness-eval` skill:

```
/harness-eval
```

- **Passes** → Proceed to Step 11.
- **Fails** → Read the diagnosis from the harness-eval output. Identify which task(s) need iteration. Return to Step 2 with `--fresh` for the relevant task, incorporating the diagnosis into the Codex prompt.

### 11. Regenerate knowledge graph

After harness evaluation passes, regenerate the knowledge graph so it reflects all code changes from the entire plan execution:

```bash
graphify . --update
```

This keeps `.graphify/` in sync with the final codebase state. Future skill invocations (on subsequent plans or branches) will start from an accurate graph.

Then proceed to `superpowers:finishing-a-development-branch`.

**When to skip:** If Step 1.5 was skipped (Graphify not installed), skip this too.

## Model selection

Implementer (Codex side) — **default to gpt-5.4 at high effort.** This is configured in `.codex/config.toml`. Per-task overrides:

- Truly trivial mechanical edits (rename, one-line config) → can drop to a smaller Codex model with `--model` if usage budget is a real concern. Otherwise, do not bother.
- Architecturally tricky tasks → keep gpt-5.4 and bump to `--effort xhigh`.

Reviewer (Claude Code side) — let Claude Code pick its default model. For the final whole-implementation review, dispatch with the most capable Claude model available in your environment.

Principle: implementer quality compounds across the review loop. A weak implementer turns the reviewers into a remediation engine and burns more tokens overall than a strong implementer would. Save costs by reducing review iterations, not by weakening the writer.

## Worked example

```
You: I'm using Subagent-Driven Development to execute this plan.

[Read plan file once: research-wiki/plans/feature-plan.md]
[Extract all 5 tasks with full text and context]
[TaskCreate for each task — persistent task list created]

[Build/update knowledge graph]
  graphify . --update
  → .graphify/GRAPH_REPORT.md updated (3 communities, 12 god nodes)

--- Task 1: Hook installation script ---
[Get Task 1 text and context (already extracted)]
[Dispatch Codex implementer]
  /codex:rescue --fresh --background <full prompt from ./codex-implementer-prompt.md>
[Poll /codex:status; eventually /codex:result returns:]

Codex:
  - Implemented install-hook command
  - Added tests, 5/5 passing
  - Self-review: realized I missed the --force flag, added it
  - Committed (SHA abc123)
  ---
  STATUS: DONE
  COMMIT_SHAS: abc123
  NOTES: none
  ---

[Dispatch spec compliance reviewer subagent via Task tool with ./spec-reviewer-prompt.md]
Spec reviewer: ✅ Spec compliant — all requirements met, nothing extra

[Dispatch code quality reviewer subagent via Task tool with ./code-quality-reviewer-prompt.md]
Quality reviewer: Strengths — good test coverage, clean error handling. Issues — none. ✅ Approved.

[Dispatch code style reviewer subagent via Task tool with ./code-style-reviewer-prompt.md]
Style reviewer: Issues — none. ✅ Approved.

[TaskUpdate: Task 1 → completed]

--- Task 2: Recovery modes ---
[Dispatch Codex implementer with --fresh]

Codex:
  - Added verify/repair modes
  - 8/8 tests passing
  - Committed (SHA def456)
  ---
  STATUS: DONE
  COMMIT_SHAS: def456
  ---

[Spec reviewer]
Spec reviewer: ❌ Issues:
  - Missing: progress reporting (spec says "report every 100 items")
  - Extra:   added --json flag (not requested)

[Fix via /codex:rescue --resume --background "Remove the --json flag; add progress reporting every 100 items as the spec requires."]

Codex:
  - Removed --json flag
  - Added progress reporting at 100-item intervals
  - Committed (SHA def789)
  ---
  STATUS: DONE
  COMMIT_SHAS: def789
  ---

[Spec reviewer re-runs] ✅ Spec compliant now
[Quality reviewer] Issues (Important): magic number 100
[Fix via /codex:rescue --resume "Extract 100 into PROGRESS_INTERVAL constant."]
Codex: extracted constant, committed ghi012, STATUS: DONE
[Quality reviewer re-runs] ✅ Approved
[Style reviewer] Minor: rename PROGRESS_INTERVAL to RECOVERY_PROGRESS_INTERVAL for clarity
[Fix via /codex:rescue --resume "Rename PROGRESS_INTERVAL to RECOVERY_PROGRESS_INTERVAL for clarity."]
Codex: renamed constant, committed jkl345, STATUS: DONE
[Style reviewer re-runs] ✅ Approved

[TaskUpdate: Task 2 → completed]

... (Tasks 3–5 similarly) ...

[All tasks complete]
[Dispatch final whole-implementation reviewer subagent across all SHAs]
Final reviewer: ✅ No cross-task issues found.

[Regenerate knowledge graph]
  graphify . --update
  → .graphify/ updated with all new code from this plan

[Hand off to superpowers:finishing-a-development-branch]
```

## Companion files

- `./codex-implementer-prompt.md` — Prompt body for `/codex:rescue`.
- `./spec-reviewer-prompt.md` — Prompt body for the spec compliance reviewer subagent (Claude Code Task tool, general-purpose).
- `./code-quality-reviewer-prompt.md` — Prompt body for the functional quality reviewer subagent (Claude Code Task tool, general-purpose). Also reused for the final whole-implementation review.
- `./code-style-reviewer-prompt.md` — Prompt body for the code style reviewer subagent (Claude Code Task tool, general-purpose). Focuses on form/style rather than functional quality.

## Common mistakes

- **Forgetting `--fresh` on a new task.** Codex will then continue the previous task's thread and produce confused, context-polluted output.
- **Forgetting `--resume` on a fix.** Codex restarts cold and may undo or duplicate work it already did.
- **Trusting Codex's self-report.** Both reviewers must read real code and diffs. The spec reviewer prompt is explicit about this; respect it.
- **Stopping after each task to check in.** Don't. Execute continuously. Only stop for BLOCKED you can't resolve.
- **Reading the plan file from inside Codex.** Don't. Paste the task text directly into the Codex prompt — Codex should not be navigating filesystems looking for the plan.
- **Letting reviewers approve "close enough."** Iterate the loop. The whole point of the cross-provider split is that the reviewer has no incentive to be charitable.
- **Using Claude Code subagents as implementers instead of Codex.** The Agent tool is for reviewers only. Implementation MUST go through `/codex:rescue`. If you catch yourself writing `Agent(prompt="implement..."`, STOP — that is a violation.
- **Skipping review stages because the task "looks simple."** Every task gets all three reviews. Simple tasks are where regressions hide because nobody bothers to check. No exceptions unless the user explicitly waives a stage.
- **Marking a task complete before all three reviews pass.** The task is NOT complete until spec + quality + style reviewers all approve. Partial review = incomplete task.
- **Skipping `TaskCreate` / `TaskUpdate`.** The persistent task list is the execution tracker — without it, progress is lost on terminal restart. Call `TaskCreate` for every task in Step 1, `TaskUpdate` for every completion in Step 8. No exceptions.

## Wiki Integration

**Precondition**: `research-wiki/` directory exists (skip this section entirely if it does not).

**Trigger**: When executing a plan and the task produces knowledge worth preserving; skip mechanical changes such as pure renames.

**Output path**: Plan and review records are saved to `research-wiki/plans/` and `research-wiki/reviews/` instead of `docs/superpowers/plans/`.

**Steps**:
1. If the task produces reusable implementation knowledge, run `.claude/tools/research_wiki.py add_entity research-wiki/ --type plan --id <slug> --title "<task plan title>"` to create the plan entity
2. If the task includes useful review feedback, run `.claude/tools/research_wiki.py add_entity research-wiki/ --type review --id <slug> --title "<task review title>"` to create the review entity
3. Append the key decisions, reusable implementation notes, and accepted or rejected review items with reasons to the generated page
4. If the plan is related to a design, run `.claude/tools/research_wiki.py add_edge research-wiki/ --from "plan:<id>" --to "design:<id>" --type implements --evidence "..."`
5. If the review feedback changes a design or plan, run `.claude/tools/research_wiki.py add_edge research-wiki/ --from "review:<id>" --to "<target-type>:<id>" --type informs --evidence "..."`
6. Run `.claude/tools/research_wiki.py rebuild_index research-wiki/`
