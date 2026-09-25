"""Small modeled display fixtures, not original evidence or device qualification.

One batched Node invocation compares the browser's display-only checks with
Python. The composed service test separately exercises real original codecs.
"""

from copy import deepcopy
import json
from pathlib import Path
import shutil
import subprocess

import pytest

from rocell.application import physical_usb_complete_projection as p
from rocell.application.physical_usb_complete_series import (
    PHASES,
    PHASE_CHECKS,
    PHASE_STATUS,
)
from rocell.application.physical_usb_reboot_phase import COMPARISON_FIELDS


def modeled(state="REVIEW_PENDING", *, reject=False, blocked=False):
    phases = []
    for i, names in enumerate(PHASE_CHECKS):
        checks = [
            dict(check_id=name, passed=not (blocked and i == 3 and j == 0))
            for j, name in enumerate(names)
        ]
        phases.append(
            dict(
                phase_sha256=str(i + 1) * 64,
                status=(
                    "HELD" if any(not c["passed"] for c in checks) else PHASE_STATUS[i]
                ),
                checks=checks,
            )
        )
    phases[3]["comparisons"] = [
        dict(field=name, status="MATCHED") for name in COMPARISON_FIELDS
    ]
    outer = dict(
        publication=dict(status="CURRENT"),
        status=state,
        plan={"MODELED": True},
        next_action=p.EXPORT,
        **{
            key: dict(phase_record=row, state="RETAINED_BLOCKED")
            for key, row in zip(("baseline", "absence", "reconnect", "reboot"), phases)
        },
    )
    outer["baseline"]["host_boot"] = dict(original_state="BOOT_RETAINED")
    checks = [
        dict(check_id="PHYSICAL_PLAN", passed=True),
        dict(check_id="BASELINE_PHYSICAL_OWNED_BOOT", passed=True),
        *(
            dict(check_id=name + "_COMPLETE", passed=row["status"] == status)
            for name, row, status in zip(PHASES, phases, PHASE_STATUS)
        ),
        *(
            dict(check_id=name + "__" + c["check_id"], passed=c["passed"])
            for name, row in zip(PHASES, phases)
            for c in row["checks"]
        ),
    ]
    missing = [c["check_id"] for c in checks if not c["passed"]]
    assessment = dict(
        verdict="BLOCKED" if missing else p.ELIGIBLE,
        checks=checks,
        missing_requirements=missing,
        phases=[
            dict(
                phase=name,
                phase_sha256=row["phase_sha256"],
                status=row["status"],
                missing_checks=[
                    c["check_id"] for c in row["checks"] if not c["passed"]
                ],
            )
            for name, row in zip(PHASES, phases)
        ],
        comparisons=deepcopy(phases[3]["comparisons"]),
    )
    complete = dict(
        series_id="usbseries-" + "7" * 32,
        state=state,
        series_sha256="a" * 64,
        assessment_sha256="b" * 64,
        review_sha256=None,
        assessment=assessment,
        review=None,
    )
    stage = "REVIEW_PENDING"
    if state == "COMPLETE_REVIEW_READY":
        complete = None
        outer["next_action"], stage = p.ASSESS, "BLOCKED"
    elif state == "ASSESSMENT_REQUESTED":
        complete.update(series_sha256=None, assessment_sha256=None, assessment=None)
        stage = "WAITING_OPERATOR"
    elif state == "REVIEW_PENDING":
        outer["next_action"] = p.REVIEW
    else:
        complete["review_sha256"] = "c" * 64
        complete["review"] = dict(
            decision="REJECT" if reject else "ACKNOWLEDGE_EXACT",
            verdict="BLOCKED" if reject or blocked else p.REVIEW_ELIGIBLE,
            reviewer_id="MODELED-distinct-reviewer",
            review_launch_id="wizard-" + "8" * 32,
            reviewed_at_utc_ns=1_789_000_000_000_000_000,
            series_sha256="a" * 64,
            assessment_sha256="b" * 64,
        )
        stage = (
            "PASS"
            if state == "REVIEWED_PASS"
            else "BLOCKED" if state == "REVIEWED_BLOCKED" else "REVIEW_PENDING"
        )
    outer["complete"] = complete
    # Match the actual legacy baseline display rather than an invented schema.
    del outer["baseline"]["phase_record"]["status"]
    return dict(
        outer=outer,
        stages=[dict(state=s) for s in ("PASS", "PASS", "PASS", stage, "PENDING")],
    )


def cases():
    result = []
    for state in (
        "COMPLETE_REVIEW_READY",
        "ASSESSMENT_REQUESTED",
        "REVIEW_PENDING",
        "REVIEWED_PASS",
        "REVIEWED_BLOCKED",
        "INCOMPLETE",
    ):
        value = modeled(state, reject=state == "REVIEWED_BLOCKED")
        result.append(("valid-" + state, value, True))
    result.append(
        ("negative-final-phase", modeled("REVIEWED_BLOCKED", blocked=True), True)
    )
    for path, replacement in [
        (("complete", "state"), "REVIEWED_PASS"),
        (("complete", "state"), "INVENTED"),
        (("complete", "series_id"), "usbseries-bad"),
        (("complete", "assessment_sha256"), None),
        (("complete", "series_sha256"), None),
        (("complete", "assessment", "checks", 0, "passed"), 1),
        (("complete", "assessment", "checks", 0, "passed"), False),
        (("complete", "assessment", "phases", 0, "phase_sha256"), "f" * 64),
        (("complete", "assessment", "comparisons", 0, "status"), "CHANGED"),
        (("complete", "assessment", "missing_requirements"), ["INVENTED"]),
        (("complete", "assessment", "extra"), True),
        (("complete", "extra"), True),
        (("next_action",), p.ASSESS),
        (("next_action",), "arm_connect"),
        (("status",), "REVIEWED_PASS"),
        (("reboot", "state"), "INCOMPLETE"),
    ]:
        value = modeled()
        target = value["outer"]
        for key in path[:-1]:
            target = target[key]
        target[path[-1]] = replacement
        result.append(("invalid-" + str(path) + str(replacement), value, False))
    for field, replacement in (
        ("decision", "REJECT"),
        ("verdict", "BLOCKED"),
        ("assessment_sha256", "f" * 64),
        ("series_sha256", "f" * 64),
        ("reviewer_id", " bad "),
        ("review_launch_id", "bad"),
        ("reviewed_at_utc_ns", True),
        ("reviewed_at_utc_ns", -1),
        ("extra", 1),
    ):
        value = modeled("REVIEWED_PASS")
        value["outer"]["complete"]["review"][field] = replacement
        result.append(("review-" + field, value, False))
    for index in (3, 4):
        value = modeled()
        value["stages"][index]["state"] = "PASS"
        result.append(("stage-drift-" + str(index), value, False))
    historical = modeled("REVIEWED_PASS")
    historical["outer"]["publication"]["status"] = "HISTORICAL_HELD"
    historical["outer"]["status"] = "HISTORICAL_HELD"
    result.append(("historical-no-replay", historical, True))
    pending = modeled()
    pending["outer"].update(
        publication=dict(status="PENDING"),
        status="NOT_DECLARED",
        next_action=None,
        **{
            key: None
            for key in (
                "plan",
                "baseline",
                "absence",
                "reconnect",
                "reboot",
                "complete",
            )
        },
    )
    result.append(("withheld-pending", pending, True))
    for key in ("plan", "baseline", "absence", "reconnect", "reboot", "complete"):
        bad = deepcopy(pending)
        bad["outer"][key] = {"MODELED": True}
        result.append(("pending-leak-" + key, bad, False))
    return result


CASES = cases()


@pytest.fixture(scope="module")
def browser_answers():
    node = shutil.which("node")
    if not node:
        pytest.skip("Optional Node unavailable")
    script = (
        Path(__file__).resolve().parents[2] / "src/rocell/ui/static/app.js"
    ).read_text(encoding="utf-8")
    section = script[
        script.index("  const usbCompleteStates=") : script.index(
            "  function usbQualificationProjection("
        )
    ]
    harness = r"""
const fs=require('fs'),input=JSON.parse(fs.readFileSync(0,'utf8'));
function receivedCameraValidators(){return {v:{exact:(x,keys)=>x!==null&&typeof x==='object'&&!Array.isArray(x)&&Object.keys(x).length===keys.length&&keys.every(k=>Object.prototype.hasOwnProperty.call(x,k)),digest:x=>typeof x==='string'&&/^[0-9a-f]{64}$/.test(x)},launch:x=>typeof x==='string'&&/^wizard-[0-9a-f]{32}$/.test(x)}}
eval(input.script+'\nprocess.stdout.write(JSON.stringify(input.cases.map(c=>{try{return usbCompleteValid(c.outer,c.stages)}catch(e){return false}})))');
"""
    run = subprocess.run(
        [node, "-e", harness],
        input=json.dumps(dict(script=section, cases=[row[1] for row in CASES])),
        capture_output=True,
        encoding="utf-8",
        timeout=20,
        check=True,
    )
    return json.loads(run.stdout)


@pytest.mark.parametrize(
    "index,case", list(enumerate(CASES)), ids=[row[0] for row in CASES]
)
def test_python_and_browser_reject_same_contradictions(index, case, browser_answers):
    _, value, expected = case
    before = deepcopy(value)
    assert p.complete_projection_valid(**value) is expected
    assert browser_answers[index] is expected
    assert value == before
