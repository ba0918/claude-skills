/**
 * claude-skills plugin for OpenCode.
 *
 * - Registers skills/ via config.skills.paths (no symlinks).
 * - Injects skill-routing + quality-gate pointer on the first user message
 *   (Claude Code SessionStart equivalent).
 */

import fs from "fs"
import path from "path"
import { fileURLToPath } from "url"

const __dirname = path.dirname(fileURLToPath(import.meta.url))
const PACKAGE_ROOT = path.resolve(__dirname, "../..")
const SKILLS_DIR = path.join(PACKAGE_ROOT, "skills")
const ROUTING_PATH = path.join(PACKAGE_ROOT, "rules", "skill-routing.md")
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
    parts.push(routing.trimEnd())
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

export const ClaudeSkillsPlugin = async () => {
  return {
    config: async (config) => {
      config.skills = config.skills || {}
      config.skills.paths = config.skills.paths || []
      if (!config.skills.paths.includes(SKILLS_DIR)) {
        config.skills.paths.push(SKILLS_DIR)
      }
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

// Test / diagnostics helpers (not used by OpenCode runtime).
export const _internals = {
  PACKAGE_ROOT,
  SKILLS_DIR,
  ROUTING_PATH,
  BOOTSTRAP_MARKER,
  getBootstrapContent,
  resetBootstrapCache: () => {
    _bootstrapCache = undefined
  },
}
