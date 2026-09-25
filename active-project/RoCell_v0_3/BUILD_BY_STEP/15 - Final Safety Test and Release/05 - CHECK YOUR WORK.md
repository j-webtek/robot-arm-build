# Step 15 — Check Your Work

Save original files under `06 - SAVE MEASUREMENTS AND PHOTOS/<BUILD_ID>/`, then record every test with `python scripts/record_step_result.py --step 15 ...`. Each `--evidence` path must be relative to that build-ID folder, remain contained within it, and name an existing regular file; `measurement_record.json` and `signoff.json` cannot cite themselves. A visual check alone is not evidence when a measured value is required.

Command form: `python scripts/record_step_result.py --step 15 --test TEST_ID --value "VALUE_OR_OBSERVATION" --unit "UNIT_OR_NA" --instrument "TOOL_ID_OR_METHOD" --evidence "photos/EXISTING_FILE.jpg" --result PASS --operator "OPERATOR_NAME"`. Repeat `--evidence` as needed. Raw JSON editing is an advanced recovery fallback only.

| Test | What must be true | How to check | Pass limit | Reviewed gate | Evidence to save | Record result in |
| --- | --- | --- | --- | --- | --- | --- |
| `15-A` | Station reinstall repeatability | Ten remove/reinstall cycles per station | X/Y no more than 0.25 mm; yaw no more than 0.20 degrees; Z no more than 0.20 mm | `station_remove_reinstall_repeatability_pass` | Cycle table and worst values | `scripts/record_step_result.py` |
| `15-B` | Structure and anchors | Apply 20 N lateral and 10 N functional station proofs for the recorded durations, plus 50 N axial at every board anchor for 60 seconds | Every load/duration is achieved; permanent shift no more than 0.10 mm; no damage or rotation | `workcell_commissioning_pass` | Force-tool ID, durations, before/after values, and photos | `scripts/record_step_result.py` |
| `15-C` | Empty-cell motion | Run the full path at the engineering-approved TCP speed/acceleration with devices removed | No collision and measured clearance never below the engineering-approved minimum | `workcell_commissioning_pass` | Approval ID, actual mm/s and mm/s^2, motion log/video, cycle count, and clearance table | `scripts/record_step_result.py` |
| `15-D` | Controlled first contact and final process | One device at a time at the engineering-approved first-contact TCP speed/force/travel with an observer at the E-stop | All approved numeric limits respected; no device shift, hard stop, unintended input, or cable load | `workcell_commissioning_pass` | Approval ID, actual mm/s, N and mm values, and signed commissioning record | `scripts/record_step_result.py` |

## Completion status

| Requirement | Current result |
| --- | --- |
| `station_remove_reinstall_repeatability_pass` | **NOT_TESTED** |
| `workcell_commissioning_pass` | **NOT_TESTED** |
| active-build step signoff | **NOT_STARTED** |

## If a check fails

Return to the earliest affected source step: board/anchors to Step 01, arm clamp/reinforcement to Step 02, keyboard to Steps 03-05, phone/TCP to Steps 06-10, tag placement to Steps 11-12, camera/vision to Step 13, or compliant tool/TCP to Step 14. Reopen and repeat every downstream acceptance affected by that change before commissioning resumes.

The step is PASS only when every test is in limit, all required reviewed gates are PASS, and `signoff.json` is signed PASS.
