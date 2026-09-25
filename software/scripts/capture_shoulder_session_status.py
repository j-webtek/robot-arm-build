"""One retained-session status GET and durable export; no servo I/O or retry."""
import argparse
from pathlib import Path
from rocell.application.first_motion_contract import canonical
from rocell.application.shoulder_session_http import ShoulderSessionHTTP
from rocell.application.wizard_diagnostic_coordinator import decode_diagnostic_json
from rocell.application.wizard_diagnostic_export import WizardDiagnosticExporter,verify_export


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--expected-boot',required=True)
    args=parser.parse_args()
    exports=Path(__file__).resolve().parents[1]/'runs/wizard-exports'
    exporter=WizardDiagnosticExporter(exports);exporter.prepare(create=True)
    raw=ShoulderSessionHTTP('192.168.0.225')('GET','/rocell/shoulder-session/status',b'',3)
    doc=decode_diagnostic_json(raw,maximum=4095)
    saved=exporter.export({'mode':'retained-shoulder-status'},[],attachments={'shoulder-status.txt':raw})
    if not verify_export(Path(saved['path']))['valid']:raise ValueError('Invalid status export')
    if doc.get('boot_id')!=args.expected_boot:raise ValueError('Boot changed; captured response retained')
    print(canonical(dict(export_path=saved['path'],status=doc,servo_commands_sent=False)).decode())


if __name__=='__main__':main()
