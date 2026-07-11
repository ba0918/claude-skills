# review-deps fixtures

各サプライチェーン信号の positive（検出すべき）/ negative（誤検出してはならない）の対。
検出述語は [../supply-chain-signals.md](../supply-chain-signals.md) が所有し、各述語からここへリンクしている。
既知脆弱性照合は scanner が正本のため、ここには scanner が出せない相関的信号の fixture のみを置く。

| Signal | positive | negative |
|--------|----------|----------|
| lockfile diff 異常 | `lockfile-anomaly.positive.json` | `lockfile-anomaly.negative.json` |
| install script | `install-script.positive.json` | `install-script.negative.json` |
| typosquat | `typosquat.positive.json` | `typosquat.negative.json` |
