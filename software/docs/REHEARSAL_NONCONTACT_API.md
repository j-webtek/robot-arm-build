# NC-01 retained noncontact gap report

This implementation runs existing source-bound collision readiness and strict
integer accuracy arithmetic, with no device, native helper, IK, plant, motion or
power action. It is **not physical noncontact acceptance**. The current result
is `BLOCKED`: three nominal readiness checks fail while five independent
software controls pass. NC-02/NC-03 and physical stage 14 remain open.

## Public API and trust boundary

`application/rehearsal_noncontact_binding.py` supplies frozen
`RehearsalNoncontactBinding(reference_binding, operator_id,
predecessor_receipt_sha256, predecessor_assessment_sha256,
predecessor_review_sha256, reference_evidence_sha256, source_context_json)`.
The reference argument is the exact `RehearsalReferenceBinding`, including its
original stage-13 operator, camera/optics/registration/controller/campaign and
independent **synthetic** final-power dependencies. The NC-01 operator is
separate. The three predecessor hashes identify complete canonical M1 payloads,
not embedded assessment self-hashes. This module does not authenticate a review;
the service/reopener must first audit those original reviewed records.

`read_noncontact_source_context(workspace) -> bytes` explicitly loads/revalidates
the locked simulation context and current strict accuracy policy. Its bounded
canonical snapshot retains the full nominal scene, historical context, original
policy UTF-8 bytes, reference-source-context hash and exact implementation hashes.
The reference context retains the pinned URDF XML and nominal tool/domain. Reads
and repeated source comparisons are not hostile-writer isolation. The service
still owns the original workspace fingerprint, source-check, cancellation,
deadline, lease and publication boundaries. No source read occurs in a view.

`evaluate_rehearsal_noncontact_stage(workspace, binding)` returns immutable
`RehearsalNoncontactEvidence`. Accessors are `canonical_bytes()`,
`evidence_sha256` (`evaluation_sha256` alias), `to_dict()`, `safe_summary()`,
`checks`, and `outcome`. Views decode fresh detached documents.

`verify_rehearsal_noncontact_evidence(payload, *, expected_binding,
expected_evidence_sha256, expected_evaluator_source_sha256)` requires all three
independent expected inputs. The evaluator hash is the single stage module's
actual file SHA-256. Other implementation hashes are in the source snapshot,
which is itself bound to the reviewed source context and workspace source.
The verifier reconstructs typed scene/model and structural collision coverage,
then independently checks integer arithmetic, term membership, freshness,
domain/epoch/provenance and the original canonical input-manifest digest. It
does not call collection, either original assessment entry point, a source
loader, IK, fitter, camera, serial provider or plant. Its structural audit is
not a pose/sweep collision query. Hash consistency is not hardware provenance.

## Complete retained calculations

- The actual `assess_current_collision_readiness` result is retained unchanged:
  historical **eye-on-arm** scope, 19 requirements, six nominal digital AABB
  proxies, no pinned-URDF collision elements, seven missing robot envelopes and
  six unknown attachment/clamp envelopes. The pure structural reconstruction
  must exactly reproduce the whole report, not just its status or count.
- The separate static contract retains all 26 body requirements and all nine
  required source names. Four source-design hashes are available (model,
  workcell layout, target catalog, static support); five reviewed geometry-source
  bindings are absent. These are not five claims that no design-related file
  exists. None of the 26 installed body envelopes is supplied; empty geometry
  is explicit and no guessed boxes or historical proxies are substituted.
- The original policy retains all ten noncontact terms and the unchanged
  illustrative historical phone/keyboard sensitivity record. That record is
  not a newly run sensitivity campaign.
- Six actual typed accuracy cases run through `assess_target_accuracy_budget`:
  `real_unmeasured`, `missing_term`, `stale_term`, `domain_term`,
  `target_margin`, `finite_control`. The real-term case has all ten observations
  explicitly `UNMEASURED`, with no admissible bindings. Its target boundary is
  synthetic and cannot certify a keyboard/phone region. The other cases use
  explicitly synthetic provenance, clock/epoch and term fixtures—even where
  the inner calculator's enum is `MEASURED_IN_DOMAIN`. No received sample or
  physical measurement is claimed by that fixture enum.

Each case's complete inputs are losslessly represented by `accuracy_common`
plus fixed `observation_replacements` keyed by term ID, `omitted_term_ids`,
and optional complete `term_bindings`/`target_geometry` replacements. Null
means reuse the exact common value; it is not an absent observation. This
closed representation does not accept arbitrary patches or silently default
missing fields. Every full `TargetBudgetAssessment` result is retained. The
verifier first demands the exact fixed case inputs, then proves the result
without calling the calculator again.

The finite control has ten 100 µm bounds: sum 1,000 µm, eroded radius 4,000 µm,
remaining margin 3,000 µm. The target-margin fault preserves erosion −500 µm
and margin −1,500 µm, rather than clamping either value. Missing/stale/domain
cases retain null aggregate and margin. All real-build terms stay unbounded.

The safe summary separates historical/static/accuracy sections, all six
control outcomes, exact stage-13 dependency hashes and the nominal
`nominal_tool_100mm` selection. It explicitly reports zero evaluated targets
out of 46 keyboard and 29 phone targets. Stage 13's `A`/`key_q` roundtrips do
not become reachability claims. Pose, route, sensitivity, visibility, dynamics
and physical motion remain `NOT_EVALUATED`. All actual physical effects are
zero; final physical power knowledge is not inferred from the predecessor.

## Bounds and verification

Canonical evidence cap: 112 KiB; source context: 32 KiB; existing M1 outer
JSON: **unchanged 128 KiB**. The actual injected-review test fixture contains
81,747 canonical bytes (116,464 pretty JSON bytes), a 13,063-byte source snapshot,
eight checks and six complete arithmetic results. Identifier values can change
the exact count; over-limit input is rejected, never truncated. No hash-only
substitute is used for technical reports.

The dedicated tests cover actual historical/calculator output equality,
independent pure verification, all source/session/predecessor dependencies,
body/term/provenance/count/margin tampering, canonical encoding, immutability,
source changes and unknown fields. The exact normal public `steps[].report`,
late-failure `failure.retained_noncontact_receipt` and dedicated-export
`receipt.evaluation` nesting pass the existing depth-12 sanitizer unchanged.
An actual temporary diagnostic export roundtrip preserves the original full
evaluation bytes and digest. That file test does not claim a qualified M1
review; original-store/public lifecycle tests belong to the integration owner.

Run:

```text
.venv/Scripts/python.exe -m pytest software/tests/unit/test_rehearsal_noncontact_binding.py software/tests/unit/test_rehearsal_noncontact_stage.py -q
```

At implementation handoff: 71 passed; both new source modules pass mypy and
Black. No controlled configuration, native provider, physical gate or global
budget was changed.
