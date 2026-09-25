# Step 00 — Finish This Step and Continue

Do not continue unless every mandatory acceptance item is PASS and there is no unresolved HOLD.

## Required handoff results

- Required result: All core parts are accepted, labeled, and assigned to their step kits.
- Required result: The retained 00A seam coupon remains with the keyboard master kit.
- Required result: The accepted 00B phone-width, locator, M3-insert, and washer results remain with the phone/TCP kit; the failed 00B nut and cable-saddle objects remain labeled as superseded evidence.
- Required result: The accepted Job 03C1 rail and its captive-nut and wide-tie evidence remain with the phone/TCP kit.
- Required result: Every selected job has a native QIDI Studio evidence record.
- Required result: Installed items, returned tools, accepted spares, quarantined parts, and affected downstream datums are recorded in the build-ID folder.
- Required result: The responsible operator ran `python scripts/sign_off_step.py --step 00 --status PASS --operator "OPERATOR_NAME"`; the helper validated and completed `signoff.json`.

Raw signoff JSON editing is an advanced recovery fallback only. Use `--status HOLD --hold "REASON"` instead of forcing PASS when any requirement is incomplete.

After PASS, follow [02 - HOW TO SAVE MEASUREMENTS AND PHOTOS.md](<../02 - HOW TO SAVE MEASUREMENTS AND PHOTOS.md>) section 8: regenerate, run `python scripts/build_step_packages.py --check`, reopen the refreshed state, and confirm this step is `COMPLETE` before any handoff.

## Next step remains locked

Step 01 cannot be opened from this handoff until Step 00 is computed `COMPLETE`.
