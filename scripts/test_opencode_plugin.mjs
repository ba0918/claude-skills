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

assert.ok(fs.existsSync(pluginPath), "plugin file missing")
assert.ok(fs.existsSync(packageJsonPath), "package.json missing")

const pkg = JSON.parse(fs.readFileSync(packageJsonPath, "utf8"))
assert.equal(pkg.name, "claude-skills")
assert.equal(pkg.main, ".opencode/plugins/claude-skills.js")
assert.equal(pkg.type, "module")

const mod = await import(pathToFileURL(pluginPath).href)
assert.equal(typeof mod.ClaudeSkillsPlugin, "function")
assert.ok(mod._internals)

const { PACKAGE_ROOT, SKILLS_DIR, ROUTING_PATH, BOOTSTRAP_MARKER, getBootstrapContent, resetBootstrapCache } =
  mod._internals

assert.equal(PACKAGE_ROOT, root)
assert.ok(fs.existsSync(path.join(SKILLS_DIR, "cycle", "SKILL.md")))
assert.ok(fs.existsSync(path.join(SKILLS_DIR, "shared", "SKILL.md")))
assert.ok(fs.existsSync(ROUTING_PATH))

resetBootstrapCache()
const bootstrap = getBootstrapContent()
assert.ok(bootstrap)
assert.ok(bootstrap.includes(BOOTSTRAP_MARKER))
assert.ok(bootstrap.includes("Skill Routing"))
assert.ok(bootstrap.includes("investigate"))
assert.ok(bootstrap.includes("Quality gate contract"))
assert.ok(bootstrap.includes(path.join(SKILLS_DIR, "shared", "references", "quality-gate-contract.md")))

// cache
assert.equal(getBootstrapContent(), bootstrap)

const hooks = await mod.ClaudeSkillsPlugin({})
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
assert.equal(messages.messages[0].parts[1].text, "hello")

// no double inject
await hooks["experimental.chat.messages.transform"]({}, messages)
assert.equal(messages.messages[0].parts.length, 2)

console.log("ok: opencode plugin checks passed")
