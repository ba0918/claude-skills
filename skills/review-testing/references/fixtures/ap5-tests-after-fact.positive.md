# AP5 POSITIVE — TDD 逸脱の候補（判定は UNCERTAIN 止まり）

## シナリオ

- コミット順: `feat: add discount calc`（実装のみ、テストなし）→ 3 コミット後に
  `test: add discount tests`（テスト追加）。
- cycle の RED/GREEN 実行ログは**存在しない**。

## 期待される扱い

- git 履歴だけが根拠なので **UNCERTAIN**（squash / rebase で順序は崩れうる）。
- CONFIRMED に昇格するには cycle の RED/GREEN 実行ログが必要。
- 「現在このテストが有効か」は別軸として層 1・層 2 で正当に評価する（後付けでも有効なら価値がある）。
