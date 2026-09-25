"""Synthetic planning constraints only; these numbers are not live settings."""

from copy import deepcopy
import json
import pytest

from rocell.motion.characterization_plan import AXES, SCHEMA, freeze_campaign, FrozenCampaign


def candidate():
    start = dict.fromkeys(AXES, 0)
    target = dict(start, x_mm=1)
    return {"schema":SCHEMA, "campaign_id":"synthetic-pair", "frame":"robot_base",
        "evidence":{**dict.fromkeys(("source_sha256", "configuration_sha256", "firmware_review_sha256",
                     "geometry_sha256"), 'a'*64), "usb_identity":"synthetic", "tool_payload_id":"none"},
        "limits":{"minimum_pose":dict.fromkeys(AXES,-10), "maximum_pose":dict.fromkeys(AXES,10),
                  "max_translation_mm":2, "max_rotation_rad":.1, "min_spd":.01,"max_spd":.1,
                  "max_trials":4,"max_duration_s":10},
        "trials":[{"trial_id":"out", "command_family":"T104", "start":start, "target":target,
                   "spd":.05, "dwell_s":.5,"timeout_s":2,
                   "stop":{"max_read_gap_s":.1,"position_tolerance_mm":.1,
                           "angle_tolerance_rad":.01,"max_endpoint_error_mm":.5}},
                  {"trial_id":"back", "command_family":"T104", "start":target,"target":start,
                   "spd":.05,"dwell_s":.5,"timeout_s":2,
                   "stop":{"max_read_gap_s":.1,"position_tolerance_mm":.1,
                           "angle_tolerance_rad":.01,"max_endpoint_error_mm":.5}}]}


def test_frozen_detached_canonical_and_no_authority():
    data = candidate(); plan = freeze_campaign(data)
    data['trials'][0]['spd'] = 999
    assert plan.to_dict()['trials'][0]['spd'] == .05
    assert freeze_campaign(plan.to_dict()).sha256 == plan.sha256
    changed = plan.to_dict(); changed['trials'][0]['spd'] = .06
    assert freeze_campaign(changed).sha256 != plan.sha256
    assert not plan.preview()['physical_ready']
    assert not plan.preview()['motion_authorized']
    assert plan.preview()['maximum_duration_s'] == 4
    assert FrozenCampaign(plan.canonical_bytes) == plan


@pytest.mark.parametrize('path,value', [
    (('frame',),'board'), (('trials',0,'spd'),True), (('trials',0,'spd'),float('nan')),
    (('trials',0,'spd'),0), (('trials',0,'spd'),.2), (('trials',0,'command_family'),'T1041'),
    (('trials',0,'timeout_s'),.1), (('trials',0,'target','x_mm'),3),
    (('trials',0,'target','pitch_rad'),1), (('trials',1,'start','x_mm'),0),
    (('trials',1,'trial_id'),'out'), (('limits','max_trials'),True),
    (('limits','max_trials'),129), (('limits','max_duration_s'),1),
    (('limits','minimum_pose','z_mm'),11), (('evidence','geometry_sha256'),'unknown'),
    (('trials',0,'stop','max_read_gap_s'),1), (('trials',0,'spd'),10**1000),
], ids=['frame','bool','nan','zero','speed-bound','direct','timeout','travel','rotation',
        'discontinuity','duplicate','bool-count','count-cap','duration','envelope','hash','gap','huge'])
def test_rejects_invalid_plan(path,value):
    data = candidate(); cursor=data
    for key in path[:-1]: cursor=cursor[key]
    cursor[path[-1]]=value
    with pytest.raises(ValueError): freeze_campaign(data)


def test_no_implicit_acceleration_repetition_or_noop():
    for field in ('acc','repetitions','motion_authorized'):
        data=candidate(); data['trials'][0][field]=1
        with pytest.raises(ValueError): freeze_campaign(data)
    data=candidate(); data['trials'][0]['target']=deepcopy(data['trials'][0]['start'])
    with pytest.raises(ValueError): freeze_campaign(data)


def test_direct_construction_cannot_skip_validation():
    data=candidate(); data['trials'][0]['spd']=-1
    with pytest.raises(ValueError): FrozenCampaign(json.dumps(data).encode())
