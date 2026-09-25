# Step 14 — Check Your Work

Save original files under `06 - SAVE MEASUREMENTS AND PHOTOS/<BUILD_ID>/`, then record every test with `python scripts/record_step_result.py --step 14 ...`. Each `--evidence` path must be relative to that build-ID folder, remain contained within it, and name an existing regular file; `measurement_record.json` and `signoff.json` cannot cite themselves. A visual check alone is not evidence when a measured value is required.

Command form: `python scripts/record_step_result.py --step 14 --test TEST_ID --value "VALUE_OR_OBSERVATION" --unit "UNIT_OR_NA" --instrument "TOOL_ID_OR_METHOD" --evidence "photos/EXISTING_FILE.jpg" --result PASS --operator "OPERATOR_NAME"`. Repeat `--evidence` as needed. Raw JSON editing is an advanced recovery fallback only.

| Test | What must be true | How to check | Pass limit | Reviewed gate | Evidence to save | Record result in |
| --- | --- | --- | --- | --- | --- | --- |
| `14-A` | Compliant travel and force for every selected route | Measure axial travel and force through at least 20 cycles | 3-6 mm smooth travel, free return, no coil bind, and force within the approved route-specific engineering-release envelope | `tool_assembled_motion_pass` | Approval ID, travel/force table, gauge ID, and cycle video | `scripts/record_step_result.py` |
| `14-D` | TCP repeatability for every selected route | Ten remove/reinstall/probe cycles using the approved probe and reference frame | XYZ range is at or below the approved route-specific engineering-release limit | `tool_assembled_motion_pass` | Approval ID, ten XYZ results per route, probe method, and calibrated TCP record | `scripts/record_step_result.py` |
| `14-BK` | Keyboard rod/bushing/TPU retention and creep | Qualified axial force-gauge pull plus 24-hour creep check | Meets both engineering-approved rod-bushing and keyboard-TPU proof loads/durations with no slip, permanent set, brittle adhesive, or loss of removability | `rod_bushing_retention_pass` | Approval ID, gauge ID, loads, durations, displacement, and before/after photos | `scripts/record_step_result.py` |
| `14-CK` | Keyboard contact function | Hand key-contact test before robot use | Reliable key input through the TPU tip without hard-stop loading | `keyboard_tpu_batch_postprint_pass` | Functional test record | `scripts/record_step_result.py` |
| `14-BP` | Phone stylus/collar retention | Qualified axial force-gauge pull and repeated removal check | Meets the engineering-approved stylus-collar proof load/duration with no slip, permanent set, or loss of serviceability | `stylus_collar_retention_pass` | Approval ID, gauge ID, load, duration, and before/after measurements | `scripts/record_step_result.py` |
| `14-CP` | Phone stylus function | Hand capacitive-contact test before robot use | Reliable touch response without hard-stop loading | `stylus_function_pass` | Manual tap count, successful taps, and video | `scripts/record_step_result.py` |

## Completion status

| Requirement | Current result |
| --- | --- |
| `tool_assembled_motion_pass` | **NOT_TESTED** |
| `stylus_function_pass` | **NOT_TESTED** |
| active-build step signoff | **NOT_STARTED** |

## If a check fails

Return to Step 00 for any failed printed body, cap, adapter, bushing, collar, TPU tip, hardware fit, spring/gripper measurement, or route-retention qualification. Keep reversible assembly, force/travel, functional-contact, or TCP calibration rework in Step 14. Reopen downstream signoffs after either correction.

The step is PASS only when every test is in limit, all required reviewed gates are PASS, and `signoff.json` is signed PASS.
