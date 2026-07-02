# Changelog

claude-skills プラグインのバージョン履歴。
`.claude-plugin/plugin.json` の `version` を bump したら、このファイルにエントリを追加すること
（マーケットプレイスがスキル変更を認識するのは version bump 時のみ）。

## 1.22.0

brainstorm skill empirically tuned (4 iterations, dispatch-based evaluation). Session Workflow: step numbering fixed (a2 → b with cascaded rename of sub-steps b→c→d→e→f→g, loop-exit step 4→5), stuck-hint placement locked to response body head (hint → normal answer → Codex section order), Codex prompt `{summary}` first-turn handling specified (`（最初のターン、履歴なし）`), Codex failure conditions expanded (Agent tool unavailable / timeout / empty response all explicit). Plan Workflow: Title/Summary provenance declared (kebab-title from idea-status link text, Summary from `## Summary` section), plan-create output path documented (`docs/plans/{new_timestamp}_{kebab-title}.md`), Step 5/6 reordered to move-first then status-update in archives/, Step 4.5 Skip Step 7 made explicit (cycle produces own completion log). Resume Workflow cross-reference corrected (steps 2-3f → 4a-4g). Mojibake (U+FFFD replacement chars in simplify-invert bullet) removed.

## 1.21.0

Codex CLI edition of handoff skill added under codex-skills/handoff/. Same save/restore/list workflows as the Claude Code version, rewritten for Codex native tools (apply_patch for file creation, shell for cat/rm/date/git, send_message for user output). Headless end-to-end: no request_user_input, no shell redirects for file writes. Handoff skill itself was empirically tuned (3 iterations, dispatch-based evaluation) before porting: status vocabulary locked to 3 values, absolute-path example fixed, restore summary templated, list extraction rules specified, git-less fallback (branch: (none)) added. Both editions share identical frontmatter structure so handoff files are cross-compatible.

## 1.20.0

New mockup-diff skill: visual diff detection between approved mockup HTML and running app. Phase 0 SETUP auto-generates a tailored Playwright comparison script per project (Tauri, Next.js, Vite, etc.) instead of hardcoded framework-specific logic. Captures screenshots of both mockup and app, enables LLM-driven visual comparison, diff analysis, code fix, and verification loop. Complements design-validate (token compliance) as the last-mile implementation quality gate.

## 1.19.0

Mockup Workflow v2: schema-based mockup generation with auto-lint (DL001-204) and Base Design approval gate. Feedback loop for iterating tokens/catalog/page-schema until human approval, then all subsequent validation is mechanical. Baseline confirmed via approval.json + screenshots.

## 1.18.0

Design-guide v2: mechanical verification for design systems. 5 new skills: design-scaffold (DESIGN.md → tokens.json + tokens.css + catalog + pages + layout-rules + rubric), design-generate (constrained page generation from page-defs + catalog), design-validate (multi-stage gate: lint → visual regression → rubric judge with weighted scoring), design-lint (14 rules: DL001-006 tokens, DL101-103 components, DL201-204 pages). Human-in-the-Loop Once: single base design approval → all subsequent validation is mechanical. Shared design-system-contract.md.

## 1.17.0

New TDD, systematic-debugging, and problem-solving skills. TDD contract and verification gate shared references injected into cycle/iterate/commit. Testing anti-patterns rule for project-wide enforcement. Brainstorm now detects stuck keywords and suggests problem-solving tools. Skill-improve gains pressure-test analysis and guardrail-strengthening category.

## 1.16.0

New design-guide skill: interactive discovery-driven DESIGN.md generator. Binary-choice questions to structure vague design vision into concrete design tokens (Google Stitch format). Anti-pattern guardrails to avoid generic AI aesthetics. Session (create), Update (modify), and Mockup (token-strict HTML/React mockup generation) workflows.

## 1.15.0

New attack-review skill: attacker-perspective security review with 6 specialist agents + Codex. Risk-matrix-based threat classification (not scores). Server/client/full mode with auto-detection. Language-adaptive attack profiles (TS/JS, Python, Go, Rust, Dart, PHP, HTML/CSS). Shared language detection contract (lang-detect.md) for cross-skill reuse.

## 1.14.1

Phase 2.5 code review follow-ups for github-issue Polling Phase B: SKILL.md Polling Step 11 now explicitly references increment_retry + should_promote_to_permanent; TickResult schema lists all 7 fields per shared contract §7; list_ready early-termination guarantee documented; retry_count / last_failed_at / run_id validation spec tightened; polling_interval vs tick_interval_loop_mode clarified. README refreshed to cover github-issue / handoff / polling commands and workflow quirks.

## 1.14.0

github-issue Polling Contract Unification (Phase B): Label adapter refactor to conform with shared polling-pattern.md contract. Split `claude-failed` into `claude-failed-transient` / `claude-failed-permanent` with backward-compatible dual-write alias. Atomic dual-write + verification + recovery marker. FS retry state replaces GitHub comment state. WARNING: Downgrade to 1.13.x is NOT supported — issues tagged with the new labels become invisible to older readers, causing silent data loss. Alias `claude-failed` will be removed in 1.16.0 (advance notice in 1.15.0).

## 1.13.x 以前

記録なし（releaseNotes の運用開始は 1.14.0 から）。
