# V5 evaluator correction V1

Evaluator only; V5 NOT evaluated. Start with [REPORT.md](REPORT.md),
[evaluator-semantics-contract.md](evaluator-semantics-contract.md), then compare
synthetic-results-before.json / synthetic-results-after.json.

Reproduce corrected validation from repo root:

```sh
python3 data/reports/breslov/v5-evaluator-correction-v1/validate_evaluator.py
cd SrvRestAstroLS_v1/backend
uv run pytest tests/test_v5_evaluator_semantics.py -q
```

Do not execute the historical run_gate.py. Legacy evaluator helpers are archived
without imports/main; they never import V5. evaluator-freeze.json freezes the
corrected instrument, synthetic truth, tests and semantic contract, not V5.
Full scope/test/hash assertions: final-validation.json. No commit/push.
