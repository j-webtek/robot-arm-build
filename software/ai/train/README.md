# Training

Training begins after the offline benchmark and deterministic/unmodified-model
baselines show a measured need. Track pinned configs, model revisions, seed,
data hash, license and output-use check, tokenizer/chat template, and final
scorecard here. Keep adapters, checkpoints, exports, and run logs in ignored
locations.

The first candidate method is response SFT on verified task proposals.
Preference or logit distillation is a later experiment tied to a specific
failure pattern. Existing ADB-agent Axolotl settings are historical examples,
not defaults for RoCell.
