# Report Template — review-deps

The output format for review-deps. **Do not emit an overall score.** The deliverable is
findings plus a [coverage ledger](../../shared/references/coverage-ledger.md) — both, always.
Finding severity and the 3-value verdict follow
[severity-and-verdicts.md](../../shared/references/severity-and-verdicts.md).

    # Dependency Health Review — {target}

    Scope: {manifest / lockfile / dependency diff}
    Ecosystem: {npm / cargo / pip / go / ...}
    Scanner: {the scanner that ran and its version, or "unavailable"}
    Contract: read-only / no overall score / findings + coverage ledger

## Findings

Every finding carries kind / severity / 3-value verdict / evidence / target. State explicitly whether it came from the scanner or from correlation.

| # | Kind | Severity | Verdict | Target (package@version) | Evidence |
|---|------|----------|---------|--------------------------|----------|
| 1 | scanner: known vulnerability | BLOCK | CONFIRMED | left-pad@1.0.0 | GHSA-xxxx (scanner output). Reachable from the prod path |
| 2 | correlation: install script | WARN | UNCERTAIN | build-tool@2.1.0 | The postinstall is obfuscated. Intent unclear from static reading |
| 3 | correlation: lockfile anomaly | WARN | CONFIRMED | ui-lib@3.0.0 | The integrity hash changed for the same version |

### Details (expand only what is both CONFIRMED and BLOCK)

- #1 left-pad@1.0.0 (GHSA-xxxx): the scanner reported a known vulnerability. The dependency path is prod (direct).
  Reachability: reached from the application's input handling. High priority.
  Fixing is out of scope for review-deps (hand off to a dependency update workflow).

## Coverage Ledger

This section is mandatory even with 0 findings.

| Target | Value | Reason / promotion condition |
|--------|-------|------------------------------|
| npm dependencies (N packages) | reviewed | Applied npm audit + static lockfile analysis |
| Known-vulnerability matching (cargo) | unsupported | cargo audit not installed. Installing it promotes this to reviewed |
| Maintainer handover | unsupported | No access to registry metadata. Determinable by re-running in an online environment |
| True intent of the obfuscated postinstall | inconclusive | Intent unclear from static reading. Dynamic analysis needs an isolated environment |

## Notes

- The scanner is the source of truth for whether a known vulnerability exists. The agent handled only prioritization and correlation.
- The agent did not judge the validity of hashes / signatures (only machine-verified results were adopted).
- Install scripts were not executed (static reading only / read-only).
