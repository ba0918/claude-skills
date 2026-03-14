# Light Review - Lightweight Review Perspectives

Simplified review criteria used for post-implementation review in iterate.
Focuses on the 2 most important perspectives instead of the full 6-dimension review from plan-reviewer.

## Perspective 1: Security

Whether the changes introduce security risks.

### Checklist

- [ ] External input validation and sanitization is appropriate
- [ ] No exposure of sensitive data (credentials, tokens, keys, etc.)
- [ ] Defense against injection attacks (SQL, command, path, etc.) is present
- [ ] Error messages do not leak internal system information

### Verdict

- **BLOCK**: Unvalidated external input, sensitive data exposure, injection vulnerability
- **WARN**: Validation exists but is incomplete, error messages contain too much information
- **PASS**: No security issues

## Perspective 2: Implementation Quality

Whether the changes maintain the existing code quality standards.

### Checklist

- [ ] Existing tests are not broken
- [ ] No obvious bugs in added/modified code
- [ ] DRY principle: No duplication with existing code
- [ ] Error handling: Failure paths are properly handled
- [ ] No violations of CLAUDE.md / `.claude/review-rules.md` rules

### Verdict

- **BLOCK**: Test failures, obvious bugs, project rule violations
- **WARN**: DRY violations, insufficient error handling
- **PASS**: Meets quality standards

## Additional Perspectives for Large Tasks

When the user chooses to continue after a Large judgment, check these in addition to the above:

### Perspective 3: Architecture

- [ ] No violations of layer structure or dependency direction
- [ ] No mixing of responsibilities
- [ ] Type safety is maintained

### Perspective 4: Completeness

- [ ] Edge cases (empty input, large input, invalid input) are considered
- [ ] Backward compatibility is maintained
- [ ] Necessary tests have been added
