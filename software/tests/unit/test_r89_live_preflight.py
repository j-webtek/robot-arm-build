"""Read-only live-launch gate; no arm or network connection."""

import json

import pytest

from scripts import preflight_r89_live_campaign as preflight


BOOT = "ab" * 16
OLD = "cd" * 16


def test_fresh_boot_only_software_ready_and_claims_fail_closed(tmp_path):
    fresh = preflight.assess_boot(tmp_path, BOOT, OLD)
    assert fresh["software_preflight_ready"]
    assert fresh["physical_clearance_verified"] is False
    assert fresh["source_pose_verified"] is False
    assert fresh["motion_authorized"] is False
    (tmp_path / f"pose-observation-{BOOT}.json").write_text("claimed")
    claimed = preflight.assess_boot(tmp_path, BOOT, OLD)
    assert not claimed["software_preflight_ready"]
    assert claimed["claim_files"] == [f"pose-observation-{BOOT}.json"]
    assert not preflight.assess_boot(tmp_path, OLD, OLD)["software_preflight_ready"]
    with pytest.raises(ValueError, match="boot"):
        preflight.assess_boot(tmp_path, "0" * 32, OLD)


def test_public_capabilities_exact_release_and_no_motion_claim(monkeypatch):
    caps = dict(schema="rocell.reviewed_hover_capabilities.v1", boot_id=BOOT,
                live_release_available=True, motion_authorized=False,
                maximum_legs=16,
                stamped_release_sha256=preflight.R89_RELEASE_SHA)

    class Response:
        status = 200
        def read(self, count):
            assert count == 513
            return json.dumps(caps).encode()

    class Connection:
        def __init__(self, address, port, timeout):
            assert (address, port, timeout) == ("127.0.0.1", 80, 3)
        def request(self, method, path, headers):
            assert (method, path) == ("GET", "/rocell/reviewed-hover/capabilities")
        def getresponse(self):
            return Response()
        def close(self):
            pass

    monkeypatch.setattr(preflight.http.client, "HTTPConnection", Connection)
    assert preflight.current_capabilities("127.0.0.1") == caps
    caps["motion_authorized"] = True
    with pytest.raises(ValueError, match="release/capabilities"):
        preflight.current_capabilities("127.0.0.1")
