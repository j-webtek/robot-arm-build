# Evaluation

Track frozen offline benchmarks here before model tuning.
Cases should include supported keyboard/phone lowercase typing and expected
clarification or rejection for unsupported requests. Record exact extraction,
RoCell compiler acceptance, false execution, and latency. Keep task paraphrase
families split between training and held-out evaluation.

Generated scorecards and run outputs belong in ignored `results/`. The
[roadmap](../docs/ROADMAP.md) defines the first baseline sequence.

`benchmark_v0.jsonl` is an agent-authored 28-case sanity set pinned by
`benchmark_v0.manifest.json`. The checked-in `baseline_v0_scorecard.json` is
the deterministic baseline result. Its 28/28 match shows this narrow contract
works on these hand-authored examples; it does not establish general English
understanding or physical task success. Keep these cases out of any training
set.

`benchmark_v1.jsonl` is a separate 31-case paraphrase and rejection set. Its
manifest freezes the exact bytes and marks the review as **simulated**. The
checked-in `simulated_review_v1.json` cross-checks labels, observation state,
prior-request duplication, and supported text against RoCell's compiler. It
reports 31/31 internally consistent cases and `human_reviewed: false`. The
English interpretations and case coverage remain agent-authored; this is not
an independent human evaluation.

The unchanged deterministic baseline scores 17/31 on v1. Its scorecard
records one false execution proposal: `Type it on the keyboard` becomes a
literal `it` plan despite the missing antecedent. This blocks any promotion
of that baseline to arm control. Keep v1 and its paraphrase families out of
training data. Model candidates should be evaluated against this frozen set
without changing its labels or examples.

From the repository root, repeat the checks with:

```powershell
python software/ai/run_offline.py review
python software/ai/run_offline.py evaluate --cases software/ai/eval/benchmark_v1.jsonl --manifest software/ai/eval/benchmark_v1.manifest.json
```
