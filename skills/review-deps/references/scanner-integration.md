# Scanner Integration — running an ecosystem scanner, and degradation

The ecosystem scanner is the canon for matching known vulnerabilities. This file defines the graceful
degradation flow of "detect presence → run → interpret the structured output → unsupported when absent",
and the prerequisites for isolated execution.
Record the evaluation scope in [coverage-ledger.md](../../shared/references/coverage-ledger.md).

## Scanners by ecosystem

| Ecosystem | Scanner (example) | Output | Notes |
|-------------|--------------|------|------|
| npm / pnpm / yarn | `npm audit --json` / osv-scanner | JSON | lockfile required |
| Rust / cargo | `cargo audit --json` | JSON | RustSec advisory DB |
| Python | `pip-audit -f json` / osv-scanner | JSON | requirements / lock |
| Go | `govulncheck -json` / osv-scanner | JSON | includes reachability analysis |
| Generic | `osv-scanner --format json` | JSON | spans several ecosystems |

The concrete command names depend on the platform and the environment. What is defined here is the abstract
procedure: "run a scanner that matches against an advisory DB with a shell command, and interpret its structured output".

## The degradation flow

```
1. Detect presence: check whether the scanner binary and the advisory DB / network are available
     └ absent → put that match into `unsupported` in the coverage ledger (noting what would promote it). The agent never substitutes its own verdict
2. Run: determine the scanner's behavior class and run it in an environment satisfying the "isolated execution" conditions below
3. Interpret the structured output: read the JSON and extract advisory IDs, severities, affected versions, and fixed versions
4. Hand over to correlation: overlay dependency path, dev/prod, and reachability onto the extracted facts and prioritize
     (prioritization belongs to the agent; the scanner is the canon for whether a vulnerability exists)
```

- **Never rewrite the scanner's results**: the agent does not judge whether an advisory is true. If the scanner says
  "vulnerable", it is vulnerable; if it cannot report, it is `unsupported`. Noting the possibility of a false positive is fine, but never overturn the verdict.
- **No network**: in an environment with no access to the advisory DB, known-vulnerability matching does not hold → `unsupported`.
  If a locally cached DB exists, it is `reviewed` with a note that it reflects that snapshot (note the freshness).

## Isolated execution (do not run install scripts)

First classify the scanner into these 2 kinds. Do not decide from the command name alone — confirm from the help output, the official specification, or an isolated observation.

- **audit-only**: reads the existing manifest / lockfile and only matches against the advisory DB; performs no dependency resolution and runs no hooks.
- **re-resolving**: may fetch packages, resolve dependencies, and trigger build / lifecycle hooks.

The following are prerequisites for both.

- **Disable scripts**: a re-resolving scanner stops lifecycle scripts with the equivalent of `--ignore-scripts`. An audit-only
  scanner does not require that option if you can confirm from the specification or an isolated observation that it runs no hooks.
- **Isolation**: confine writes outside the target. Allow the network only to read the advisory DB / registry metadata, and
  never execute a package's install script or fetched artifacts. If you cannot restrict the destinations, use an offline
  cache / DB and note its freshness. If neither holds, it is `unsupported`.
- **Put the output outside the target tree**: the scanner's stdout/stderr, JSON output, and logs go **outside** the directory
  under review (a scratch working area). Redirecting into the target tree (running `> audit.json` and the like in the target
  directory, or pointing `--output` under it) violates the read-only contract. Redirecting while the current directory is still
  inside the target tree leaves temporary files behind, so always specify the output path as an absolute path outside the target.
- **When it cannot be disabled**: **do not run** that scan and fall back to `unsupported` (never run arbitrary code for the sake of a review).
- Static analysis of the lockfile / manifest (the predicates of [supply-chain-signals.md](supply-chain-signals.md)) does not
  execute code, so it holds even where a scanner is unavailable. It is the main force when no scanner is present.

## The minimum schema of the structured output (interpretation guidance)

The minimum items to pick out of the scanner JSON (the actual fields differ per scanner, so leave
"the fields that could not be interpreted" in [coverage-ledger.md](../../shared/references/coverage-ledger.md)):

- advisory ID (the unique key for matching)
- severity (the scanner's classification. The map to severity follows "Severity mapping" below)
- affected package name / version range / fixed version
- dependency path (direct / transitive. When the scanner does not emit it, the agent fills it in from the lockfile)

## Severity mapping (the scanner's classification → severity)

Map the scanner's severity labels (critical / high / moderate / low / info, etc.; the system differs per scanner) onto the
BLOCK / WARN / INFO of [severity-and-verdicts.md](../../shared/references/severity-and-verdicts.md).

**Ownership**: the verdict of "does a vulnerability exist" is canonical to the scanner and the agent never overturns it.
"Severity (BLOCK/WARN/INFO)", on the other hand, is a **correlation judgment overlaying reachability and dev/prod** on top of
existence, and the agent owns it. Use the scanner's severity label as **the starting point**, and note the reason whenever you adjust it.

**The default starting point** (before adjustment):

| Scanner severity | Starting severity |
|---------------|---------------|
| critical / high | BLOCK |
| moderate | WARN |
| low / info | INFO |

**Adjustment rules** (grounds for moving up or down from the starting point. Write the reason into the finding whenever applied):

- **A dev-only dependency confirmed unreachable from the prod runtime** → lower by one step (e.g. a critical devDependency → WARN).
  When unreachability cannot be confirmed, do not lower it (stay conservative).
- **Fires at install time** (postinstall, build.rs, etc.; runs on `install` even without being imported) → do not lower.
  It fires regardless of code reachability, so no dev/prod attenuation applies.
- **Arbitrary code execution, exfiltration of credentials, or known malware** → **fixed at BLOCK** regardless of the scanner severity (never lower).
- The absence of a fixed version (`fixAvailable=false`, etc.) is not a reason to raise the severity, but note it as hard to remediate.

When the severity cannot be mapped (the scanner emits its own labels, etc.), leave a note to that effect in
[coverage-ledger.md](../../shared/references/coverage-ledger.md), and use the nearest step of the starting-point table with a note.
