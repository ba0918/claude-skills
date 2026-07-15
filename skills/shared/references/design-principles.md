# Design Principles

These are the foundational design principles that apply to ALL projects.
Every principle exists to serve one supreme goal: **Testability**.

## The Supreme Principle: Testability Above All

In the age of LLM-assisted development, a single instruction can produce vast amounts of code.
Human review alone cannot keep up. The only reliable safety net is **mechanically verifiable correctness** — meaning tests.

This problem will only accelerate. As LLMs grow more capable, the volume of generated code will scale from hundreds to thousands to tens of thousands of lines per instruction — while human cognitive capacity remains constant. The gap between what is produced and what can be manually reviewed will widen relentlessly. Testability is not a trend; it is the only architecture that survives this trajectory.

Therefore, testability is not one concern among many; it is THE concern.
Every other principle below exists because it makes code more testable.

If a design cannot be tested, the design is wrong. Full stop.

## Core Principles

### 1. Compose Small Parts into Larger Parts

Build systems by composing small, focused units into larger ones.

- Small parts are easy to test in isolation.
- Composed parts are easy to test because their dependencies are already tested.
- 200 lines per module is a heuristic signal for review, not a hard limit. A single-responsibility module may exceed this.
- The goal is preventing mixed responsibilities, NOT minimizing line count.

### 2. No Business Logic in Glue Code

Upper layers (orchestrators, handlers, routers) delegate only — they contain zero business logic.

- Orchestrators compose domain calls; they do not compute.
- This makes orchestrators trivially testable (verify delegation order) and domain logic independently testable (pure input/output).

### 3. Strict Layer Separation

Maintain clear architectural layers with unidirectional dependency flow:

```
Domain (pure logic, no side effects)
  -> Service (domain composition + I/O orchestration)
    -> Handler / Adapter (thin translation layer)
      -> UI / CLI / API (presentation only)
```

- Top-to-bottom dependencies only. Reverse dependencies are forbidden.
- Lateral dependencies across sibling modules at the same layer are forbidden.
- The domain layer must have zero external dependencies — framework-agnostic, pure logic only.

### 4. Pure Functions at Module Boundaries

Domain logic must be expressed as pure functions — no side effects, no hidden state.

- Pure functions are the easiest thing to test: given input X, expect output Y.
- Extract pure logic into dedicated modules (separate from I/O glue).
- If a function has side effects, it belongs in the service or infrastructure layer, not the domain.

### 5. Design for Dependency Injection

All external dependencies (randomness, time, file system, network, APIs) must be injectable.

- Inject abstractions (interfaces/traits/protocols), not implementations.
- This enables testing without mocks when possible, and with simple test doubles when necessary.
- If you cannot test a module without a running database, the design is wrong — abstract the data access.

### 6. Extend by Adding, Not Modifying (Open-Closed Principle)

New functionality is added by creating new modules/classes, not by modifying existing ones.

- Use interface + strategy/registry patterns: define a contract, implement per variant.
- When a new variant is added, existing code and existing tests remain untouched.
- If adding a feature requires touching many existing files, the abstraction boundary is wrong.

### 7. Type Safety as Mechanical Verification

Leverage the type system to catch errors at compile time — before tests even run.

- Use union types / Result types instead of exceptions for expected failures.
- Use exhaustive pattern matching so the compiler enforces completeness.
- Validate at system boundaries (runtime type checks), trust types internally.
- Avoid escape hatches (`any`, unsafe casts) — they defeat the purpose.

### 8. Immutability by Default

Prefer immutable data structures. Create new instances instead of mutating existing ones.

- Immutable data eliminates an entire class of bugs (unexpected mutation, race conditions).
- State transitions become explicit and testable: given state A and event X, expect state B.
- Use copy-with patterns for updates.

### 9. Security as a Design Constraint

Security is not a feature — it is a structural property of the design.

- Minimum permissions / minimum surface area.
- Validate and sanitize at boundaries (single canonical validator, reused everywhere).
- Path traversal prevention, prototype pollution prevention, input sanitization — bake these into the architecture, not sprinkled as afterthoughts.

## How to Apply These Principles

When reviewing or writing code, ask:

1. **Can I test this in isolation?** If not, decompose further.
2. **Does this module have exactly one reason to change?** If not, split responsibilities.
3. **Can I add a new variant without touching existing code?** If not, introduce an abstraction.
4. **Are all external dependencies injectable?** If not, wrap them behind interfaces.
5. **Does the type system enforce correctness?** If not, strengthen the types.
6. **Is the data immutable by default?** If not, justify the mutation.

The cost of good design is paid once. The cost of untestable code is paid on every change, forever.
