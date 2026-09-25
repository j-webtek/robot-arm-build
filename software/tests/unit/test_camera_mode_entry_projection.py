"""Fast browser/Python display parity; supplied state is explicitly MODELED."""

from copy import deepcopy
import json
from pathlib import Path
import shutil
import subprocess

import pytest

from rocell.application import physical_camera_mode_entry_projection as p


def model(status="ENTERED"):
    setup = dict(
        source_sha256="a" * 64,
        launch_session_id="wizard-" + "1" * 32,
        publication=dict(status="CURRENT", operation_id="MODELED-log"),
        session=dict(
            binding=dict(
                session_id="physical-camera-" + "2" * 32,
                cell_id="wizard-physical-camera-" + "3" * 16,
                launch_id="wizard-" + "4" * 32,
            ),
            verification=dict(session=dict(header_sha256="b" * 64)),
            stages=[
                dict(
                    state=(
                        "PASS" if i < 4 else "WAITING_OPERATOR" if i == 4 else "PENDING"
                    )
                )
                for i in range(15)
            ],
        ),
    )
    entry = dict(
        entry_id="cameramode-" + "5" * 32,
        entry_sha256="c" * 64,
        state="ENTERED",
        **{k: setup["session"]["binding"][k] for k in ("cell_id", "session_id")},
        origin_launch_id=setup["session"]["binding"]["launch_id"],
        entry_launch_id=setup["launch_session_id"],
        header_sha256="b" * 64,
        selected_identity_sha256="d" * 64,
        complete_review_sha256="e" * 64,
        operator_id="MODELED_op_é",
    )
    value = dict(
        schema=p.SCHEMA,
        source_sha256=setup["source_sha256"],
        launch_session_id=setup["launch_session_id"],
        publication=deepcopy(setup["publication"]),
        status=status,
        entry=entry,
        attempt=None,
        attempted=False,
        next_action=None,
        meaning=p.MEANING,
        **{flag: False for flag in p.FALSE_FIELDS},
    )
    if status == "ENTERED_PREPARATION_PENDING_REVIEW":
        setup["session"]["stages"][4]["state"] = "BLOCKED"
    elif status == "INCOMPLETE_HELD":
        entry["state"] = "INCOMPLETE"
        setup["session"]["stages"][4]["state"] = "PENDING"
    elif status == "READY_TO_ENTER":
        value.update(entry=None, next_action=p.ACTION)
        setup["session"]["stages"][4]["state"] = "PENDING"
    elif status == "NOT_STARTED":
        value["entry"] = None
    elif status == "HISTORICAL_HELD":
        setup["publication"]["status"] = value["publication"]["status"] = (
            "HISTORICAL_HELD"
        )
    elif status == "PENDING_PUBLICATION":
        value["entry"] = None
        setup["publication"]["status"] = value["publication"]["status"] = "PENDING"
    return dict(value=value, setup=setup)


def cases():
    result = [
        (name, model(name), True)
        for name in (
            "ENTERED",
            "ENTERED_PREPARATION_PENDING_REVIEW",
            "INCOMPLETE_HELD",
            "READY_TO_ENTER",
            "HISTORICAL_HELD",
            "PENDING_PUBLICATION",
            "NOT_STARTED",
        )
    ]
    mutations = [(("value", flag), True) for flag in p.FALSE_FIELDS] + [
        (("value", "extra"), True),
        (("value", "schema"), "wrong"),
        (("value", "next_action"), "arm_connect"),
        (("value", "source_sha256"), "f" * 64),
        (("value", "publication", "status"), "PENDING"),
        (("value", "entry", "entry_id"), "bad"),
        (("value", "entry", "header_sha256"), "f" * 64),
        (("value", "entry", "origin_launch_id"), "wizard-" + "f" * 32),
        (("value", "entry", "operator_id"), " bad "),
        (("value", "entry", "operator_id"), "é" * 33),
        (("value", "entry", "operator_id"), "<b>\nunsafe</b>"),
        (("setup", "session", "stages", 4, "state"), "PASS"),
        (("setup", "session", "stages", 5, "state"), "WAITING_OPERATOR"),
    ]
    for path, replacement in mutations:
        value = model()
        item = value
        for key in path[:-1]:
            item = item[key]
        item[path[-1]] = replacement
        result.append((str(path), value, False))
    for retained in p.RETENTION:
        value = model("HISTORICAL_HELD")
        e = value["value"]["entry"]
        value["value"].update(
            attempted=True,
            attempt=dict(
                entry_id=e["entry_id"],
                entry_sha256=e["entry_sha256"],
                retention=retained,
                event_count=0,
            ),
        )
        result.append((retained, value, True))
        invalid = deepcopy(value)
        invalid["value"]["attempt"]["event_count"] = True
        result.append((retained + "-bool", invalid, False))
    return result


CASES = cases()


@pytest.fixture(scope="module")
def browser_answers():
    node = shutil.which("node")
    assert node, "Node is required to verify both wizard interfaces"
    script = (
        Path(__file__).resolve().parents[2] / "src/rocell/ui/static/app.js"
    ).read_text(encoding="utf-8")
    section = script[
        script.index("  const cameraModeEntryFlags") : script.index(
            "  function physicalCameraSetup()"
        )
    ]
    harness = r"""
const fs=require('fs'), input=JSON.parse(fs.readFileSync(0,'utf8'));
function cameraConfigurationValidators(){return {exact:(x,keys)=>x!==null&&typeof x==='object'&&!Array.isArray(x)&&Object.keys(x).length===keys.length&&keys.every(k=>Object.hasOwn(x,k)),digest:x=>typeof x==='string'&&/^[0-9a-f]{64}$/.test(x)}}
eval(input.script+'\nprocess.stdout.write(JSON.stringify(input.cases.map(c=>cameraModeEntryValid(c.value,c.setup))))');
"""
    response = subprocess.run(
        [node, "-e", harness],
        input=json.dumps(dict(script=section, cases=[c[1] for c in CASES])),
        capture_output=True,
        encoding="utf-8",
        timeout=20,
        check=True,
    )
    return json.loads(response.stdout)


@pytest.mark.parametrize(
    "index,case", list(enumerate(CASES)), ids=[c[0] for c in CASES]
)
def test_browser_and_python_agree_without_mutation(index, case, browser_answers):
    _, value, expected = case
    previous = deepcopy(value)
    assert p.mode_entry_projection_valid(**value) is expected
    assert browser_answers[index] is expected
    assert value == previous
