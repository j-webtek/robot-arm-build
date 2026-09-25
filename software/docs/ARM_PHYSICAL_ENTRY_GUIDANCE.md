# Physical arm entry: what the wizard must establish next

Date: 2026-09-12. Companion to
[ROCELL-ARM-WIZARD-001](ARM_WIZARD_IMPLEMENTATION_PLAN.md).

## Important vendor finding

The official [RoArm-M3 introduction](https://docs.waveshare.net/RoArm-M3/Introduction/)
describes automatic joint initialization/movement at power-up and distinguishes
USB indicator illumination from external supply power. This is vendor behavior,
not a verified observation of our installed firmware or proof of isolation.
Accessed 2026-09-12. The English wiki fetch returned HTTP 403 during this review;
the linked official Chinese guide supplied the readable source.

Do not reconnect external power, initialize, home or issue torque commands merely
because Windows detects a COM port or the rehearsal passes. Power restoration
is a separate supervised transition. Closing USB is not an emergency stop.

## Work now visible in the Arm page and terminal

| Work | Owner | Required outcome |
| --- | --- | --- |
| Received controller association | Operator + hardware reviewer | Visible board/model revision associated with this arm, USB identity and applicable hardware documentation; bridge serial is not chassis identity |
| Supply separation and startup review | Hardware reviewer + operator | Applicable electrical review and expected startup/reset effects; cable-disconnected attestation remains separate from independent evidence |
| Original admission and retention | Developer | Authentic original references, durable one-use intent, exact retained outcome and restart handling; synthetic hashes cannot qualify entry |
| Supervised native lifecycle | Developer + reviewer | Reviewed registration and qualified exclusive open/settings/passive read/close with bounded containment and unknown-cleanup handling |
| First explicit passive attempt | Operator, after preceding requirements | Fresh metadata/setup confirmation and one explicitly started USB-only attempt with no outbound JSON or retry |
| Feedback through contact | Developer + operator | Canonical identity/power/startup, feedback, installed calibration, noncontact motion, then separate keyboard/phone contact acceptance |

The worklist is **guidance, not an admission evaluator**. It contains no PASS,
approval checkbox, editable authorization field or physical action. Refresh is
inert and returns detached values. Existing action validation and release holds
remain authoritative. Rehearsal mode shows the same physical prerequisites to
prevent a synthetic pass from being confused with received-device qualification.

## Operator information requested now

Without reconnecting external power or opening the enclosure, provide a photo of
any externally visible controller model/revision label and the current OLED
display. If the label is inaccessible, say so; do not disassemble the arm or
probe energized circuitry to answer. A display photograph is an observation,
not independent electrical certification or an installed-firmware identification.

The last recorded external-power-disconnected statement is historical until
reconfirmed at a future physical transition. Missing evidence stays unknown.
Software development continues while this information is pending.

## Code and acceptance scope

- `application/arm_wizard_readiness.py`: pure six-item worklist and startup warning.
- `ui/static/app.js`: bounded text-only rendering beside the existing guided action.
- Terminal consumes the same service projection; no second status engine.
- `tests/unit/test_arm_wizard_readiness.py`: both presentations, caller mutation
  isolation, zero runner calls for view, existing selection/hold precedence.
- No serial/camera access, firmware changes, power actions or physical passes.
- Selected regression: **156 passed in 20.31 seconds**, retained at
  `software/runs/pytest-arm-entry-guidance-20260912-01`. This covers readiness,
  native Arm UI, wizard service and terminal tests—not physical qualification.

## Camera dependency reconciliation

Current source includes the capture-workflow source-check fixture alias and its
fast regression. Run 07's complete workflow is useful evidence but not a pinned
release because source changed during execution. The next full acceptance must
use a verified stable/isolated checkout; see the
[source audit](STORAGE_EXISTING_ROOT_OBSERVATION_WORKORDER.md). Do not repeat the
old missing-alias diagnosis or combine tests from different source revisions.
