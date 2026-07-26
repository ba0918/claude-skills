# Supply-Chain Signals — detection predicates and their limits

Detection predicates for the correlation-based supply chain signals a scanner cannot emit. Verdicts follow the
CONFIRMED / FALSE_POSITIVE / UNCERTAIN of
[severity-and-verdicts.md](../../shared/references/severity-and-verdicts.md), and areas that cannot be detected go into
`unsupported` / `inconclusive` in [coverage-ledger.md](../../shared/references/coverage-ledger.md).

Each predicate has a corresponding positive / negative pair in [fixtures](fixtures/) (for regression checking).

**The overarching principle**: the agent never reads and judges the validity of a hash or a signature. Only the result of
mechanical verification is adopted. The predicates in this file target "context-dependent anomalies a machine cannot rule on".

**Corroborating the evidence**: the concrete values written as a finding's evidence (the IOCs — fetch URL, write destination
path, environment variable name, resolved host, etc.) must be **transcribed accurately from the actual line of the target file**.
Never fill them in from memory, guesswork, or "the value it usually is". The write destination in particular changes the nature
of the threat depending on whether it is ephemeral or persistent (`/tmp` versus under `$HOME`), so corroborate it by quoting the
relevant line of setup.js or the like. For any item you cannot corroborate, never invent a concrete value — state "unconfirmed".

## Signal 1: lockfile diff anomaly

- **Candidate extraction**: in the lockfile diff, a resolved URL changed to something outside the registry (a different host,
  a git URL, a file: reference), an integrity hash changed while the version stayed the same, or transitives were swapped en masse without any direct dependency being added.
- **Evidence requirement**: show with the diff a "divergence between the manifest's intent and the lockfile's reality", such as the integrity changing under the same version specifier.
  Do not judge whether the integrity hash value itself is right or wrong — the evidence is the **mechanical fact** that "the hash changed for the same version".
- **Three-valued**: the divergence is shown in the diff → CONFIRMED / a legitimate reason can be explained (a registry migration, a change accompanying a version update) → FALSE_POSITIVE /
  the intent cannot be read from the diff alone → UNCERTAIN.
- **fixtures**: [positive](fixtures/lockfile-anomaly.positive.json) / [negative](fixtures/lockfile-anomaly.negative.json)

## Signal 2: install script (lifecycle script)

- **Candidate extraction**: lifecycle hooks in the manifest such as `postinstall` / `preinstall` / `install` (npm) or
  `build.rs` (cargo). Especially those involving external network access, an encoded payload, or executing another file.
- **Evidence requirement**: explain what the script's **contents** do, in a structured form filling in all 4 items below
  (if even one is missing, the evidence is insufficient and the finding is demoted to UNCERTAIN):
  1. **Fetch source** — what it pulls from outside (URL, host, the binary/code fetched). State "none" if there is none.
  2. **Write destination** — what it writes where (home directory, a system path, whether it grants the execute bit). State "none" if there is none.
  3. **Secrets referenced** — the environment variables, credentials, and keys it reads (never transcribe the values, only the names and whether they are sent out).
     When it enumerates and exfiltrates the whole environment via `process.env` or similar, write "all environment variables (individual names are not bounded by the code)".
     State "none" if there is none.
  4. **Commands executed** — subprocesses, eval, execution via chmod+x, and so on. State "none" if there is none.

  "Assigning meaning" is the agent's role. But never **run** the script to check (read it statically).
- **Three-valued**: dangerous behavior (data exfiltration, fetching arbitrary code) can be shown in the code → CONFIRMED /
  it can be explained as legitimate build processing (compiling a native module, etc.) → FALSE_POSITIVE /
  obfuscation makes the intent unreadable → UNCERTAIN (also recorded in the ledger as an `inconclusive` area).
- **fixtures**: [positive](fixtures/install-script.positive.json) / [negative](fixtures/install-script.negative.json)

## Signal 3: typosquat

- **Candidate extraction**: dependency names at a small edit distance from a well-known package name (`lodahs` vs `lodash`,
  scope spoofing such as `@types-node` vs `@types/node`, hyphen/underscore differences).
- **Evidence requirement**: show the difference from the legitimate package name, and that this dependency is not the legitimate one (a different maintainer, low download count, recently published).
  In an environment without registry metadata, all you can say is "the names are similar" → it stops at UNCERTAIN.
- **Three-valued**: a similar name plus a different origin can be shown → CONFIRMED / it is confirmed to be a legitimate scope or alias → FALSE_POSITIVE /
  name similarity only, with no metadata → UNCERTAIN.
- **fixtures**: [positive](fixtures/typosquat.positive.json) / [negative](fixtures/typosquat.negative.json)

## Signal 4: maintainer change / maintenance state (stating the limit)

- **Candidates**: a change of who holds publish rights within a short period, a sudden major update after a long dormancy, a sharp drop in the number of maintainers.
- **Limit**: these are **undecidable** without registry metadata (publish history, owner information).
  In an environment with no network or with private metadata, always put them into `unsupported`. The agent never marks them CONFIRMED on speculation.

## Limits of detection (always leave these in the ledger)

- The true intent of an obfuscated install script → `inconclusive`.
- Signals requiring registry metadata (confirming a typosquat's origin, maintainer changes) → `unsupported` without metadata.
- Without call-graph analysis, treat the reachability of a transitive dependency conservatively as "may be reachable" and avoid asserting otherwise.
