"""Join retained onboarding facts without upgrading their evidence strength.

USB metadata identifies the interface. Model/history statements remain operator
reports; neither these records nor vendor documentation identify installed code.
No device access, key creation, motion or automatic approval occurs here.
"""
from dataclasses import asdict
import hashlib
import re

from .first_motion_contract import canonical
from .wizard_diagnostic_coordinator import decode_diagnostic_json
from . import wizard_native_arm_metadata as metadata
from .physical_connection_contracts import EvidenceOrigin, RoArmUsbSerialIdentity, UsbDriverIdentity
from rocell.providers.windows.arm_feedback_worker import ReviewedControllerBinding
from rocell.providers.windows.nonpurging_serial_api import DcbSettings, CommTimeouts


def reviewed_vendor_protocol_original():
    """Fixed engineering review of vendor semantics, not installed binary proof."""
    return canonical(dict(schema='rocell.observational_vendor_protocol_review.v1', reviewed='2026-09-13',
        sources=['https://www.waveshare.com/wiki/RoArm-M3',
                 'https://www.waveshare.com/wiki/RoArm-M3-S_Robotic_Arm_Control'],
        command_type=101, joint=4, target_units='radians', target_kind='absolute_joint_angle',
        speed_units='servo_steps_per_second', acceleration_units='100_servo_steps_per_second_squared',
        tested_policy=dict(relative_degrees=1, spd=20, acc=1, automatic_return=False, retry=False),
        installed_binary_verified=False, physical_motion_qualified=False,
        basis='VENDOR_DOCUMENTATION_REVIEW_NOT_DEVICE_OBSERVATION'))


def export_source_originals(*, root, receipts, session_id, source_sha256):
    """Export bounded exact originals; reject missing/changed data, never truncate.

    Receipt selection is host-owned. Fixed filenames and content hashes prevent
    a source label or browser value from selecting another filesystem location.
    """
    import base64
    from .physical_onboarding_durability import contained_path, read_bounded_regular_file
    if type(receipts) is not tuple or not 0 < len(receipts) <= 8:
        raise ValueError('One to eight host-retained source receipts required')
    originals, associations, seen = {}, [], set()
    retained_bytes = 0
    for receipt in receipts:
        source_id = receipt['source_id']
        if (type(source_id) is not str or not re.fullmatch(r'observational-source-[a-f0-9]{32}', source_id)
                or source_id in seen or receipt['session_id'] != session_id
                or receipt['source_sha256'] != source_sha256
                or set(receipt['original_sha256']) != {'controller', 'protocol'}):
            raise ValueError('Source receipt identity/context changed')
        seen.add(source_id)
        files = [(kind, source_id+'-'+kind+'.json', digest)
            for kind,digest in receipt['original_sha256'].items()]
        onboarding = receipt.get('onboarding')
        if onboarding is not None:
            operation = onboarding['operation_id']
            if (type(operation) is not str or not re.fullmatch(r'operation-[a-f0-9]{32}', operation)
                    or set(onboarding['original_sha256']) != {'native_identity', 'generic_review',
                        'received_unit', 'protocol', 'serial_profile', 'boot_policy'}):
                raise ValueError('Onboarding source association changed')
            files.extend(('onboarding_'+kind, operation+'-observational-onboarding-'+kind+'.json', digest)
                for kind,digest in onboarding['original_sha256'].items())
        association = dict(source_id=source_id, originals={})
        for kind, filename, digest in files:
            raw = read_bounded_regular_file(contained_path(root, filename,
                label='observational source original'), maximum_bytes=256*1024)
            if hashlib.sha256(raw).hexdigest() != digest:
                raise ValueError('Observational source original changed')
            if digest not in originals:
                retained_bytes += len(raw)
                if retained_bytes > 600*1024:
                    raise ValueError('Source export byte budget exceeded; nothing truncated')
                originals[digest] = dict(bytes=len(raw), base64_chunks=[
                    base64.b64encode(raw[i:i+32768]).decode('ascii') for i in range(0, len(raw), 32768)])
            association['originals'][kind] = digest
        associations.append(association)
    result = canonical(dict(schema='rocell.observational_source_export.v1',
        session_id=session_id, source_sha256=source_sha256, associations=associations,
        originals=originals, installed_binary_verified=False, motion_authorized=False))
    if len(result) > 900*1024:
        raise ValueError('Encoded source export exceeds budget')
    return result


def sources_from_onboarding(*, native_original, generic_review, received_unit_original,
        protocol_original, session_id, source_sha256):
    """Inputs must be host-selected originals, never arbitrary browser JSON.

    The protocol original is an already reviewed host input; this function
    verifies its association/structure, not its engineering correctness.
    """
    def document(raw, maximum):
        if type(raw) is not bytes:
            raise ValueError('Immutable original bytes required')
        value = decode_diagnostic_json(raw, maximum=maximum)
        if type(value) is not dict or not value or canonical(value) != raw:
            raise ValueError('Canonical structured original required')
        return value

    native = document(native_original, metadata.MAX_REPORT_BYTES)
    rebuilt = metadata.correlate_native_arm_metadata(native['snapshot'], generic_review,
        mode='physical', session_id=session_id, source_sha256=source_sha256,
        operation_id=native['binding']['operation_id'])
    if rebuilt != native or rebuilt['status'] != 'METADATA_CORRELATED':
        raise ValueError('Onboarding metadata does not correlate with the retained selection')
    snapshot = metadata.decode_controller_snapshot(native['snapshot'], 'physical')
    if snapshot.origin is not EvidenceOrigin.PHYSICAL_OBSERVATION:
        raise ValueError('Physical metadata provenance required')
    candidates = [item for item in snapshot.serial_inventory.candidates
        if item.to_dict() == native['reviewed_generic_candidate']]
    if len(candidates) != 1:
        raise ValueError('Unique retained generic candidate required')
    candidate = candidates[0]
    matches = [row for row in snapshot.native_observations if
        (row.vid, row.pid, row.port_name) == (candidate.vid, candidate.pid, candidate.ephemeral_locator)]
    if len(matches) != 1:
        raise ValueError('Unique native USB/COM mapping required')
    row = matches[0]
    unit = document(received_unit_original, 8192)
    fields = {'schema', 'session_id', 'source_sha256', 'native_report_sha256', 'operator_id',
        'model', 'firmware_unchanged_since_delivery', 'basis', 'installed_binary_verified'}
    if (set(unit) != fields or unit['schema'] != 'rocell.observational_received_unit.v1'
            or unit['session_id'] != session_id or unit['source_sha256'] != source_sha256
            or unit['native_report_sha256'] != hashlib.sha256(native_original).hexdigest()
            or type(unit['operator_id']) is not str
            or not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_.-]{0,63}', unit['operator_id'])
            or unit['model'] != 'RoArm-M3-Pro' or unit['firmware_unchanged_since_delivery'] is not True
            or unit['basis'] != 'OPERATOR_REPORTED' or unit['installed_binary_verified'] is not False):
        raise ValueError('Explicit associated model/history report required; installed binary remains unknown')
    document(protocol_original, 128*1024)
    identity = RoArmUsbSerialIdentity(row.vid, row.pid, candidate.unit_serial,
        row.persistent_instance_id, row.persistent_port_path, row.port_name,
        UsbDriverIdentity(row.driver_provider, row.driver_service, row.driver_version, row.driver_inf))
    serial = canonical(dict(schema='rocell.observational_serial_profile.v1',
        dcb=asdict(DcbSettings()), timeouts=asdict(CommTimeouts())))
    boot = canonical(dict(schema='rocell.observational_boot_policy.v1',
        serial_open_may_reset_controller=True, startup_motion_possible=True,
        no_automatic_home=True, physical_stop_verified=False))
    originals = dict(native_identity=native_original, generic_review=canonical(generic_review), received_unit=received_unit_original,
        protocol=protocol_original, serial_profile=serial, boot_policy=boot)
    hashes = {name:hashlib.sha256(raw).hexdigest() for name,raw in originals.items()}
    binding = ReviewedControllerBinding(identity, hashes['native_identity'], hashes['received_unit'],
        hashes['received_unit'], hashes['boot_policy'], hashes['serial_profile'], EvidenceOrigin.PHYSICAL_OBSERVATION)
    return binding, originals, dict(status='ONBOARDING_SOURCES_ASSOCIATED',
        original_sha256=hashes, model_basis='OPERATOR_REPORTED', firmware_basis='OPERATOR_REPORTED_HISTORY',
        installed_binary_verified=False, motion_authorized=False, physical_accuracy_verified=False)
