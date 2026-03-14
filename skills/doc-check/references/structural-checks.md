# Structural Checks

Mechanically cross-referencing the actual file system state against descriptions in documentation.
Low false positive rate and easy to auto-fix.

## Check Target Patterns

### 1. File/Directory References in Tables and Lists

When Markdown tables or lists in documentation enumerate files or directories:

- Whether listed paths actually exist
- Whether existing files/directories are missing from the table

**Detection method:**
1. Extract table rows (`|` delimited) and list items (`- ` / `* `) from the document
2. Detect file paths, directory paths, and command names within lines using regex
3. Compare against the actual file system state

**Typical examples:**
- Command listing table vs `commands/` directory
- Skill listing table vs `skills/` directory
- API endpoint listing vs routing definitions

### 2. Directory Tree Diagrams

Tree diagrams in documentation (code blocks containing `├──` / `└──` / `│`):

- Whether entries in the tree actually exist
- Whether existing entries are missing from the tree (judged based on siblings at the same level)

**Detection method:**
1. Detect `├──` `└──` patterns in code blocks
2. Identify the root directory of the tree (infer from context preceding the tree)
3. Verify existence of each entry

### 3. File Path References in Code Blocks

File paths in command examples and code samples:

- Whether referenced files actually exist
- Whether path format is correct

**Detection method:**
1. Extract path patterns from strings in code blocks (strings containing `src/`, `./`, `/`)
2. Exclude obviously placeholder values (`example`, `foo`, `bar`, etc.)
3. Verify existence of remaining paths

### 4. Version Numbers

Version mentions in documentation:

- Whether they match versions in `package.json` / `Cargo.toml` / `pyproject.toml` etc.
- Whether dependency library version mentions match actual state

**Detection method:**
1. Detect version patterns in documentation (`v1.2.3`, `^1.2.3`, `>=1.0`, etc.)
2. Compare against versions in corresponding manifest files

## Auto-Fix Policy

- **Table missing entries**: Add rows following existing entry format. Infer description from frontmatter or leading comments of the corresponding file
- **Table extra entries**: Do not delete; report as WARN (may be intentionally kept)
- **Tree diagram missing entries**: Add following sibling entry format
- **Tree diagram extra entries**: Do not delete; report as WARN
- **Version mismatch**: Update with the value from the manifest file
