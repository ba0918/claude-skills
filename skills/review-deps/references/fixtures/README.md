# review-deps fixtures

For each supply chain signal, a pair of positive (must be detected) / negative (must not be a false positive).
The detection predicates are owned by [../supply-chain-signals.md](../supply-chain-signals.md), and each predicate links here.
Because the scanner is canonical for known-vulnerability matching, only fixtures for correlation signals a scanner cannot emit live here.

| Signal | positive | negative |
|--------|----------|----------|
| lockfile diff anomaly | `lockfile-anomaly.positive.json` | `lockfile-anomaly.negative.json` |
| install script | `install-script.positive.json` | `install-script.negative.json` |
| typosquat | `typosquat.positive.json` | `typosquat.negative.json` |
