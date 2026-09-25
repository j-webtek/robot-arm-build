"""Read only the fixed controller home page; never execute its JavaScript."""
import hashlib
import http.client
import json
from pathlib import Path
from rocell.providers.windows.arm_wifi_feedback import neighbor_mac, MAC
from rocell.providers.windows.arm_transport_lock import arm_transport_lock
from rocell.application.wizard_diagnostic_export import WizardDiagnosticExporter, verify_export


def main():
    with arm_transport_lock():
        if neighbor_mac()!=MAC: raise ValueError('Controller identity mismatch')
        connection=http.client.HTTPConnection('192.168.0.225',timeout=2)
        try:
            connection.request('GET','/')
            response=connection.getresponse()
            raw=response.read(524289)
            if response.status!=200 or len(raw)>524288: raise ValueError('Invalid bounded page response')
        finally:
            connection.close()
        if neighbor_mac()!=MAC: raise ValueError('Controller identity changed')
    page=raw.decode('utf-8',errors='replace')
    # Keep only static command-related lines, not network credential fields.
    fragments=[dict(line=i+1,text=line[:1200]) for i,line in enumerate(page.splitlines())
        if any(token in line for token in ('CMD_SINGLE_JOINT_CTRL','/js?','json=','singleJoint'))
        and not any(token in line.lower() for token in ('password','ssid'))][:30]
    report=dict(schema='rocell.interface_inspection.v1',http_status=200,method='GET',path='/',
        page_bytes=len(raw),page_sha256=hashlib.sha256(raw).hexdigest(),
        command_fragments=fragments,motion_commands=0,javascript_executed=False,
        installed_firmware_identified=False)
    root=Path(__file__).resolve().parents[2]
    exporter=WizardDiagnosticExporter((root/'software/runs/wizard-exports').resolve())
    exporter.prepare(create=True)
    receipt=exporter.export(dict(mode='read-only-interface-inspection'),[],attachments={
        'interface-inspection.json':json.dumps(report).encode()})
    if not verify_export(Path(receipt['path']).resolve())['valid']: raise ValueError('Export verification failed')
    print(json.dumps(dict(report=report,export=receipt['path'])))


if __name__=='__main__': main()
