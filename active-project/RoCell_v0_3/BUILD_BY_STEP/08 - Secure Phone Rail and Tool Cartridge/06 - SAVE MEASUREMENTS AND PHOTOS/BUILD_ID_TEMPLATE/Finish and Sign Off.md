# Step 08 — Finish and Sign Off

Use the copy inside your active build-ID folder as a work aid; never edit this generated template.

Use `scripts/sign_off_step.py` to update the authoritative `signoff.json`. Raw JSON editing is an advanced recovery fallback only.

- Required result: every required test row is complete and PASS
- Required result: every original measurement/photo/report path is recorded
- Required result: applicable reviewed project gates are PASS
- Required result: corrections and retests are preserved
- Required result: `open_holds` is empty
- Required result: operator, witness when required, and signed time are recorded

PASS command: `python scripts/sign_off_step.py --step 08 --status PASS --operator "OPERATOR_NAME"` (add `--witness "WITNESS_NAME"` when required).

HOLD command: `python scripts/sign_off_step.py --step 08 --status HOLD --operator "OPERATOR_NAME" --hold "REASON"` (repeat `--hold` for separate reasons).

The PASS helper derives accepted test IDs and refuses incomplete or invalid rows. If any item is incomplete, record HOLD and do not continue to the next step.
