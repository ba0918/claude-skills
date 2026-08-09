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

console.log("ok: opencode plugin checks passed")
