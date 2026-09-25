"""Inspect a pinned official archive as data; never execute or deploy firmware.

Downloads only the named public reference. Preserves hashes and a comparison to
the previously retained arm page in a verified diagnostic export. No arm access.
"""
import hashlib
import io
import json
from pathlib import Path
import urllib.request
import zipfile

from rocell.application.first_motion_contract import canonical
from rocell.application.wizard_diagnostic_export import WizardDiagnosticExporter,verify_export

URL='https://files.waveshare.com/wiki/RoArm-M3/RoArm-M3_example20260115.zip'
SHA256='d627e180c4814776ef0ccf78f237482d48dcd3745be1e37378c25fd9005fd6a9'
BASE='RoArm-M3_example20260115/RoArm-M3_example/'
RETAINED='wizard-20260917T184526089377Z-37a82dfd581a4032bd90927e00bec210'
PAGE_SHA='2f93fdc878a0ecc24d8e6e3a3c5803184165a6d2ec3cf265d86c41e2408e75e8'


def main():
    root=Path(__file__).resolve().parents[1]/'runs'/'wizard-exports'
    retained_dir=root/RETAINED
    if not verify_export(retained_dir)['valid']:
        raise ValueError('Original served-page export failed verification')
    observed=(retained_dir/'attachment-served-interface.txt').read_bytes()
    if hashlib.sha256(observed).hexdigest()!=PAGE_SHA:
        raise ValueError('Unexpected retained page identity')
    with urllib.request.urlopen(URL,timeout=20) as response:
        archive=response.read(16_000_001)
    if len(archive)>16_000_000 or hashlib.sha256(archive).hexdigest()!=SHA256:
        raise ValueError('Reference download differs from reviewed archive')
    files={}
    with zipfile.ZipFile(io.BytesIO(archive)) as zipped:
        for name in ('http_server.h','uart_ctrl.h','RoArm-M3_example.ino',
                     'RoArm-M3_module.h','RoArm-M3_config.h','m3_web_page.h'):
            info=zipped.getinfo(BASE+name)
            if info.file_size>1_000_000:raise ValueError('Reference member exceeds bound')
            files[name]=zipped.read(info)
    page=files['m3_web_page.h'].split(b'rawliteral(',1)[1].split(b')rawliteral',1)[0]
    page=page.replace(b'\r\n',b'\n')
    # This is a reviewed comparison, not normalization of arbitrary differences.
    # The single difference is a numeric default in the page's example command.
    known_difference=(page[49385:49386]==b'6'
        and page[:49385]+b'11'+page[49386:]==observed)
    if not known_difference:raise ValueError('Served-page comparison no longer matches review')
    report=dict(schema='rocell.legacy_firmware_source_review.v1',
        source_url=URL,source_sha256=SHA256,archive_bytes=len(archive),
        discovery_revision=110226,
        member_sha256={name:hashlib.sha256(raw).hexdigest() for name,raw in files.items()},
        retained_page_export=RETAINED,retained_page_sha256=PAGE_SHA,
        reference_page_lf_sha256=hashlib.sha256(page).hexdigest(),
        reference_page_lf_bytes=len(page),observed_page_bytes=len(observed),
        exact_page_match=False,all_other_page_bytes_match=True,
        difference=dict(reference_offset=49385,reference_bytes_hex='36',observed_bytes_hex='3131'),
        reference_joint_servo_mapping={'1':[11],'2':[12,13],'3':[14],'4':[15],'5':[16],'6':[17]},
        findings=['DIRECT_HTTP_JSON_FEEDBACK','FAILED_FEEDBACK_RETAINS_POSITION',
            'PUBLIC_FEEDBACK_OMITS_ACQUISITION_VALIDITY','SINGLE_JOINT_WRITE_RETURN_IGNORED',
            'NO_GOAL_REGISTER_DIAGNOSTIC_ROUTE_IN_REVIEWED_HANDLER',
            'BOOT_PERFORMS_MOTION_AND_CONFIGURATION_WRITES'],
        installed_binary_verified=False,installed_library_verified=False,
        deployment_authorized=False,motion_commands=0)
    exporter=WizardDiagnosticExporter(root)
    exporter.prepare(create=True)
    receipt=exporter.export({'mode':'offline-reference-review'},[],
        attachments={'legacy-reference-review.json':canonical(report)})
    if not verify_export(Path(receipt['path']))['valid']:
        raise ValueError('Reference review export verification failed')
    print(json.dumps(dict(export=receipt['path'],verified=True,report=report)))


if __name__=='__main__':main()
