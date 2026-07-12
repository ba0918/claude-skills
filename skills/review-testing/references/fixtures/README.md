# review-testing fixtures

各アンチパターンの positive（候補抽出すべき）/ negative（誤検出してはならない）の対。
検出述語は [../anti-pattern-detection.md](../anti-pattern-detection.md) が所有し、各述語からここへリンクしている。
レビュー実行時の回帰確認に使う。positive の最終 verdict は各 fixture の期待値に従う。
AP1〜AP4 は CONFIRMED、履歴だけを持つ AP5 は候補抽出後 UNCERTAIN が正解である。

| Anti-Pattern | positive | negative |
|--------------|----------|----------|
| AP1 モックの振る舞い検証 | `ap1-mock-behavior.positive.test.ts` | `ap1-mock-behavior.negative.test.ts` |
| AP2 テスト専用メソッド | `ap2-test-only-method.positive.ts` | `ap2-test-only-method.negative.ts` |
| AP3 理解しないモック | `ap3-mock-understanding.positive.test.ts` | `ap3-mock-understanding.negative.test.ts` |
| AP4 不完全なモック | `ap4-incomplete-mock.positive.test.ts` | `ap4-incomplete-mock.negative.test.ts` |
| AP5 後付けテスト | `ap5-tests-after-fact.positive.md` | `ap5-tests-after-fact.negative.md` |
