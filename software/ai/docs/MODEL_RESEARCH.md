# Llama training reference for this AI task

Llama 3.1 is a dense, autoregressive Transformer with grouped-query attention.
Meta describes broad pretraining followed by iterative supervised fine tuning,
rejection sampling, and preference optimization. For Llama 3.2's 1B/3B text
models, Meta reports pruning and teacher-logit distillation. These published
methods inform experiments; they do not provide Meta's full training data or a
reproducible recipe for its weights.

Sources: [Llama 3 paper](https://arxiv.org/abs/2407.21783),
[Llama 3.1 model card](https://github.com/meta-llama/llama-models/blob/main/models/llama3_1/MODEL_CARD.md),
[Llama 3.2 model card](https://github.com/meta-llama/llama-models/blob/main/models/llama3_2/MODEL_CARD.md).

For RoCell, the first learnable problem is English intent to a valid task
proposal. RoCell already compiles supported characters deterministically, so
training the model to memorize key coordinates or reproduce that compiler
would add risk without demonstrated value. Compare a deterministic parser,
unmodified Llama candidates, and only then a small response-SFT student.
Teacher-logit training is a separate, more complex experiment that requires
accessible logits and token alignment. LoRA/QLoRA is an adaptation method;
GGUF quantization is a deployment step.

Each model run must pin the exact base/teacher revisions, tokenizer and chat
template, licenses, training-source rights, dataset split/hash, config, seed,
served artifact hash, and frozen scorecard. The Llama 3.1 license allows some
output-based model improvement and sets conditions for distribution; check the
chosen release's [actual license](https://github.com/meta-llama/llama-models/blob/main/models/llama3_1/LICENSE)
before using teacher outputs or releasing a model.
