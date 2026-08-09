/**
 * claude-skills plugin for OpenCode.
 *
 * - Registers skills/ via config.skills.paths (no symlinks).
 * - Injects the using-workflow funnel (routing discipline included) on the first
 *   user message (Claude Code SessionStart equivalent).
 */

import fs from "fs"
import path from "path"
import { fileURLToPath } from "url"

const __dirname = path.dirname(fileURLToPath(import.meta.url))
const PACKAGE_ROOT = path.resolve(__dirname, "../..")
const SKILLS_DIR = path.join(PACKAGE_ROOT, "skills")
const ROUTING_PATH = path.join(SKILLS_DIR, "using-workflow", "SKILL.md")
const BOOTSTRAP_MARKER = "<!-- claude-skills-bootstrap -->"

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

function getBootstrapContent() {
  if (_bootstrapCache !== undefined) return _bootstrapCache

  const parts = [BOOTSTRAP_MARKER]
  const routing = readText(ROUTING_PATH)
  if (routing) {
    parts.push(stripFrontmatter(routing).trimEnd())
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

const ClaudeSkillsPlugin = async () => {
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

// OpenCode treats every module export as a plugin. Keep this module's public
// surface to the plugin function so test helpers cannot be loaded as plugins.
export default ClaudeSkillsPlugin
