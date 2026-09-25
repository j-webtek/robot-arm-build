"""Staged-source regression checks, not proof of live scheduling or clearance."""
from pathlib import Path
import hashlib
import json


ROOT=Path(__file__).resolve().parents[2]
STAGE=ROOT/'.firmware-tools/configured-diagnostic-candidate-r23/RoArm-M3_example'


def text(name):
    return (STAGE/name).read_text()


def test_every_preparation_path_checks_shoulder_reservation_first():
    entries=[('diagnostic_http.h','bool rocellPrepareHoldChallenge(){'),
        ('configured_pair_board_routes.h','bool operator()(){'),
        ('configured_pair_board_routes.h','bool rocellConfigurationBusInactive(void*){'),
        ('configured_recovery_board_routes.h','bool operator()(char* out,size_t capacity){'),
        ('pose_observation_board.h','bool rocellReservePose(void*){')]
    for name,signature in entries:
        body=text(name).split(signature,1)[1].lstrip()
        assert body.startswith('if(rocellShoulderReserved)return false;'),name


def test_reserved_loop_cannot_fall_through_to_other_owners():
    body=text('diagnostic_boot.h').split('void loop(){',1)[1].lstrip()
    assert body.startswith('if(rocellDiagnosticBootReady&&rocellShoulderReserved){pollShoulderSession();delay(1);return;}')
    setup=text('diagnostic_boot.h').split('void loop(){',1)[0]
    assert 'webCtrlServer(' not in setup and 'initHttpWebServer(' not in setup
    assert 'jsonCmdReceiveHandler(' not in body


def test_prepare_rejects_existing_owners_before_sticky_reservation():
    body=text('shoulder_board_session.h').split('bool rocellPrepareShoulder(){',1)[1]
    checks=body.split('rocellShoulderReserved=true;',1)[0]
    for flag in ('rocellDiagnosticOwned','rocellPoseReserved','rocellHoldChallengeAttempted',
                 'rocellHoldConfigured','rocellRecoveryReserved','PairNetworkPhase::New'):
        assert flag in checks
    assert 'rocellShoulderReserved=false' not in body
    assert 'LittleFS.open("/rocell-hold.key","r")' in body
    assert 'LittleFS.open("/rocell-hold.key","w")' not in body
    # r23 is immutable history, not an alias for the evolving working source.
    receipt=ROOT/'runs/wizard-exports/wizard-20260919T183847722083Z-b678aeb19d894ca698948a169a198c85/attachment-pair-candidate-review.json'
    review=json.loads(receipt.read_bytes())
    compile_report=json.loads((receipt.parent.parent/review['compile_export_id']/'attachment-compile-review.json').read_bytes())
    for name in ('shoulder_board_session.h','shoulder_session_owner.h','shoulder_authorized_start.h'):
        path=STAGE/name
        assert hashlib.sha256(path.read_bytes()).hexdigest()==compile_report['source_hashes'][str(path.relative_to(ROOT))]
