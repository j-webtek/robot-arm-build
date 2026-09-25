import pytest

from rocell.application.heldout_pair_validation import draft


def frozen():
    return dict(parameters=dict(
        bands=[[2, 9.666666666666666], [-7, -1]],
        constant=[6.5, -4.333333333333333],
        directional={"-1": [9.666666666666666, -7], "1": [3.3333333333333335, -1.6666666666666667]}),
        sha256="963df1b4975ca385e6b8d9cd9509695fdfa4838f0cab9bcde9444e28c28452e5")


def test_heldout_plan_is_fixed_and_inert():
    value = draft(frozen(), [[0, 4095]] * 7,
                  evidence_export="wizard-20260920T195904937964Z-0a6902dbff5340e887db1d93b27259f6",
                  evidence_model_sha256=frozen()["sha256"])
    assert value["desired"] == [2390, 1725]
    assert value["candidate"]["manifest"]["goals"] == [[2377, 1737], [2388, 1726]]
    assert value["control"]["manifest"]["goals"] == [[2377, 1737], [2389, 1725]]
    assert value["candidate"]["frozen_prediction"] == [2390, 1725]
    assert value["control"]["frozen_prediction"] == [2391, 1724]
    assert value["endpoint_is_new"] and value["command_is_interpolation"]
    assert not value["hardware_access"] and not value["movement_authorized"]


def test_heldout_plan_rejects_changed_model_binding():
    with pytest.raises(ValueError):
        draft(frozen(), [[0, 4095]] * 7, evidence_export="wizard-x",
              evidence_model_sha256="0" * 64)
