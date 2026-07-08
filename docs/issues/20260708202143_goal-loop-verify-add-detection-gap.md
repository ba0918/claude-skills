---
title: goal-loop: cmd_verify が oracle ディレクトリへの追加ファイルを検出せず oracle-gaming の抜け道が残る
status: open
created: 2026-07-08 20:21:43
tags: goal-loop,bug,security,oracle-gaming
source: codex-sync（goal-loop の Codex 移植）中の Codex 敵対レビューが検出
---

## 概要

`skills/goal-loop/scripts/goal_loop.py` の CLI `verify`（`cmd_verify`）が、lock 後に oracle ディレクトリ配下へ**新規追加されたファイルを検出しない**。これは共有契約 `skills/shared/references/convergence-pattern.md` の「変更・削除・**追加**をすべて検出」「oracle_tampered で即 halt」という宣言と矛盾し、oracle-gaming（テスト・検証定義を弱めて合格する）の抜け道を残す。

**Codex 版（`codex-skills/goal-loop/`）は goal_loop.py を symlink で共有しているため、本バグは Claude / Codex 両方に影響する。** 本 issue は Claude 側スクリプトの修正として追跡する（移植では発見バグを修正しない原則に従い、issue 化のみ）。

## 根本原因（該当箇所）

`skills/goal-loop/scripts/goal_loop.py` `cmd_verify`（およそ L197-201）:

```python
current: dict[str, str] = {}
for path in manifest:          # ← manifest に記録済みのパスだけを走査
    p = Path(path)
    if p.exists():
        current[path] = hashlib.sha256(p.read_bytes()).hexdigest()
```

- `lock`（`_collect_paths`）はディレクトリを `rglob("*")` で再帰展開して manifest に個別ファイルとして記録する。
- しかし `verify` は `current` を **manifest のキーからのみ**再構築する。lock 後にディレクトリへ置かれた新規ファイル（manifest に無いキー）は `current` に入らないため、純関数 `verify_oracle_integrity`（追加検出ロジック自体は正しく、`test_added_file_is_tampered` で担保済み）に「追加」として渡らない。
- 結果: 変更・削除は検出できるが、**新規追加は CLI 経路で検出できない**。

## 攻撃シナリオ（oracle-gaming）

oracle が `pytest tests/` の場合、implementer（または誤動作）が lock 後に `tests/conftest.py`（autouse fixture で失敗を握りつぶす）や pytest 設定ファイルを**新規追加**すると、oracle は「合格」するが verify は追加を見逃す。maker/checker 分離とハッシュロックの安全性が破れる。

## 受け入れ条件

- `cmd_verify` が oracle の入力 root（特にディレクトリ）を metadata として manifest に保存し、verify 時に root を**再走査**して current 集合を再構築する（`_collect_paths` と同じ除外ルール = `__pycache__` / `*.pyc` を適用）。これにより追加ファイルが `verify_oracle_integrity` に渡り oracle_tampered として検出される。
- CLI レベルの**追加検出テスト**を `test_goal_loop.py` に追加する（現状の `test_added_file_is_tampered` は純関数のみ。CLI `cmd_verify` の end-to-end で追加が exit 2 になることを検証する）。
- `convergence-pattern.md` の宣言（追加検出）と実装が一致する。
- `python3 scripts/validate_repo.py` が合格する。
- Codex 版は goal_loop.py を symlink 共有しているため、Claude 側修正で自動的に反映される（追加作業不要）。ただし manifest フォーマットに metadata を足す場合、`codex-skills/goal-loop/SKILL.md` の lock/verify 手順に影響が無いか確認する。

## 備考

- 発見経路: codex-sync パイロットで確立した「Codex 版スキルを Codex 自身に敵対レビューさせる」プロセス。移植の副産物として Claude 側の実バグ（しかもセキュリティ関連）を掘り当てた3例目。
- 純関数 `verify_oracle_integrity` は正しいので、修正は `cmd_verify` の current 構築と manifest フォーマットに限定される見込み。

---

> **Note:** Do not include sensitive information (passwords, tokens, personal data, etc.) in this file.
