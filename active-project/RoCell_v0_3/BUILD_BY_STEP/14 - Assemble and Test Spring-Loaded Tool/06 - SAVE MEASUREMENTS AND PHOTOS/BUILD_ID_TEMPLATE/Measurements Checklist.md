# Step 14 — Measurements Checklist

Use the copy inside your active build-ID folder as a work aid; never edit this generated template.

Record authoritative results with `scripts/record_step_result.py`; it safely updates `measurement_record.json`. Raw JSON editing is an advanced recovery fallback only.

Every `--evidence` path must be relative to the build-ID folder, remain contained within that folder, and point to an existing regular file. Neither `measurement_record.json` nor `signoff.json` is physical evidence. Repeat `--evidence` when one test has multiple files.

Command form:

`python scripts/record_step_result.py --step 14 --test TEST_ID --value "VALUE_OR_OBSERVATION" --unit "UNIT_OR_NA" --instrument "TOOL_ID_OR_METHOD" --evidence "photos/EXISTING_FILE.jpg" --result PASS --operator "OPERATOR_NAME"`

## 14-A — Compliant travel and force for every selected route

- Method: Measure axial travel and force through at least 20 cycles
- Pass limit: 3-6 mm smooth travel, free return, no coil bind, and force within the approved route-specific engineering-release envelope
- Required evidence: Approval ID, travel/force table, gauge ID, and cycle video
- Required record: value or observation
- Required record: unit and instrument ID
- Required record: original evidence file path
- Required record: PASS or FAIL result

## 14-D — TCP repeatability for every selected route

- Method: Ten remove/reinstall/probe cycles using the approved probe and reference frame
- Pass limit: XYZ range is at or below the approved route-specific engineering-release limit
- Required evidence: Approval ID, ten XYZ results per route, probe method, and calibrated TCP record
- Required record: value or observation
- Required record: unit and instrument ID
- Required record: original evidence file path
- Required record: PASS or FAIL result

## 14-BK — Keyboard rod/bushing/TPU retention and creep

- Method: Qualified axial force-gauge pull plus 24-hour creep check
- Pass limit: Meets both engineering-approved rod-bushing and keyboard-TPU proof loads/durations with no slip, permanent set, brittle adhesive, or loss of removability
- Required evidence: Approval ID, gauge ID, loads, durations, displacement, and before/after photos
- Required record: value or observation
- Required record: unit and instrument ID
- Required record: original evidence file path
- Required record: PASS or FAIL result

## 14-CK — Keyboard contact function

- Method: Hand key-contact test before robot use
- Pass limit: Reliable key input through the TPU tip without hard-stop loading
- Required evidence: Functional test record
- Required record: value or observation
- Required record: unit and instrument ID
- Required record: original evidence file path
- Required record: PASS or FAIL result

## 14-BP — Phone stylus/collar retention

- Method: Qualified axial force-gauge pull and repeated removal check
- Pass limit: Meets the engineering-approved stylus-collar proof load/duration with no slip, permanent set, or loss of serviceability
- Required evidence: Approval ID, gauge ID, load, duration, and before/after measurements
- Required record: value or observation
- Required record: unit and instrument ID
- Required record: original evidence file path
- Required record: PASS or FAIL result

## 14-CP — Phone stylus function

- Method: Hand capacitive-contact test before robot use
- Pass limit: Reliable touch response without hard-stop loading
- Required evidence: Manual tap count, successful taps, and video
- Required record: value or observation
- Required record: unit and instrument ID
- Required record: original evidence file path
- Required record: PASS or FAIL result

