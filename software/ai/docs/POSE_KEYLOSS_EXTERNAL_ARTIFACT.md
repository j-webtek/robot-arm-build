# Pose-keyloss external checkpoint

This package records the exact identity and development evidence for the
translation-weighted pose checkpoint requested by GitHub issues #56 and #61.
The 1,111,650-byte checkpoint remains external to Git at:

```text
software/ai/results/translation_weighted_v0_translation_weighted/pose_model.pt
```

Its SHA-256 is
`0fd4ee3edd1dc6e0068c6e1530fdf7017a77a3e7841334682272e99aa344125d`.
The manifest is
[`translation_weighted_pose_keyloss_v0.external.json`](../manifests/translation_weighted_pose_keyloss_v0.external.json).

## Provenance and reproduction

The source and plan were frozen in commit
`fe20dc15376361f38049e4791583af72b62e5a77`. From that commit, with its Python,
PyTorch/CUDA dependencies and external starting checkpoint available at the
path and digest pinned in `translation_weighted_v0_plan.json`, run:

```powershell
python software/ai/vision/train_translation_weighted.py
```

The command deterministically defines the study inputs, seed, sample order,
budget, loss weights and development-MSE selection rule. Reproduced bytes must
still match both the manifest size and digest before use as evidence.

## Clean-clone check

From a fresh worktree where ignored external results are absent:

```powershell
python scripts/ci/check_external_artifact.py software/ai/manifests/translation_weighted_pose_keyloss_v0.external.json --root . --allow-unavailable
python software/ai/eval/verify_pose_checkpoint_artifact.py --root . --expect external_artifact_unavailable
```

Both commands must emit the exact status `external_artifact_unavailable`. The
allow flag changes only the generic checker's exit code; it does not turn
absence into verification.

## Artifact-present check

After the externally retained checkpoint is placed at the manifest's exact
repository-relative path, run without `--allow-unavailable`:

```powershell
python scripts/ci/check_external_artifact.py software/ai/manifests/translation_weighted_pose_keyloss_v0.external.json --root .
python software/ai/eval/verify_pose_checkpoint_artifact.py --root . --expect verified
```

`verified` means only that size and SHA-256 match. It does not promote the
candidate, install runtime qualification, authorize controller access, or
establish real-camera or physical performance.

## Retained evidence

- Clean-clone receipt:
  [`pose_keyloss_external_artifact_unavailable_receipt.json`](../eval/pose_keyloss_external_artifact_unavailable_receipt.json),
  SHA-256 `e9347f172421bc6faa8b8a75b176cbcf25f8e5b75ca6518e84673008abb8110c`.
- Artifact-present receipt:
  [`pose_keyloss_external_artifact_verified_receipt.json`](../eval/pose_keyloss_external_artifact_verified_receipt.json),
  SHA-256 `09d0b08b20acbd120b255e018a69b1867de2c2b99fe7b497789adcc793ca8b7a`.
- Compact development scorecard:
  [`pose_keyloss_external_artifact_scorecard.json`](../eval/pose_keyloss_external_artifact_scorecard.json),
  SHA-256 `0fb3077fcea31a61b4d6c977e4266f5b313ac69497af021bf697e02dcbc5fb3f`.

The unavailable receipt was generated from fresh detached worktree commit
`88a018d75cb8245d079148503aa46929a0c4efc9`. The verified receipt was generated
separately against externally retained bytes. Neither receipt contains model
weights or grants runtime authority.
