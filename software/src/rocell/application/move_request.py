"""Serializable request identity for the existing one-use joint move route.

Constructed from a validated transaction before reservation publication. This
record describes intent; it cannot be submitted as a permit or replayed.
"""
from copy import deepcopy
import hashlib

from rocell import __version__
from rocell.application.first_motion_contract import canonical


def describe_request(*, attempt_id, transaction, address, mac):
    command = transaction['command']
    configuration = dict(
        schema='rocell.bounded_move_configuration.v1',
        application_version=__version__,
        transport='WIFI_HTTP', address=address, expected_mac=mac,
        firmware_version=None, calibration_id=None,
        frame='CONTROLLER_JOINT', units='radians', joint_order=['b','s','e','t','r','g'],
        speed_policy=dict(spd=command['spd'], acc=command['acc'],
                          units='FIRMWARE_NATIVE_NOT_PHYSICAL_VELOCITY'),
        endpoint_policy=deepcopy(transaction['policy']),
        completion_budget_ns=transaction['completion_budget_ns'],
        scope='EXISTING_BOUNDED_ROLL_ROUTE_ONLY')
    return dict(
        schema='rocell.move_request.v1', request_id=attempt_id,
        frame='CONTROLLER_JOINT', units='radians', joint='r',
        desired_target=transaction.get('desired_endpoint_rad', command['rad']),
        command=deepcopy(command), baseline=list(transaction['baseline']),
        baseline_finished_ns=transaction['baseline_finished_ns'],
        configuration=configuration,
        configuration_id=hashlib.sha256(canonical(configuration)).hexdigest(),
        motion_authorized=False, replay_allowed=False)
