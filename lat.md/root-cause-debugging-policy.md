# Root Cause Debugging Policy

Non-trivial bugs must not be closed only because an existing test passes.

Required flow:

```text
symptom
reproduction
hypothesis
evidence
minimal fix
regression test when reasonable
final validation
```

Use this policy especially when:

- manual testing finds a bug that automated tests missed;
- browser behavior differs between desktop and mobile;
- local and production behavior differ;
- state persistence is involved;
- duplicate requests or 5xx responses appear;
- AI fallback or empty model responses are suspected.

This policy is local to TebaAI and has no dependency on gstack `/investigate`.
