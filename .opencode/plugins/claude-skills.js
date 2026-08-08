/**
 * claude-skills plugin for OpenCode.
 *
 * - Registers skills/ via config.skills.paths (no symlinks).
 * - Injects the using-workflow funnel (routing discipline included) + quality-gate
 *   pointer on the first user message (Claude Code SessionStart equivalent).
 */

import fs from "fs"
import path from "path"
import { spawnSync } from "child_process"
import { fileURLToPath } from "url"

const __dirname = path.dirname(fileURLToPath(import.meta.url))
const PACKAGE_ROOT = path.resolve(__dirname, "../..")
const SKILLS_DIR = path.join(PACKAGE_ROOT, "skills")
const ROUTING_PATH = path.join(SKILLS_DIR, "using-workflow", "SKILL.md")
const BOOTSTRAP_MARKER = "<!-- claude-skills-bootstrap -->"

const QUALITY_GATE_FILES = [
  "skills/shared/references/quality-gate-contract.md",
  "skills/shared/references/skill-repository-profile.md",
  "skills/shared/references/evidence-format.md",
]

let _bootstrapCache = undefined

function readText(filePath) {
  try {
    return fs.readFileSync(filePath, "utf8")
  } catch {
    return null
  }
}

// SKILL.md is injected without its frontmatter (metadata for the skill loader,
// noise in a resident-context injection).
function stripFrontmatter(text) {
  const m = /^---\n[\s\S]*?\n---\n?/.exec(text)
  return m ? text.slice(m[0].length) : text
}

function buildQualityGatePointer() {
  const lines = [
    "Quality gate contract (recall pointer): a publish-type state transition (merge / release / distribution) requires valid verification evidence bound to the target SHA and the in-force contract version. Read the canonical sources before publishing:",
  ]
  for (const rel of QUALITY_GATE_FILES) {
    const abs = path.join(PACKAGE_ROOT, rel)
    if (fs.existsSync(abs)) {
      lines.push(`- ${abs}`)
    }
  }
  return lines.length > 1 ? lines.join("\n") : null
}

function getBootstrapContent() {
  if (_bootstrapCache !== undefined) return _bootstrapCache

  const parts = [BOOTSTRAP_MARKER]
  const routing = readText(ROUTING_PATH)
  if (routing) {
    parts.push(stripFrontmatter(routing).trimEnd())
  }

  const quality = buildQualityGatePointer()
  if (quality) {
    parts.push(quality)
  }

  // Only inject when at least one payload section exists.
  if (parts.length === 1) {
    _bootstrapCache = null
    return null
  }

  parts.push(
    [
      "**OpenCode notes for claude-skills:**",
      "- Load skills with the native `skill` tool (name only; no plugin namespace prefix).",
      "- Prefer platform-agnostic skill instructions; map actions to OpenCode tools (`read`, `edit`, `bash`, `grep`, `glob`, `todowrite`, `task`, `webfetch`).",
      "- Subagent delegation → `task` (`general` / `explore` as appropriate).",
      `- Skill files live under \`${SKILLS_DIR}\` (including \`shared/\` contracts).`,
    ].join("\n"),
  )

  _bootstrapCache = parts.join("\n\n")
  return _bootstrapCache
}

const GATE_SCRIPT = path.join(SKILLS_DIR, "shared", "scripts", "workflow_gate.py")
// workflow_gate.py の _GIT_WORD と同一の文字クラス。lookbehind に / を足すと
// パス経由の /usr/bin/git が語として拾えなくなり、判定コア（Python 側）が deny
// する形をゲート未起動のまま素通しする — プレフィルタは常にコアの検出集合の
// 上位集合でなければならない（偽陽性はコアが allow を返すだけで無害、
// 偽陰性はゲートの迂回になる）。
const GIT_WORD = /(?<![\w.-])git(?![\w.-])/

// ゲート起動そのものを git に触れうるコマンドへ限定し、通常コマンドの往復
// コスト（python 起動）をゼロにするプレフィルタ。判定コアは (1) 生テキスト、
// (2) shlex トークン化後（クォート・エスケープ解決後）、(3) .git/hooks 接触の
// 3 経路で検出するため、ここでも同じ 3 経路を近似する。
function mightInvokeGit(command) {
  if (GIT_WORD.test(command) || command.includes(".git/hooks")) return true
  // shlex のクォート解決の近似: g"i"t / g'i't / g\it を git として再判定する
  const unquoted = command.replace(/["'\\]/g, "")
  return GIT_WORD.test(unquoted) || unquoted.includes(".git/hooks")
}

// この環境の実行前フックは「例外送出による遮断」しか表現できないため、
// escalate（人間確認）は deny + 理由文へ縮退する。正本契約:
// skills/shared/references/workflow-gate.md（縮退の規定と恩赦手順を含む）。
function runWorkflowGate(command) {
  let result
  try {
    result = spawnSync(
      "python3",
      [GATE_SCRIPT, "--decide", "--gate-command", command],
      { encoding: "utf8", timeout: 60000 },
    )
  } catch {
    return null // ゲート基盤の障害でセッションを壊さない（fail-open）
  }
  if (result.status !== 0 || !result.stdout) return null
  try {
    return JSON.parse(result.stdout)
  } catch {
    return null
  }
}

const ClaudeSkillsPlugin = async () => {
  return {
    config: async (config) => {
      config.skills = config.skills || {}
      config.skills.paths = config.skills.paths || []
      if (!config.skills.paths.includes(SKILLS_DIR)) {
        config.skills.paths.push(SKILLS_DIR)
      }
    },

    "tool.execute.before": async (input, output) => {
      if (input?.tool !== "bash") return
      const command = output?.args?.command
      if (typeof command !== "string" || !mightInvokeGit(command)) return
      const decision = runWorkflowGate(command)
      if (!decision || decision.verdict === "allow") return
      const label =
        decision.verdict === "deny"
          ? "workflow-gate deny"
          : "workflow-gate escalate (degraded to a refusal: this environment cannot ask the human inline — a human may approve per the reason below)"
      throw new Error(`${label}: ${decision.reason}`)
    },

    "experimental.chat.messages.transform": async (_input, output) => {
      const bootstrap = getBootstrapContent()
      if (!bootstrap || !output.messages?.length) return

      const firstUser = output.messages.find((m) => m.info?.role === "user")
      if (!firstUser?.parts?.length) return

      if (
        firstUser.parts.some(
          (p) => p.type === "text" && typeof p.text === "string" && p.text.includes(BOOTSTRAP_MARKER),
        )
      ) {
        return
      }

      const ref = firstUser.parts[0]
      firstUser.parts.unshift({ ...ref, type: "text", text: bootstrap })
    },
  }
}

// OpenCode treats every module export as a plugin. Keep this module's public
// surface to the plugin function so test helpers cannot be loaded as plugins.
export default ClaudeSkillsPlugin
