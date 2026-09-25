"""Export the frozen r49 separated-probe mapping plan; offline only."""
from pathlib import Path

from rocell.application.first_motion_contract import canonical
from rocell.application.separated_pair_mapping_batch import plan_separated_mapping_batch
from rocell.application.wizard_diagnostic_export import WizardDiagnosticExporter,verify_export


def main():
    root=Path(__file__).resolve().parents[1]
    exporter=WizardDiagnosticExporter(root/'runs/wizard-exports');exporter.prepare(create=True)
    saved=exporter.export({'mode':'separated-pair-mapping-batch-plan'},[],attachments={
        'separated-pair-mapping-batch-plan.json':canonical(plan_separated_mapping_batch())})
    if not verify_export(Path(saved['path']))['valid']:raise ValueError('Plan export invalid')
    print(saved['path'])


if __name__=='__main__':main()
