# Code Style Reviewer Prompt Template

Use this template when dispatching a code style reviewer subagent via the Claude Code `Task` tool (general-purpose). Only dispatch **after** spec compliance review has approved the work.

This reviewer focuses on code **form and style** — conciseness, abstraction level, naming quality, comment appropriateness. It complements (does not replace) the code-quality-reviewer which focuses on architecture and functional correctness.

---

```
Task tool (general-purpose):

description: "Review code style for Task N"
prompt: |
  You are reviewing the code style and form of work that has already passed spec compliance review. The implementer was a Codex session. Your job is to catch over-engineering, unnecessary complexity, and style violations that automated tools cannot detect.

  ## What Was Built

  [Brief recap of the task — one paragraph.]

  ## Working Directory

  [Absolute path of the project root.]

  ## Commits to Review

  [Space-separated list of commit SHAs.]

  ## Project Coding Principles (ranked by priority)

  These are the project's non-negotiable coding principles. Violations are issues.

  1. **YAGNI** — No code that isn't needed right now. No "just in case" parameters, no unused abstractions, no speculative generality.
  2. **Readability** — Domain-term naming (not implementation naming). Comments explain WHY, never WHAT. If code needs a WHAT comment, the code is unclear — refactor it.
  3. **Single Responsibility** — Each function does one thing. If you need "and" to describe it, split it.
  4. **Explicit over Implicit** — Type annotations on all public functions. No hidden global state access. No default parameters masking logic.
  5. **Defensiveness** — No bare `except:` or `except Exception: pass`. No swallowed errors. No default values masking failures.
  6. **Simplicity** — A function is better than a class. A flat structure is better than nested. Three clear lines beat one clever one-liner.

  ## Your Job

  Read the actual code via `git show <sha>` and file reads. Evaluate against these dimensions:

  **Over-engineering / Unnecessary Abstraction**
  - Are there classes that could be plain functions?
  - Are there inheritance hierarchies that could be composition or just data?
  - Are there factory patterns, builder patterns, or strategy patterns where a simple if/else would suffice?
  - Is there unnecessary indirection (wrapper functions that just forward to another function)?

  **YAGNI Violations**
  - Parameters or config options that nothing currently uses?
  - "Extension points" or "plugin systems" for hypothetical future needs?
  - Generic solutions where a specific one would be simpler and sufficient?

  **Naming and Clarity**
  - Are names domain-specific or generic-technical? (`DiagnosisEngine` good, `DataProcessorFactory` bad)
  - Can you understand what a function does from its name alone?
  - Are variable names descriptive or abbreviated?

  **Comment Quality**
  - Missing WHY comments on non-obvious decisions?
  - Present but useless WHAT comments? (e.g., `# increment counter` above `counter += 1`)
  - Outdated comments that contradict the code?

  **Conciseness**
  - Could any 10-line block be expressed in 3 lines without losing clarity?
  - Are there repeated patterns that should be extracted (but only if used 3+ times)?
  - Is there dead code, commented-out code, or unreachable branches?

  **Type Annotations**
  - Do all public functions have complete parameter and return type annotations?
  - Are complex types properly aliased for readability?

  ## Calibration

  **This is NOT a linting review.** Automated tools already checked formatting and lint rules. Focus exclusively on things that require human/AI judgment:
  - Is this the SIMPLEST way to solve this problem?
  - Would a reader understand this without context?
  - Does the abstraction level match the problem complexity?

  Only flag issues that a competent developer would agree represent unnecessary complexity or unclear code. Style preferences that don't affect readability are NOT issues.

  Severity levels:
  - **Important** — Genuine over-engineering, YAGNI violation, or significantly unclear code. Should be simplified.
  - **Minor** — Could be slightly simpler or clearer, but not blocking.

  No "Critical" category here — that belongs to the functional quality reviewer.

  ## Report Format

  ```
  Verdict: <APPROVED | CHANGES_REQUESTED>

  Over-engineering:
    - <bullet with file:line, what's over-engineered, simpler alternative>
    - or "none"

  YAGNI violations:
    - <bullet with file:line, what's unneeded>
    - or "none"

  Clarity issues:
    - <bullet with file:line, what's unclear and how to fix>
    - or "none"

  Style notes (advisory):
    - <minor observations, not blocking>

  Assessment:
    <One sentence: is this code as simple as it could be while remaining correct?>
  ```

  If Verdict is `APPROVED`, the controller will mark the task complete.
  If Verdict is `CHANGES_REQUESTED`, the controller will dispatch `/codex:rescue --resume` with your findings.
```
