---
name: review-deps
description: A focused read-only review that treats manifests, lockfiles, and dependency diffs as first-class input and evaluates known vulnerabilities and supply chain signals. Use when the user says "review the dependencies", "look at the dependency vulnerabilities", "check the lockfile", "supply chain risk", "organize the npm audit output", "detect typosquats", "dependency health", or "review-deps". Its subject is the health of the dependencies, not test quality or code quality.
---

# Review: Dependency Health

A focused skill that reviews the health of dependency libraries from a continuous-health viewpoint.
For known vulnerabilities the machine (a scanner) is the source of truth; the agent's value lies in **correlation analysis**.
It treats the lockfiles, manifests, and dependency diffs that `codebase-review` structurally excludes as first-class input.

**In scope**: manifests (package.json / Cargo.toml, etc.), lockfiles, dependency update diffs, install scripts.
**Out of scope**: exhaustive attack scenarios (→ `attack-review`), test quality (→ `review-testing`),
application code quality (→ `codebase-review`).

## Contract (declare this first)

- **read-only**: operations that change dependencies — `npm audit fix`, `cargo update`, committing a regenerated lockfile — are forbidden.
  Emit them as findings and hand the fixing over to an existing fix-oriented workflow.
  **Writing anything into the directory under review is also entirely forbidden** (this covers not only dependency changes but also
  creating scanner output files, temporary files, or logs inside the target tree). Always redirect scanner stdout/stderr to a working area
  outside the target (a scratch directory). Compliance with read-only is judged not by "whether the report declared it"
  but by "whether the target directory's state is unchanged before and after the run" — leaving a temporary file behind is a violation too.
- **The machine is the source of truth, the agent supplies correlation**: for known facts (advisory matching, checksums, signature verification) adopt only the results of the scanner and
  of machine verification. **The agent must never "read and judge" the validity of a hash or a signature.**
  The agent owns the correlations a scanner cannot produce: dependency paths, reachability, dev/prod, and the meaning of a diff.
- **Do not produce an overall score**: never emit a score of the "dependency health: 80 points" kind. The deliverables are findings and a
  [coverage ledger](../shared/references/coverage-ledger.md).
- **Three-way verdict**: verify every finding with the
  CONFIRMED / FALSE_POSITIVE / UNCERTAIN values of
  [severity-and-verdicts.md](../shared/references/severity-and-verdicts.md).
- **Always record the evaluated range in a ledger**: report the areas the scanner could confirm as `reviewed`, the dependency groups you put out of scope as `skipped`,
  the areas you cannot see because a scanner is missing, the network is unavailable, or registry metadata is absent as `unsupported`,
  and the areas where a candidate exists but the evidence is insufficient as `inconclusive`, in the form defined by
  [coverage-ledger.md](../shared/references/coverage-ledger.md).

## Division of Roles

| Owner | Area | Basis |
|------|------|------|
| **Scanner (source of truth)** | Advisory matching for known vulnerabilities, checksum / integrity verification | [references/scanner-integration.md](references/scanner-integration.md) |
| **Agent (correlation)** | Prioritization (dev/prod, reachability), interpreting install scripts, lockfile diff anomalies, typosquatting, maintainer handover | [references/supply-chain-signals.md](references/supply-chain-signals.md) |

The agent prioritizes the advisories the scanner emitted using context such as "this dependency is dev-only" or "it is reachable only from a test path".
In an environment without a scanner, matching against known vulnerabilities is `unsupported` (the agent does not substitute for it).

**Ownership of severity**: the judgment of whether a vulnerability **exists** belongs to the scanner and is never overturned. The **severity** of a finding
(BLOCK/WARN/INFO), by contrast, is decided by the agent as a correlation judgment that layers reachability and dev/prod on top of that existence.
The mapping rule from the scanner's severity labels and the grounds for adjusting it follow
the "Severity mapping" section of [references/scanner-integration.md](references/scanner-integration.md).

## Workflow

1. **Identify the input**: collect the manifests, lockfiles, and dependency diffs. Determine the ecosystem (npm / cargo / pip / go, etc.).
2. **Run the scanner (graceful degradation)**: detect presence → run → interpret the structured output → mark `unsupported` when absent.
   The details and the prerequisites for isolated execution are in [references/scanner-integration.md](references/scanner-integration.md).
3. **Correlation analysis**: prioritize by layering dependency paths, reachability, and dev/prod on top of the scanner's advisories.
   Verify the signals from lockfile diffs, install scripts, typosquatting, and maintainer handover with the predicates in
   [references/supply-chain-signals.md](references/supply-chain-signals.md).
4. **Three-way verdict**: assign each candidate to CONFIRMED / FALSE_POSITIVE / UNCERTAIN. State the limits of what could not be detected.
5. **Report**: emit findings plus the coverage ledger in the form defined by [references/report-template.md](references/report-template.md).

## Security

- **Run the scanner on the premise that install scripts are not executed**: re-resolving or scanning dependencies can execute install scripts such as
  postinstall. scanner-integration.md makes script disabling (the equivalent of `--ignore-scripts`) and isolated execution a prerequisite.
  When they cannot be disabled, do not run that area and fall back to `unsupported`.
- **Do not let secrets leak into the report**: never transcribe registry credentials, tokens, or environment variables into the evidence for a finding.
- **Do not delegate the validity of a hash or signature to the agent**: adopt only the results of machine verification (a scanner, or regeneration in a clean environment).
