# PBT binding guide

The design guidance for the bind workflow when it generates property-based tests (PBTs) from a clause's
kind-specific payload. The norms for clause vocabulary and assurance levels are canonical in
[clause-schema.md](clause-schema.md), and the observation format and the conditions for valid evidence are
canonical in [evidence-manifest.md](evidence-manifest.md); this document redefines neither.
Identify the language with the procedure of the [lang-detect contract](../../shared/references/lang-detect.md).

## The common contract (a language-independent adapter)

Whatever the library, a generated PBT is built from the following 5 elements. Each element is derived from the
clause's kind-specific payload and never depends on reinterpreting the natural language `statement`.

| Element | Derived from | Rule |
|------|--------|------|
| generator | the payload's input domain (`input_domain` / `target` / `states`+`events` / subject×action×resource) | satisfy preconditions **by constructing the generator, not by filtering** (see below) |
| oracle | the payload's verification predicate (`postcondition` / `condition` / the transition rules / `effect`) | **no side effects**: never access the network, write files, or change environment variables |
| seed fixing and reproduction | the library's seed mechanism | on failure, record the seed (or the library's reproduction token) and leave the reproduction command |
| shrink | the library's shrinking mechanism | have counterexamples reported in minimized form (even with a hand-rolled generator, choose a shape that can shrink) |
| distribution observation | the library's statistics / label mechanism | observe whether inputs reach the intended regions (boundary values, equivalence classes) |

### Avoiding filter abuse

Satisfying a precondition with a filter (an assume / discard style mechanism) increases discards and reduces the
number of valid executed cases. The promotion conditions (valid case count, failure count, exit status, and all the
skip/xfail conditions) are canonical in
[the assurance level section of clause-schema.md](clause-schema.md#保証レベル),
and filter abuse produces "tests that ran but count as no evidence".

- Satisfy preconditions by constructing the generator (restricting the value range, structural assembly, mapping).
  Example: build "a sorted array" not with filter(isSorted) but by "generating an array and sorting it".
- Limit filters to the residual conditions that cannot be expressed constructively.
- In libraries that expose the discard count, record it in the observation's `cases_discarded`
  ([evidence-manifest.md](evidence-manifest.md)) and use distribution observation to confirm that discards are not
  squeezing out the valid cases.

### Confirming the valid case count

After running, record the execution result as an observation
(the fields and the conditions for valid evidence are canonical in [evidence-manifest.md](evidence-manifest.md)).
Because which runs count as evidence of success (the promotion conditions) is canonical in
[the assurance level section of clause-schema.md](clause-schema.md#保証レベル),
confirm at generation time, via distribution observation, that the test can produce valid cases every run.

### Test identifiers

Name the generated tests with identifiers that can be recorded directly as a binding's `test_id`
(the character-set rule is in [evidence-manifest.md](evidence-manifest.md#識別子digest-の形式規則)).
Never give a name containing whitespace or shell metacharacters.

## Generation patterns by kind

### invariant (`target` / `condition`)

The minimal form: generate the target data shape and verify the invariant predicate.

```text
property "CLAUSE-ID: condition holds for all target values":
  for_all x in gen_target():        # a generator derived from the description of target
    assert condition(x)             # an oracle derived from condition
```

### pre_post (`input_domain` / `precondition` / `operation` / `postcondition`)

Generate inputs from input_domain, satisfy the precondition constructively, run the operation,
and verify the postcondition.

```text
property "CLAUSE-ID: postcondition after operation":
  for_all input in gen_precondition_satisfying(input_domain):
    result = operation(input)       # calling the target operation
    assert postcondition(input, result)
```

When the postcondition covers "the relation between input and output", hand the input to the oracle as well
(never weaken it to a property of the output alone).

### transition (`states` / `events` / `transitions` / `forbidden`)

State machine testing. Generate random event sequences and run the clause's transition table as a model
alongside the implementation.

```text
property "CLAUSE-ID: implementation follows the transition table":
  for_all event_sequence in gen_sequences(events):
    model_state = initial; impl = new_implementation()
    for event in event_sequence:
      expected = lookup(transitions, model_state, event)   # evaluate the guards too
      if expected is undefined or (model_state, event) in forbidden:
        assert impl.rejects(event)                         # forbidden and undefined transitions are rejected
      else:
        impl.apply(event)
        model_state = expected.to
        assert impl.state == model_state
```

- Use the library's state machine testing mechanism when it has one. When it does not, the substitute above
  ("generate an event sequence + apply it step by step") works. When neither is possible, report that clause
  as unsupported (the rule of the bind workflow).
- Never skip verifying `forbidden`. Following the allowed transitions alone cannot detect a forbidden transition slipping in.

### authorization (`subject` / `action` / `resource` / `context` / `effect`)

Decision table testing. Generate the decision's input space as tuples and match the expected effect against the
implementation's decision.

```text
property "CLAUSE-ID: access decision matches the clause":
  for_all (subj, act, res, ctx) in gen_tuples(subject, action, resource, context):
    expected = decide(clauses_in_scope, subj, act, res, ctx)  # resolved deny-first
    assert authorize(subj, act, res, ctx) == expected
```

- **Deny-first conflict resolution** is the semantics the v1 schema fixes
  ([clause-schema.md](clause-schema.md#kind-別-discriminated-payload)),
  and it must always be built into the oracle (`decide`).
- Verify not only that the allow side succeeds but that **tuples that should be denied are reliably denied**
  (placing the clause's `counterexamples` alongside as fixed cases makes the boundary explicit).
- Construct the generator to straddle "inside and outside the boundary" (generate both target and non-target roles,
  and both owned and non-owned resources).

## Examples by language

A mapping of representative libraries. **These are examples and deliberately avoid version-specific API details**
(follow the documentation of the library actually installed in the target project for the exact call form).

| Language | Representative library | Seed reproduction | Shrink | Distribution observation | State machine testing |
|------|---------------|-----------|--------|----------|---------------|
| TypeScript / JavaScript | fast-check | yes | yes | yes | yes (model-based) |
| Python | hypothesis | yes | yes | yes | yes (rule-based) |
| Rust | proptest | yes | yes | limited | not built in (substitute a companion crate or event sequence generation) |
| Go | rapid | yes | yes | yes | yes |

### TypeScript (fast-check) — pseudocode

```text
// invariant: "the price after a discount stays at or above 0 and at or below the original"
test("PRICE-INV-001: discounted price stays within [0, original]", () =>
  assertProperty(
    forAll(genOrder(),                 // generate valid orders by construction, not by filtering
      order => {
        const p = applyDiscount(order)
        return p >= 0 && p <= order.originalPrice
      }),
    { seed: recordedSeedOnFailure }))  // record the seed on failure and reproduce
```

- Do the distribution observation with the library's statistics / label mechanism, confirming that boundary values
  (a price of 0, the upper limit) are reached.
- For a state machine (a transition clause), run the model-based testing mechanism with the model = the clause's
  transition table and the subject = the implementation.

### Python (hypothesis) — pseudocode

```text
# pre_post: "pop on a non-empty list shortens it by 1, and returns the former last element"
@given(non_empty_lists())            # satisfy "non-empty" by generator construction, not by assume
def test_LIST_PP_003_pop_shrinks_by_one(xs):
    old_length = len(xs)
    tail = xs[-1]
    result = pop(xs)
    assert result == tail
    assert len(xs) == old_length - 1
```

- Follow the library's failure database / seed output to reproduce a failure, and record the reproduction command
  in the observation's `command`.
- A transition clause can be expressed with the rule-based state machine testing mechanism.

### Rust (proptest) / Go (rapid) — briefly

- **Rust (proptest)**: satisfy preconditions constructively by composing strategies. Whether the regression file
  recording seeds on failure is committed follows the target project's conventions.
  Because state machine testing is not built into the crate itself, a transition clause either introduces a
  companion crate (let the user choose when none is installed — the rule of the bind workflow) or falls back to the
  "generate an event sequence as a Vec and apply it step by step" pattern.
- **Go (rapid)**: it has generator composition and a state machine testing mechanism. Shape the test name so it can
  be given directly to the runner's filter argument (the `-run` equivalent), and keep it identical to the binding's
  `test_id`.
