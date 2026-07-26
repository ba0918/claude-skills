# Root Cause Tracing

The technique of tracing a bug backwards to find the root cause rather than the symptom.

## Core Principle

```
Do not fix the symptom. Find the root cause first, then fix.
```

## The tracing process

### 1. Observe the symptom

Record the error message, the stack trace, and the abnormal output exactly.

```
Error: git init failed in /Users/user/project/packages/core
```

### 2. Identify the direct cause

What code caused this error directly?

```typescript
await execFileAsync('git', ['init'], { cwd: projectDir });
```

### 3. Trace further upstream

Repeat the question "what called this function with these arguments?".

```
WorktreeManager.createSessionWorktree(projectDir, sessionId)
  → Session.initializeWorkspace()
    → Session.create()
      → test: Project.create()
```

### 4. Keep tracing upstream

Verify the value passed at each layer:

- `projectDir = ''` (an empty string!)
- An empty `cwd` → resolves to `process.cwd()`
- That is, git init ran inside the source-code directory

### 5. Discover the root cause

```typescript
const context = setupCoreTest(); // returns { tempDir: '' }
Project.create('name', context.tempDir); // accessed before beforeEach!
```

The root cause: a top-level variable initialization is accessing an empty value.

## Diagnostic instrumentation in a multi-layer system

When a system is composed of several components, add logging at each component boundary to identify **where it breaks**.

### The pattern

```
At each component boundary:
  - log the input data
  - log the output data
  - verify the propagation of the environment and the configuration
  - confirm the state at each layer

Run it once and collect the evidence
→ analyze which boundary it breaks at
→ investigate that specific component
```

### A concrete example

```bash
# Layer 1: the workflow
echo "=== Secrets available: ==="
echo "API_KEY: ${API_KEY:+SET}${API_KEY:-UNSET}"

# Layer 2: the build script
echo "=== Env vars in build: ==="
env | grep API_KEY || echo "API_KEY not in environment"

# Layer 3: the application
echo "=== Config loaded: ==="
cat config.json | jq '.apiKey'
```

## Adding a stack trace

When you cannot trace it by hand, add instrumentation:

```typescript
async function riskyOperation(directory: string) {
  const stack = new Error().stack;
  console.error('DEBUG riskyOperation:', {
    directory,
    cwd: process.cwd(),
    nodeEnv: process.env.NODE_ENV,
    stack,
  });
  // the actual work
}
```

**Use `console.error()` during tests** (a logger can be suppressed in tests).

## Defense-in-Depth

After fixing the root cause, add validation at each layer so the same bug cannot recur:

1. **Layer 1**: input validation (an empty-string check, and so on)
2. **Layer 2**: an environment guard (in a test environment, refuse operations outside tmpdir, and so on)
3. **Layer 3**: added logging (emit a log before a dangerous operation)
4. **Layer 4**: a regression test (add a test reproducing this specific bug)

## Key Principle

```
You found the direct cause → can you trace one layer up?
  You can → go further upstream
  You cannot → this is the root cause
    → fix the root cause
    → add validation at each layer
    → the bug becomes structurally unable to recur
```
