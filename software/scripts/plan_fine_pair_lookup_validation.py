"""Export the fixed r50 fine-pair validation plan; offline only."""
from pathlib import Path

from rocell.application.fine_pair_lookup_validation import plan_fine_lookup_validation
from rocell.application.first_motion_contract import canonical
from rocell.application.wizard_diagnostic_export import WizardDiagnosticExporter,verify_export


def main():
    root=Path(__file__).resolve().parents[1]
    exporter=WizardDiagnosticExporter(root/'runs/wizard-exports');exporter.prepare(create=True)
    saved=exporter.export({'mode':'fine-pair-lookup-validation-plan'},[],attachments={
        'fine-pair-lookup-validation-plan.json':canonical(plan_fine_lookup_validation())})
    if not verify_export(Path(saved['path']))['valid']:
        raise ValueError('Fine lookup plan export invalid')
    print(saved['path'])


if __name__=='__main__':main()
