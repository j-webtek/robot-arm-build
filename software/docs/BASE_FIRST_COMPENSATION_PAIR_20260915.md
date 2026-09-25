# First live base compensation pair

## Outcome

The first evidence-backed base inverse trial reached a reported endpoint of
**1.054687474 degrees** for a desired **1 degree**. A matched uncorrected control
stayed at **0.439453128 degrees**. Absolute reported endpoint error decreased
from **0.560546872 degrees** to **0.054687474 degrees**, a **90.24% reduction**
in this single pair.

This is encoder-reported joint-space evidence, not independently measured
tool-tip or board-space accuracy. No model coefficients were refitted on these
trials. The control command is outside the fitted command-anchor range; it is
an empirical control, not an extrapolated model prediction.

## Matched comparison

| Measurement | Corrected trial | Uncorrected control |
| --- | --- | --- |
| Actual reported starting base angle | 0.439453128 degrees | 0.439453128 degrees |
| Desired reported endpoint | 1 degree | 1 degree |
| Transmitted absolute target | 2.335749466 degrees | 1 degree |
| Final reported endpoint | 1.054687474 degrees | 0.439453128 degrees |
| Signed endpoint error | +0.054687474 degrees | -0.560546872 degrees |
| Experiment screen, at most 0.25 degree | Passed | Failed |
| Native result | REPORTED_SETTLED | NO_RESPONSE / HELD |
| Post-command capture | 5 seconds, 283 poses | 5 seconds, 283 poses |
| Confirmed command bytes | 63 | 64 |
| Final constant base tail | 231 samples, 4.125 seconds | 283 samples, 4.922 seconds |

The six-joint starting vectors matched exactly:
`[0.007669904, 0, 1.593806039, 0.050621366, -0.001533981, 3.149262558]` radians.
Both used logical base joint 1, speed parameter 20 and acceleration parameter 1,
the same hardware/tool/workcell context, and the same frozen model.

Both original exports independently reconstructed. Neither had capture errors,
other-joint drift beyond tolerance, joint excursion, uncertain writes or pending
I/O. All owned handles closed. The control's base samples remained unchanged;
its failure is retained as a measured control outcome, not rewritten as success.

## Four separately admitted live commands

1. Positioning: from 0.878906257 degrees, transmit the previously tested negative
   midpoint -0.708984380 degrees; observe 0.439453128 degrees.
2. Corrected trial: fresh baseline at 0.439453128 degrees; transmit 2.335749466
   degrees for desired 1 degree; observe 1.054687474 degrees.
3. Positioning: from 1.054687474 degrees, transmit the same negative midpoint;
   observe 0.439453128 degrees.
4. Control: fresh baseline at 0.439453128 degrees; transmit uncorrected 1 degree;
   observe 0.439453128 degrees.

Each positioning result was reviewed before a separate fresh baseline and the
next campaign. Positioning commands missed their raw targets and remain marked
as misses; their actual stable endpoints qualified the subsequent starting pose.
There were no automatic retries or automatic return commands.

Last observed pose after the control is the six-joint starting vector above.
There is no scheduled or continuous follow-on motion. A future trial still needs
a fresh native baseline; this document is not a freshness claim.

## Retained originals

All campaign bundles are under `software/runs/wizard-exports/<campaign-id>/`.
Each contains `<campaign-id>-parent-report.json` and the referenced originals.

| Role | Campaign | Parent-report SHA-256 |
| --- | --- | --- |
| First positioning | `campaign-442b4620d71242bba3c15ca5722d9b6e` | `0361cd3aec96038bafbb444831c3ae780487fec871733101ed47dd1975034470` |
| Corrected trial | `campaign-bf825a7653d4499b84dc0afd0b56695a` | `7f79c4561f2f38f126d28939ef976792d010e5b26078e2e8dd049d8dec529bdf` |
| Second positioning | `campaign-943af78f3d6040c8ab343db04b0bfbcf` | `8bba5f1ef49b95662809ad14a46eaa8f0f5daaf3f3cbd42ee2c7bcecf240cf69` |
| Control | `campaign-c29af73fb4204b85a4179c1a44b7198b` | `e6c8e2ec33ea6901c93a48bc744a1e53e5e601874beaf044f069d6feb6fc3934` |

Planning baseline operations, in the same order:

- `operation-37c1be874d0d49eca46a251ce06580cf`
- `operation-ff67af06cfa445ccb06c258eed090fbf`
- `operation-1b122f68ce9f412186da2dab8af43355`
- `operation-c6164034f45948a995894d9b3a58610a`

Each baseline session sent zero command bytes and closed cleanly. A separate
owned native baseline was also required inside each actual motion campaign.

Machine-readable comparison: `runs/BASE_FIRST_COMPENSATION_PAIR_20260915.json`.
The earlier offline proposal and the proposals embedded in these live originals
retain their historical `NOT_IMPLEMENTED_FOR_THIS_SCHEMA` metadata. Their bytes
were not rewritten. Current proposals describe the implemented v10/v11 profiles;
execution authority is determined by the versioned reviewed intent, not that
descriptive metadata field.

## Software delivered

- v10: one frozen base correction; v11: its one-command matched control.
- Evidence rebuilding during trusted staging, exact model/command/domain binding,
  startup synchronization, fresh starting-domain checks, and separate desired
  versus transmitted endpoint handling.
- Existing wizard review, cancellation, one-use execution and workspace export
  pipeline used for both live trials. Arbitrary browser-supplied angles remain
  unsupported.
- The 0.25-degree experiment screen participates in the native pass/fail decision.
- `application/base_compensation_comparison.py` reproduces paired scores from
  pinned original exports, checks six-joint start matching within 0.01 degree,
  context, trial roles, capture quality and stable final tails. It cannot send
  commands, train a model or authorize another trial.
- Training extraction excludes v10/v11 experiments so the frozen training set
  cannot silently absorb the evaluation pair.

Validation: 680 broad regression tests passed, with 156 intentionally inapplicable
wizard parameter combinations skipped. Expanded edge suite: 53 passed. Final
proposal/dataset/native-experiment/comparison targeted suite: 83 passed. These
counts overlap and must not be added as a unique-test total. Reports:
`base-compensation-native-regression-20260915.xml` and
`base-compensation-final-regression-20260915.xml` under `runs/`.

## Developer entry points

Trusted wizard intake:
`ArrivalWizardService.configure_base_compensation_experiment(...)`, with
`experiment_kind='CORRECTED'` or `'UNCORRECTED_CONTROL'`. Supply evidence from
`load_fixed_base_compensation_evidence(workspace)` and a reviewed historical
planning start. Staging rebuilds evidence; it does not open the arm. The existing
`run_positional_campaign` action performs reviewed one-use execution.

Bench entry point: `software/scripts/bench_attended_campaign.py` now accepts
`--base-experiment corrected` or `--base-experiment control`, alongside its existing
operator-confirmation, baseline and controller-directory arguments. These options
can move the arm; they are not preview-only. Startup synchronization is mandatory
inside these profiles and does not depend on an additional CLI opt-in.

To reproduce the saved pair without hardware, run this Python code from the
workspace root with the project's virtual environment:

```python
import json
from pathlib import Path
from rocell.application.base_compensation_comparison import compare_base_compensation_pair

root = Path('software/runs')
saved = json.loads((root / 'BASE_FIRST_COMPENSATION_PAIR_20260915.json').read_bytes())
def selection(role):
    row = saved[role]
    cid = row['campaign_id']
    return dict(directory=root / 'wizard-exports' / cid,
                report_name=cid + '-parent-report.json',
                report_sha256=row['report_sha256'])
print(compare_base_compensation_pair(corrected=selection('corrected'),
                                     control=selection('control')))
```

## Next bounded work

Repeat matched pairs with the same frozen candidate, pose, speed and approach.
Keep positioning separate, verify every endpoint, and retain misses as well as
passes. The next comparison should reverse the trial order to help expose order
effects. Review repeat variability before expanding destinations, speeds or joints.
One successful pair does not establish a general compensation map.
