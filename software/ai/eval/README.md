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

The first local model comparison uses the installed
`llama-3.1-8b-instruct-q4_k_m:latest` Ollama artifact. Its exact digest,
runtime version, prompt hash, generation settings, per-case latency, invalid
responses, and false execution count are in `llama31_8b_q4_v1_scorecard.json`.
This is one locally served quantized candidate, not a result for every Llama
3.1 release. The installed tag carries a translation-oriented default system
prompt; the evaluator supplies an explicit task system message. Local
metadata does not establish the weights' origin or license, so do not treat
this run as a verified unmodified base-model result. It matched
17/31, made five false execution proposals, and returned one invalid response.
The five accepted wrong proposals all concern ambiguous requests. The runner
records response hashes rather than full generated text. Latency depends on
local model loading and cache state; it is not a deployment benchmark.

`benchmark_v2.jsonl` is a fresh 24-case challenge set frozen before project
fine tuning or prompt revision. Its `simulated_review_v2.json` cross-checks
24/24 cases against the compiler and checks exact request reuse against both
earlier sets. No person reviewed its English labels. It was consumed once for
the first SFT pilot comparison. Do not use it for selecting examples, prompts,
or checkpoints; freeze a new held-out set before further tuning.

The provenance-pinned Meta Llama 3.2 1B Instruct candidate scores 0/31 on v1
with 13 invalid outputs in JSON mode. That is a measured failure of this
checkpoint and prompt under the strict proposal schema. The source revision
and imported Ollama digest are recorded in
[`train/llama32_1b_candidate.json`](../train/llama32_1b_candidate.json).

The first SFT pilot scores 14/31 on v1 with five false execution proposals.
On v2 it scores 10/24 with one false execution proposal and one invalid
response. The unmodified official 1B checkpoint scores 0/24 on v2, while the
deterministic parser scores 8/24 with no false execution proposals. All these
results are offline intent/compiler measurements; the SFT pilot remains
blocked from arm control.

From the repository root, repeat the checks with:

```powershell
python software/ai/run_offline.py review
python software/ai/run_offline.py evaluate --cases software/ai/eval/benchmark_v1.jsonl --manifest software/ai/eval/benchmark_v1.manifest.json
python software/ai/run_offline.py evaluate-model --model llama-3.1-8b-instruct-q4_k_m:latest
python software/ai/run_offline.py review --cases software/ai/eval/benchmark_v2.jsonl --manifest software/ai/eval/benchmark_v2.manifest.json --prior software/ai/eval/benchmark_v0.jsonl --prior software/ai/eval/benchmark_v1.jsonl
```
