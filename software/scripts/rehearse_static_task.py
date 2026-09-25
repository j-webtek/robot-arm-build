"""Run the static task route offline and export its diagnostic evidence."""
import argparse
import json
from pathlib import Path

from rocell.application.static_simulation_context import load_static_simulation_context
from rocell.application.static_task_rehearsal import run_static_task_rehearsal
from rocell.application.wizard_diagnostic_export import WizardDiagnosticExporter


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--device', choices=('keyboard', 'phone'), required=True)
    parser.add_argument('--text', required=True)
    parser.add_argument('--workspace', type=Path, default=Path(__file__).resolve().parents[2])
    parser.add_argument('--export-dir', type=Path)
    parser.add_argument('--dense', action='store_true', help='Check sequential intermediate poses at <=15 mm spacing')
    parser.add_argument('--keyboard-translation-mm',nargs=2,type=float,metavar=('DX','DY'),
                        help='Simulation-only keyboard translation, each axis within +/-50 mm; dimensions unchanged')
    parser.add_argument('--tool-length-mm', type=float, choices=(80.,100.,120.),
                        help='Nominal tool-offset hypothesis only; not a fabrication dimension or calibration')
    parser.add_argument('--park-xy-mm', nargs=2, type=float, metavar=('X', 'Y'),
                        help='Simulation-only board-frame park overlay; does not change frozen geometry')
    args = parser.parse_args()
    root = args.workspace.resolve(strict=True)
    report = run_static_task_rehearsal(load_static_simulation_context(root),
                                     device=args.device, text=args.text,
                                     park_xy_board_mm=None if args.park_xy_mm is None else tuple(args.park_xy_mm),
                                     dense=args.dense, tool_length_mm=args.tool_length_mm,
                                     keyboard_translation_mm=args.keyboard_translation_mm)
    exporter = WizardDiagnosticExporter(
        (args.export_dir or root/'software/runs/wizard-exports').resolve())
    exporter.prepare(create=True)
    receipt = exporter.export(
        dict(mode='simulation', status=report['status'], architecture=report['architecture']),
        [], attachments={'static-task.json': json.dumps(report, allow_nan=False).encode()})
    print(json.dumps(dict(status=report['status'], ik_converged=report['ik']['converged_count'],
                         ik_samples=report['ik']['sampled_tip_point_count'],
                         dense_waypoints=None if report['dense_route'] is None else
                         (report['dense_route'].get('round') or {}).get('waypoint_count'),
                         dense_evaluated=None if report['dense_route'] is None else
                         (report['dense_route'].get('round') or {}).get('evaluated_waypoint_count'),
                         export=receipt)))
    return 0 if report['status'] in ('SAMPLED_CHECKS_PASS_NOT_EXECUTABLE', 'DENSE_SAMPLES_PASS_NOT_EXECUTABLE') else 1


if __name__ == '__main__':
    raise SystemExit(main())
