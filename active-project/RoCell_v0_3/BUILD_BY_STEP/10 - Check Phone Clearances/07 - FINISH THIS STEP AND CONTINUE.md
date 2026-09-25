# Step 10 — Finish This Step and Continue

Do not continue unless every mandatory acceptance item is PASS and there is no unresolved HOLD.

## Required handoff results

- Required result: All four no-go checks have raw measurements and photos.
- Required result: Minimum clearance is recorded for the final case and cable state.
- Required result: After evidence is complete, the phone and keyboard are unloaded and protected from the clean tag-transfer work in Step 11.
- Required result: Installed items, returned tools, accepted spares, quarantined parts, and affected downstream datums are recorded in the build-ID folder.
- Required result: The responsible operator ran `python scripts/sign_off_step.py --step 10 --status PASS --operator "OPERATOR_NAME"`; the helper validated and completed `signoff.json`.

Raw signoff JSON editing is an advanced recovery fallback only. Use `--status HOLD --hold "REASON"` instead of forcing PASS when any requirement is incomplete.

After PASS, follow [02 - HOW TO SAVE MEASUREMENTS AND PHOTOS.md](<../02 - HOW TO SAVE MEASUREMENTS AND PHOTOS.md>) section 8: regenerate, run `python scripts/build_step_packages.py --check`, reopen the refreshed state, and confirm this step is `COMPLETE` before any handoff.

## Next step remains locked

Step 11 cannot be opened from this handoff until Step 10 is computed `COMPLETE`.
