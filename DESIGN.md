# DESIGN.md

> This file defines the design system for this project.
> AI coding agents MUST reference this file when generating or modifying any UI component.

**適用範囲**: このリポジトリが生成する唯一の UI である `brief` スキルの自己完結 HTML。
リポジトリ本体はスキル集（Markdown + Python）であり、他に UI を持たない。

**絶対制約**: 生成物は外部ネットワークへ一切アクセスしない。
Web フォント、CDN、外部アイコン、外部画像は使用禁止。フォントは OS に実在するものだけで組む。

## Visual Theme & Atmosphere

- **Mood:** 落ち着いて読める / 雑誌・編集的。日本の編集物（墨と生成り紙）の配色を土台に、
  長い日本語の解説文を数分間読み通せることを最優先する
- **Density:** spacious（ゆったり）。ただし索引の行間だけは一覧性のため詰める
- **Design philosophy:**
  装飾ではなく情報設計で可読性を作る。1 画面 1 フォーカス、索引と詳細の分離、
  初期表示ブロックの固定という制約自体が読みやすさを担保する。凝ったダッシュボードを作らない。
  色は意味を持つときだけ使う（地はミュート、警告だけ彩度を上げる）
- **Reference inspirations:**
  日本語の編集組版（明朝見出し × ゴシック本文 × 等幅コードの 3 書体コントラスト）、
  diff review 画面の意図別グループカード + 左カラーラベル

## Color Palette

| Role | Value | Usage |
|------|-------|-------|
| Primary | `#2C4A63` | 藍。リンク、フォーカスリング、アクティブ状態、主要アクション |
| Primary Hover | `#1F3648` | リンク・ボタンの hover |
| Secondary | `#6E6A62` | 補助ラベル、件数バッジ、セカンダリボタンの文字 |
| Accent | `#2C4A63` | Primary と同一。アクセントを増やさず藍 1 本に集約する |
| Background | `#FBFAF7` | 生成り。ページ背景 |
| Surface | `#FFFFFF` | カード背景、展開中の詳細領域 |
| Surface Alt | `#F4F2EC` | 交互行、節の区切り帯、閉じた折りたたみの地 |
| Error | `#A62B1F` | 検証失敗、破壊的操作 |
| Warning | `#C8442C` | 朱。要注意グループ、未決事項、未確認の主張 |
| Success | `#2F6B57` | 検証通過、確認済み |
| Text Primary | `#1A1917` | 墨。本文・見出し |
| Text Secondary | `#6E6A62` | 補助テキスト、ラベル、メタ情報 |
| Text Disabled | `#A29D93` | 非活性テキスト |
| Border | `#E4E0D7` | 罫線、カード枠、入力枠 |
| Focus Ring | `#2C4A63` | キーボードフォーカス表示 |
| Code Background | `#23211E` | 墨の暗地。コードブロック・diff 領域の背景 |
| Code Text | `#EAE6DC` | コードブロック上の文字 |
| Diff Added | `#8FBF9F` | コード暗地の上での追加行マーカー |
| Diff Removed | `#D98A7E` | コード暗地の上での削除行マーカー |

**色の使用規律:**

- 重要度・状態を**色だけで伝えない**。必ずテキストラベル（`要注意` / `未決` / `低リスク`）を併用する
- 藍・朱・深緑以外の色相を追加しない
- グレースケールのみに落とさない（生成りの暖味が地の性格を作っている）

### Dark Mode Overrides

**MVP では未定義**（意図的な決定）。4 view のうち 3 つが日本語の長文を読ませる用途であり、
基調を 1 本に絞って完成度を上げることを優先した。トークン化してあるため、
後から `.design/tokens.json` にダークパレットを追加するコストは小さい。

## Typography

| Level | Font Family | Size | Weight | Line Height | Letter Spacing |
|-------|------------|------|--------|-------------|---------------|
| Display | Heading (明朝) | 38px | 400 | 1.45 | 0.04em |
| H1 | Heading (明朝) | 30px | 400 | 1.5 | 0.03em |
| H2 | Heading (明朝) | 24px | 400 | 1.55 | 0.02em |
| H3 | Body (ゴシック) | 18px | 700 | 1.6 | — |
| H4 | Body (ゴシック) | 16px | 700 | 1.6 | — |
| Body | Body (ゴシック) | 16px | 400 | 1.85 | — |
| Body Small | Body (ゴシック) | 14px | 400 | 1.8 | — |
| Caption | Body (ゴシック) | 13px | 400 | 1.7 | 0.02em |
| Code | Code (等幅) | 14px | 400 | 1.7 | — |

- **Heading font:** ヒラギノ明朝 — `"Hiragino Mincho ProN", "HiraMinProN-W3", "Yu Mincho", "YuMincho", "BIZ UDPMincho", "Noto Serif JP", "Source Han Serif JP", serif`
- **Body font:** ヒラギノ角ゴ — `"Hiragino Kaku Gothic ProN", "Hiragino Sans", "Yu Gothic", "YuGothic", "BIZ UDPGothic", "Noto Sans JP", "Meiryo", sans-serif`
- **Code font:** SF Mono — `"SFMono-Regular", "SF Mono", Menlo, Consolas, "DejaVu Sans Mono", "Liberation Mono", monospace`

**タイポグラフィ規律:**

- ジャンプ率 Display / Body = 2.4 を維持する。見出しは 1 画面に 1 つ（`つまり` の 1 行）だけ
- **本文の行長を 40 全角（約 42rem）に制限する。** 画面幅いっぱいに伸ばさない
- 3 書体（明朝 / ゴシック / 等幅）のコントラストが唯一の書体的差別化手段である。
  Web フォントが使えない以上、ここを崩すと没個性になる
- 総称ファミリー（`sans-serif` / `serif` 単独）だけの指定を禁止する。必ず具体名を先に積む

## Component Stylings

### Buttons

| Variant | Background | Text | Border | Border Radius | Padding |
|---------|-----------|------|--------|---------------|---------|
| Primary | `#2C4A63` | `#FBFAF7` | none | 3px | 10px 20px |
| Secondary | transparent | `#2C4A63` | 1px solid `#2C4A63` | 3px | 10px 20px |
| Ghost | transparent | `#1A1917` | none | 3px | 8px 12px |
| Destructive | `#A62B1F` | `#FBFAF7` | none | 3px | 10px 20px |

**States:**

- Hover: 背景を Primary Hover へ、または地を `#FFFFFF` へ抜く。**opacity の変更だけで済ませない**
- Focus: `#2C4A63` 2px、offset 2px のリング
- Active: 1px 下方向に沈める（`translateY(1px)`）
- Disabled: `#A29D93` の文字、`cursor: not-allowed`

### Cards（グループカード）

- Border radius: 2px
- Background: 閉じた状態 `#F4F2EC` / 展開中 `#FFFFFF`
- Border: 1px solid `#E4E0D7`
- **Left rail: 4px の左ボーダー。** 色でグループの性格を示す
  （藍 = 通常 / 朱 = 要注意・未決 / 深緑 = 確認済み / `#A29D93` = 低リスク）
- Shadow: 閉じた状態は none。**展開中のカードだけ Level 1** を当てて「今見ているもの」を示す
- Padding: 24px
- Hover: left rail が 4px → 6px に伸び、地が `#FFFFFF` へ抜ける

### Badges（種別・リスク・件数）

- Border radius: **0px**（角を立ててラベル感を出す。カード・ボタンと明確に差別化する）
- Padding: 2px 8px
- Font: Caption 13px
- 種別バッジ: 地 `#F4F2EC`、文字 `#6E6A62`、1px solid `#E4E0D7`
- 警告バッジ: 地 `#C8442C`、文字 `#FBFAF7`
- 件数は数字のみを Secondary 色で置き、バッジにしない

### Code Blocks / Diff

- Border radius: 3px
- Background: `#23211E`、文字 `#EAE6DC`
- Padding: 16px 20px
- 追加行 `#8FBF9F` / 削除行 `#D98A7E` のマーカーを行頭に置き、**背景色だけで差分を示さない**
- 横方向は `overflow-x: auto`。ページ本体を横スクロールさせない

### Inputs

- Border radius: 3px
- Border: 1px solid `#E4E0D7`
- Padding: 10px 12px
- Focus: border-color `#2C4A63`、box-shadow `0 0 0 2px rgba(44,74,99,0.18)`
- Error: border-color `#A62B1F`
- Placeholder: `#A29D93`

### Navigation（グループ索引）

- Style: 縦積みリスト。**通し番号（01, 02, …）を本文カラムの左外にぶら下げる**（ハンギング）
- Background: `#FBFAF7`（地のまま。索引に別背景を敷かない）
- Active indicator: left rail の伸長 + 地の白抜き + 番号の色を `#2C4A63` へ
- Item padding: 12px 0（索引だけは行間を詰めて一覧性を確保する）

**この番号のハンギングが、本デザインで唯一の意図的な非対称要素**である。
完全対称グリッドを避けるための構造であり、削除しない。

## Layout Principles

- **Base unit:** 8px
- **Spacing scale:** 4, 8, 12, 16, 24, 32, 48, 64
- **Max content width:** 本文カラム 672px（42rem）/ ページコンテナ 768px
  （差分の 96px は番号ハンギング用の左余白帯）
- **Grid:** 単一カラム。多カラムグリッドを使わない
- **White space philosophy:**
  セクション間で余白に緩急をつける。要約 → 索引 → 詳細 → 確認質問の 4 ブロック境界を
  最も広く取り、ブロック内部は詰める。全セクション同一パディングにしない
- **Section spacing:** 48px

### 画面構造（固定）

```text
1  つまり（Display 1 行）
2  目的 / 対象範囲（Body Small・Secondary）
3  グループ索引（縦積みアコーディオン。番号は左にハンギング）
     └ 展開すると詳細がその場に開く。同時に開くのは 1 つ
4  隠れている件数（deferred）— 常時可視
5  確認の質問 3 つ
```

## Depth & Elevation

| Level | Name | Usage | Shadow |
|-------|------|-------|--------|
| 0 | Flat | 既定。閉じたカード、索引、本文 | none（1px ボーダーで区切る） |
| 1 | Raised | **展開中のグループカードのみ** | `0 1px 2px rgba(26,25,23,0.06)` |
| 2 | Overlay | ポップオーバー（MVP 未使用） | `0 4px 12px rgba(26,25,23,0.10)` |
| 3 | Modal | モーダル（MVP 未使用） | `0 12px 32px rgba(26,25,23,0.14)` |
| 4 | Toast | トースト（MVP 未使用） | `0 8px 24px rgba(26,25,23,0.16)` |

深度の基本はボーダー階層である。影は「今フォーカスしている 1 枚」を示すためだけに使う。
**全カードに同じ影を当てない。**

## Do's and Don'ts

### Do

- 色には必ずテキストラベルを併用する（`要注意` / `未決` / `低リスク`）
- 折りたたみは閉じた状態でも「件数 + 1 行要約」を表示する
- 項目は読点で連結した段落にせず、1 行 1 項目のリストにする
- 角丸を役割で変える（ラベル 0px / 構造 2px / インタラクティブ・コード 3px）
- hover は left rail の伸長や地の白抜きなど、位置・形・色の変化で表現する
- 隠している情報の件数を常に可視にする
- コードブロックは自身の内部で横スクロールさせる
- キーボードフォーカスを明示的に描画する（`:focus-visible` で 2px リング）

### Don't

- **禁止フォント**: Inter, Roboto, Arial, Helvetica, Open Sans, Lato, Montserrat, Poppins,
  Space Grotesk、および総称ファミリー単独指定
- **禁止色**: Indigo-500 (`#6366F1`)、Violet-500 (`#8B5CF6`)、紫 → 青のグラデーション、
  Tailwind / Material のデフォルト値をそのまま使うこと
- 全要素を同じ角丸にしない
- 全カードに同じ影を当てない
- hover を opacity の変更だけで済ませない
- 中央寄せ Hero + 3 カラムカード + CTA の構成を作らない
- 完全対称グリッドにしない（番号ハンギングの非対称を維持する）
- 本文を画面幅いっぱいに伸ばさない
- 色だけで重要度・状態を伝えない
- 外部フォント・CDN・外部画像・ネットワーク送信を含めない
- 装飾目的のグラデーション・アイコンフォント・アニメーションを足さない

## Responsive Behavior

| Breakpoint | Name | Min Width | Behavior |
|-----------|------|-----------|----------|
| sm | Mobile | 0px | 単一カラム。番号ハンギングを解除し、番号を見出し行の先頭へ戻す。左余白 16px |
| md | Tablet | 640px | 本文行長が 42rem に届くまで自然に伸長。左余白 32px |
| lg | Desktop | 1024px | ページコンテナ 768px で中央寄せ。番号ハンギングが有効化される |
| xl | Wide | 1280px | lg と同一。コンテナをこれ以上広げない（行長を守るため） |

- **Touch targets:** minimum 44px
- **Approach:** mobile-first
- **Collapse strategy:**
  索引と詳細は元から縦積みのため、折り返しによる構造変化を起こさない。
  コードブロックのみ横スクロールで退避する。ページ本体は決して横スクロールさせない

## Agent Prompt Guide

AI コーディングエージェントへの指示:

1. UI を生成・変更する際は、必ずこの DESIGN.md を参照すること
2. Color Palette に定義されていない色を使用しないこと
3. Typography に定義されていないフォントファミリーを導入しないこと
4. Spacing は必ず Spacing scale の値を使用すること
5. Component Stylings に定義されたスタイルを逸脱しないこと
6. 新しいコンポーネントを作る場合は、既存コンポーネントのスタイルパターンに従うこと
7. **`brief` のレンダラは色・寸法をコードにハードコードしないこと。**
   すべて `.design/tokens.json` 由来の CSS 変数を経由すること
8. 生成 HTML に外部ネットワーク参照が含まれないことを、生成のたびに検証すること
