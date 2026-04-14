# Generation Constraints

design-generate スキルが生成するコードに適用される制約ルール。

## 制約の階層

```
Page Definition (sections, order, allowedComponents)
  → Component Catalog (variants, props, a11y)
    → Design Tokens (colors, fonts, spacing)
      → CSS Custom Properties (var(--*) のみ)
```

上位の制約は下位を含む。ページ定義がコンポーネントを制約し、コンポーネントがトークンを制約し、トークンが CSS 値を制約する。

## 許可される自由度

| カテゴリ | 自由度 | 例 |
|---------|--------|-----|
| テキストコンテンツ | 完全に自由 | 見出し・本文・ラベルの文言 |
| 画像コンテンツ | URL のみ自由 | `<img src="...">` の src 属性 |
| アニメーション | tokens 外の領域 | `transition`, `animation`, `@keyframes` |
| データバインディング | 完全に自由 | state management, API calls |
| イベントハンドラ | 完全に自由 | onClick, onChange 等のロジック |

## 禁止事項

| カテゴリ | 禁止内容 | 違反時のルール |
|---------|---------|-------------|
| カラー | tokens 外の色の使用 | DL001 / DL006 |
| フォント | tokens 外のフォントの使用 | DL002 |
| スペーシング | tokens 外の spacing 値 | DL003 |
| 角丸 | tokens 外の border-radius | DL004 |
| シャドウ | tokens 外の box-shadow | DL005 |
| コンポーネント | catalog 外のカスタムコンポーネント | DL101 |
| バリアント | catalog 外の variant | DL102 |
| スタイル上書き | inline style でのトークン対象プロパティ | DL103 |
| セクション構成 | page-def の sections 変更 | DL203 |
| レイアウト | layout-rules の constraints 違反 | DL204 |

## Do's/Don'ts → 機械検証可能ルールの変換例

DESIGN.md の Do's/Don'ts は自然言語。layout-rules.json の `constraints` で機械検証可能な形に変換する。

| Do/Don't (自然言語) | constraint (機械検証) |
|---------------------|---------------------|
| "左揃えを基本にする" | `LC001: text-align: center は h1, h2 のみ許可` |
| "余白を十分に取る" | `LC002: section gap は spacing.scale の上位3値のみ` |
| "3カラム以上のグリッドを使わない" | `LC003: grid-template-columns の列数 ≤ 3` |
| "モバイルではカードを縦積みにする" | `LC004: sm ブレークポイントで flex-direction: column` |
| "全要素に角丸をつける" | `LC005: border-radius: 0 は禁止（allowRawValues 除外を除く）` |
