/**
 * OpenCode plugin の静的検証（OpenCode 本体は不要）。
 * run_checks / unittest 発見対象外の .mjs なので、validate 前に明示実行するか
 * scripts/run_checks から呼ぶ。現状は単体で node 実行。
 */
import assert from "assert/strict"
import fs from "fs"
import path from "path"
import { fileURLToPath, pathToFileURL } from "url"

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..")
const pluginPath = path.join(root, ".opencode/plugins/claude-skills.js")
const packageJsonPath = path.join(root, "package.json")
const runtimeTestPath = path.join(root, "scripts/test_opencode_runtime.sh")

assert.ok(fs.existsSync(pluginPath), "plugin file missing")
assert.ok(fs.existsSync(packageJsonPath), "package.json missing")
assert.ok(fs.existsSync(runtimeTestPath), "OpenCode runtime test missing")
assert.ok(fs.statSync(runtimeTestPath).mode & 0o100, "OpenCode runtime test is not executable")

const pkg = JSON.parse(fs.readFileSync(packageJsonPath, "utf8"))
assert.equal(pkg.name, "claude-skills")
assert.equal(pkg.main, ".opencode/plugins/claude-skills.js")
assert.equal(pkg.type, "module")

const mod = await import(pathToFileURL(pluginPath).href)
// OpenCode treats module exports as plugin candidates. Keep the entrypoint
// surface to a single function so helper values stay private to the module.
assert.deepEqual(Object.keys(mod), ["default"])
assert.equal(typeof mod.default, "function")

const PACKAGE_ROOT = root
const SKILLS_DIR = path.join(PACKAGE_ROOT, "skills")
const ROUTING_PATH = path.join(PACKAGE_ROOT, "skills", "using-workflow", "SKILL.md")
const BOOTSTRAP_MARKER = "<!-- claude-skills-bootstrap -->"

assert.ok(fs.existsSync(path.join(SKILLS_DIR, "cycle", "SKILL.md")))
assert.ok(fs.existsSync(path.join(SKILLS_DIR, "shared", "SKILL.md")))
assert.ok(fs.existsSync(ROUTING_PATH))

const hooks = await mod.default({})
assert.equal(typeof hooks.config, "function")
assert.equal(typeof hooks["experimental.chat.messages.transform"], "function")

const config = { skills: { paths: ["/tmp/other"] } }
await hooks.config(config)
assert.deepEqual(config.skills.paths, ["/tmp/other", SKILLS_DIR])
// idempotent
await hooks.config(config)
assert.deepEqual(config.skills.paths, ["/tmp/other", SKILLS_DIR])

const messages = {
  messages: [
    {
      info: { role: "user" },
      parts: [{ type: "text", text: "hello", id: "p1" }],
    },
  ],
}
await hooks["experimental.chat.messages.transform"]({}, messages)
assert.equal(messages.messages[0].parts.length, 2)
assert.ok(messages.messages[0].parts[0].text.includes(BOOTSTRAP_MARKER))
assert.ok(messages.messages[0].parts[0].text.includes("Using the Trunk Workflow"))
assert.ok(messages.messages[0].parts[0].text.includes("investigate"))
// frontmatter is stripped from the injected SKILL.md body
assert.ok(!messages.messages[0].parts[0].text.includes("name: using-workflow"))
assert.ok(messages.messages[0].parts[0].text.includes("Quality gate contract"))
assert.ok(
  messages.messages[0].parts[0].text.includes(
    path.join(SKILLS_DIR, "shared", "references", "quality-gate-contract.md"),
  ),
)
assert.equal(messages.messages[0].parts[1].text, "hello")

// no double inject
await hooks["experimental.chat.messages.transform"]({}, messages)
assert.equal(messages.messages[0].parts.length, 2)

// --- workflow gate (tool.execute.before) ---
assert.equal(typeof hooks["tool.execute.before"], "function")

// 非 bash ツール・git を含まないコマンドは素通し（発話ゼロ）
await hooks["tool.execute.before"]({ tool: "read" }, { args: { filePath: "/x" } })
await hooks["tool.execute.before"]({ tool: "bash" }, { args: { command: "ls -la" } })

// バイパスフラグは deny: 例外送出で遮断され、理由文を運ぶ
await assert.rejects(
  hooks["tool.execute.before"](
    { tool: "bash" },
    { args: { command: "git commit --no-verify -m x" } },
  ),
  (err) => err.message.includes("workflow-gate deny"),
)

// プレフィルタ回帰: Python 判定コア（workflow_gate.py）が deny / escalate する
// 敵対形は、プレフィルタでもゲート起動まで到達しなければならない
// パス経由の git + バイパスフラグ
await assert.rejects(
  hooks["tool.execute.before"](
    { tool: "bash" },
    { args: { command: "/usr/bin/git commit --no-verify -m x" } },
  ),
  (err) => err.message.includes("workflow-gate deny"),
)
// クォート分割形（シェルは g"i"t を git として実行する）
await assert.rejects(
  hooks["tool.execute.before"](
    { tool: "bash" },
    { args: { command: 'g"i"t commit --no-verify -m x' } },
  ),
  (err) => err.message.includes("workflow-gate deny"),
)
// フックディレクトリ接触（git の語なし）は escalate → deny 縮退 + 理由文
await assert.rejects(
  hooks["tool.execute.before"](
    { tool: "bash" },
    { args: { command: "rm -f .git/hooks/pre-push" } },
  ),
  (err) => err.message.includes("workflow-gate escalate"),
)
// クォート分割形のフックディレクトリ接触（シェルは .gi"t/hooks" を .git/hooks に解決する）
await assert.rejects(
  hooks["tool.execute.before"](
    { tool: "bash" },
    { args: { command: 'rm .gi"t/hooks/pre-push"' } },
  ),
  (err) => err.message.includes("workflow-gate escalate"),
)

// ゲート子プロセスのタイムアウトは Python 側 evidence 検証タイムアウトより長くなければ
// ならない — 短いと push 判定の evidence 検証中に子プロセスが打ち切られ、
// fail-open（無言 allow）へ落ちる
const pluginSource = fs.readFileSync(pluginPath, "utf8")
const gateSource = fs.readFileSync(
  path.join(root, "skills/shared/scripts/workflow_gate.py"),
  "utf8",
)
const evidenceTimeoutSec = Number(/_EVIDENCE_TIMEOUT\s*=\s*(\d+)/.exec(gateSource)[1])
const gateTimeoutMs = Number(/timeout:\s*(\d+)/.exec(pluginSource)[1])
assert.ok(
  gateTimeoutMs > evidenceTimeoutSec * 1000,
  `gate child-process timeout (${gateTimeoutMs}ms) must exceed the Python evidence-verification timeout (${evidenceTimeoutSec}s)`,
)

console.log("ok: opencode plugin checks passed")
