# {Feature Name}

**Cycle ID:** `{timestamp}`
**Started:** {YYYY-MM-DD HH:MM:SS}
**Status:** 🟡 Planning
**Issue:** _{issue_slug or remove this line if not from an issue}_
**Spec:** _{path to domain spec in docs/spec/, or remove this line if no spec exists yet}_

---

## 📝 What & Why

{1-2 sentences describing what to build and why. This section and Goals are the human-facing layer: write them for the reader defined in [Target audience](../../shared/references/human-readable-summary.md#target-audience). Unpack every technical term, internal abbreviation, and code name at first use, and write references to issues or past decisions so they carry their meaning without being opened.}

## 🎯 Goals

- {Goal 1 — same plain-language rule as What & Why: state the outcome in words a reader without project background understands}
- {Goal 2}
- {Goal 3}

## 📐 Design

### Files to Change

```
src/
  {Affected files with brief change descriptions}
  example.ts - {What to do}
  example.test.ts - {Test description}
```

### Key Points

- **{Change point 1}**: {Brief explanation}
- **{Change point 2}**: {Brief explanation}

## ✅ Tests

- [ ] {Test 1}
- [ ] {Test 2}
- [ ] {Test 3}

## 🔧 Implementation Steps

1. **{Step title}**
   - Files: `{path/to/file}`
   - {What to implement in this step}

2. **{Step title}**
   - Files: `{path/to/file}`
   - {What to implement in this step}

3. **{Step title}**
   - Files: `{path/to/file}`
   - {What to implement in this step}

## 🔒 Security (if applicable)

- [ ] Input validation
- [ ] XSS protection
- [ ] {Other security considerations}

---

**Next:** Write tests → Implement → Commit with `claude-skills:commit` 🚀
