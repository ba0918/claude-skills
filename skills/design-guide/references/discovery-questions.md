# Discovery Questions

ディスカバリーフェーズで使用する質問バンクと回答解釈マトリクス。

## 質問設計の原則

- **オープンクエスチョンを避ける**: 「どんな色がいいですか？」は禁止。具体的な選択肢を提示する
- **二択〜四択で絞る**: AskUserQuestion の options（2-4択）で方向性を収束させる
- **preview を活用**: カラーパレットやフォントは preview フィールドでASCII表現を見せる
- **段階的に具体化**: ムード → カラー方向 → 具体 hex 値の順で詳細度を上げる
- **各フェーズ冒頭で中間まとめ**: 前フェーズの決定事項を要約してから次へ進む

## Phase 1: プロジェクトコンテキスト

### Q1: プロジェクトの種類

header: "プロジェクト種類"

| Option | Description |
|--------|-------------|
| Web アプリ / SPA | ログインがある業務ツール・SaaS・ダッシュボード等 |
| ランディングページ / マーケティング | 商品紹介・サービスLP・ポートフォリオ等 |
| モバイルアプリ | iOS / Android / クロスプラットフォーム |
| ドキュメント / ブログ | 技術文書・ブログ・ナレッジベース等 |

### Q2: ターゲットユーザー

header: "ユーザー層"

| Option | Description |
|--------|-------------|
| 開発者 / テック系 | エンジニア、デザイナー、テック好き |
| 一般消費者 | 幅広い年齢層、ITリテラシーは様々 |
| ビジネス / エンタープライズ | 企業の意思決定者、マネージャー層 |
| 社内ツール | 自社チームが使う内部ツール |

### Q3: 与えたい印象（multiSelect: true, 2つまで）

header: "印象"

| Option | Description |
|--------|-------------|
| プロフェッショナル | 信頼感・安定感・落ち着き |
| 親しみやすい | カジュアル・明るい・フレンドリー |
| 先進的 / イノベーティブ | テクノロジー感・未来的・エッジィ |
| プレミアム / 高級感 | 洗練・ラグジュアリー・品格 |

## Phase 2: ビジュアル方向（二択ラッシュ）

各質問は AskUserQuestion で1問ずつ出す。description で具体的なイメージを添える。

### Q4: カラーモード

header: "カラーモード"

| Option | Description |
|--------|-------------|
| ライトモード優先 | 白背景ベース。ダークモードは後から検討 |
| ダークモード優先 | 暗い背景ベース。開発者ツール・メディア系に多い |
| 両対応で設計 | 最初から両方のパレットを定義する |

### Q5: カラートーン

header: "色の温度"

| Option | Description |
|--------|-------------|
| 暖色系（Warm） | オレンジ・赤・イエロー寄り。親しみ・エネルギー感 |
| 寒色系（Cool） | ブルー・パープル・グリーン寄り。信頼・知性・落ち着き |
| ニュートラル | グレー・ベージュ・スレート。控えめでコンテンツが主役 |

### Q6: 情報密度

header: "密度"

| Option | Description |
|--------|-------------|
| ゆったり（Spacious） | 余白たっぷり。呼吸感があり視線が迷わない |
| みっちり（Dense） | 情報量重視。ダッシュボード・データ系向き |

### Q7: 角の形状

header: "角丸"

| Option | Description |
|--------|-------------|
| まるっと（Rounded） | 丸みのある柔らかいUI。親しみやすさ・フレンドリー |
| カクッと（Sharp） | 直線的でシャープ。プロフェッショナル・構造的 |
| 中間（Moderate） | ほどほどの丸み (4-8px)。バランス型 |

### Q8: 色の強さ

header: "彩度"

| Option | Description |
|--------|-------------|
| ビビッド（Bold） | 高彩度・高コントラスト。目を引く・エネルギッシュ |
| ミュート（Subtle） | 低彩度・柔らかい。上品・疲れにくい |

### Q9: 深度表現

header: "深度"

| Option | Description |
|--------|-------------|
| フラット（Flat） | シャドウなし or 極薄。ボーダーで区切る |
| 立体的（Depth） | シャドウ・エレベーションで奥行き表現 |

### Q10: フォントの方向性

header: "フォント"

| Option | Description |
|--------|-------------|
| サンセリフ（Modern） | Geometric / Grotesque 系。モダン・クリーン |
| セリフ（Classic） | 伝統的・権威感・エディトリアル |
| ミックス（見出しセリフ+本文サンセリフ） | コントラストで視覚的リズムを作る |

## Phase 3: カラーパレット生成

Phase 2 の回答から3つのパレット候補を生成し、AskUserQuestion の preview で提示する。

### 解釈マトリクス

| 温度 | 彩度 | 印象 | Primary 候補方向 |
|------|------|------|-----------------|
| Warm + Bold | — | #E84855, #FF6B35, #F77F00 系 |
| Warm + Subtle | — | #C1666B, #D4A373, #DDA15E 系 |
| Cool + Bold | — | #2563EB, #7C3AED, #0891B2 系 |
| Cool + Subtle | — | #6B7280, #64748B, #78716C 系 |
| Neutral + Bold | — | #18181B, #0F172A, #1C1917 系 |
| Neutral + Subtle | — | #9CA3AF, #A1A1AA, #A8A29E 系 |

各候補は以下を含むパレット全体として提示:
- Primary / Secondary / Accent
- Background / Surface
- Text Primary / Secondary
- Error / Warning / Success

### Preview 形式

```
━━━━━━━━━━━━━━━━━━━━━━━━━━
 Option A: "Ocean Breeze"
━━━━━━━━━━━━━━━━━━━━━━━━━━
 Primary:    #2563EB ████
 Secondary:  #3B82F6 ████
 Accent:     #06B6D4 ████
 Background: #FFFFFF
 Surface:    #F8FAFC ████
 Text:       #0F172A ████
 Error:      #DC2626 ████
 Success:    #16A34A ████
━━━━━━━━━━━━━━━━━━━━━━━━━━
```

## Phase 4: タイポグラフィ選定

Phase 2 の Q10 回答に基づき、3つのフォントペアリング候補を提示。

### フォント候補プール

**サンセリフ（見出し向き）:**
- Outfit — Geometric, modern, versatile
- Satoshi — Clean, contemporary, neutral
- Cabinet Grotesk — Bold, distinctive character
- Clash Display — Strong, editorial presence
- General Sans — Balanced, professional
- Switzer — Swiss-inspired, precise

**サンセリフ（本文向き）:**
- Plus Jakarta Sans — Friendly, readable
- DM Sans — Clean, geometric harmony
- Manrope — Semi-rounded, tech-friendly
- Geist — Vercel's font, developer-oriented
- Onest — Round, warm, accessible

**セリフ:**
- Playfair Display — Elegant, editorial
- Fraunces — Quirky, warm, distinctive
- Newsreader — Traditional, readable
- Lora — Elegant, literary
- Source Serif 4 — Professional, versatile

**モノスペース:**
- JetBrains Mono — Developer favorite, ligatures
- Fira Code — Ligatures, readable
- IBM Plex Mono — Clean, professional

### 禁止フォント（Anti-patterns より）

以下は使用禁止。AI が安易に選びがちなため、独自性に欠ける:
- Inter
- Roboto
- Arial
- Helvetica
- Open Sans
- Lato
- Montserrat
- Poppins
- system-ui (具体フォントの代替として)
- Space Grotesk

## Phase 5: コンポーネント＆レイアウト確認

Phase 2-4 で決定した内容を統合し、主要コンポーネントのスタイリングを提案する。

### 自動導出ルール

| Phase 2 回答 | 導出されるトークン |
|-------------|------------------|
| Rounded | border-radius: 12-16px (button), 16-24px (card) |
| Sharp | border-radius: 0-2px (button), 0-4px (card) |
| Moderate | border-radius: 6-8px (button), 8-12px (card) |
| Spacious | base-unit: 8px, section-gap: 64-96px, max-width: 1200px |
| Dense | base-unit: 4px, section-gap: 24-32px, max-width: 1440px |
| Flat | shadow: none, border: 1px solid {border} |
| Depth | shadow: 0 1px 3px rgba(0,0,0,0.1) to 0 25px 50px rgba(0,0,0,0.25) |

### 確認項目

AskUserQuestion で最終確認:
- 生成されたコンポーネントスタイルの preview を表示
- 「この方向でOK？」と確認
- 微調整があればフリーテキストで受け付ける

## 解釈の注意点

- 回答は絶対ではなくヒント。矛盾する回答があった場合は AskUserQuestion で意図を確認する
- ユーザーが「Other」でフリーテキストを入力した場合は、その内容を最優先で反映する
- 全フェーズを通じて、ユーザーの言葉を DESIGN.md の "Visual Theme & Atmosphere" セクションに反映する
