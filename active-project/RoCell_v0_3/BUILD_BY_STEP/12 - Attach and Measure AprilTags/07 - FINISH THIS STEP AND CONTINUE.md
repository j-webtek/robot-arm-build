# Step 12 — Finish This Step and Continue

Do not continue unless every mandatory acceptance item is PASS and there is no unresolved HOLD.

## Required handoff results

- Required result: All six direct-applied tags pass size and physical placement metrology; vision detection remains pending Step 13.
- Required result: Installed center, yaw, edge lift, and optical Z are recorded per ID.
- Required result: After `tag_plane_placement_measured` is PASS, fiducials/apriltag_map.json is regenerated, verified as measured_installation for exactly T0-T3/K0/P0, and its SHA-256 is handed to Step 13.
- Required result: The application frame and spare set are labeled and stored.
- Required result: Installed items, returned tools, accepted spares, quarantined parts, and affected downstream datums are recorded in the build-ID folder.
- Required result: The responsible operator ran `python scripts/sign_off_step.py --step 12 --status PASS --operator "OPERATOR_NAME"`; the helper validated and completed `signoff.json`.

Raw signoff JSON editing is an advanced recovery fallback only. Use `--status HOLD --hold "REASON"` instead of forcing PASS when any requirement is incomplete.

After PASS, follow [02 - HOW TO SAVE MEASUREMENTS AND PHOTOS.md](<../02 - HOW TO SAVE MEASUREMENTS AND PHOTOS.md>) section 8: regenerate, run `python scripts/build_step_packages.py --check`, reopen the refreshed state, and confirm this step is `COMPLETE` before any handoff.

## Next step remains locked

Step 13 cannot be opened from this handoff until Step 12 is computed `COMPLETE`.
