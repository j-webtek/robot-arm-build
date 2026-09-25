"""Compare an exported feedback snapshot to pinned model FK, without hardware."""
import argparse
import json
from pathlib import Path
from rocell.application.controller_model_baseline import compare_controller_model
from rocell.application.controller_route_preview import preview_vertical_pair
from rocell.application.static_simulation_context import load_static_simulation_context
from rocell.application._pinned_model import load_pinned_urdf
from rocell.application.wizard_diagnostic_export import WizardDiagnosticExporter, verify_export


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--input', type=Path, required=True)
    args = parser.parse_args()
    folder = args.input.resolve(strict=True)
    if not verify_export(folder)['valid']:
        raise ValueError('Invalid source export')
    reports = []
    for file in folder.glob('attachment-result-*.json'):
        result = json.loads(file.read_text())
        if result.get('action_id') == 'read_arm_wifi_feedback':
            reports.append(result['steps'][0]['report'])
    if len(reports) != 1:
        raise ValueError('Select an export with exactly one feedback request')
    root = Path(__file__).resolve().parents[2]
    context = load_static_simulation_context(root)
    model = load_pinned_urdf(context.scenario.model_path, context.scenario.model_sha256)
    report = compare_controller_model(reports[0], model.model)
    report['noncontact_route_preview'] = preview_vertical_pair(reports[0])
    report.update(input_export=str(folder), input_response_sha256=reports[0]['response_sha256'],
                  model_sha256=model.sha256)
    exporter = WizardDiagnosticExporter((root/'software/runs/wizard-exports').resolve())
    exporter.prepare(create=True)
    receipt = exporter.export(dict(mode='offline-analysis'), [],
        attachments={'controller-model.json':json.dumps(report, allow_nan=False).encode()})
    print(json.dumps(dict(report=report, export=receipt['path'])))


if __name__ == '__main__':
    main()
