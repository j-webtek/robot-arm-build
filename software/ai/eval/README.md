# Evaluation

Track a frozen, human-reviewed offline benchmark here before model tuning.
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
set and add a separately reviewed, broader held-out benchmark before making
a model-promotion decision.
