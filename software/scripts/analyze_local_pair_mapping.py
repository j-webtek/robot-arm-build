"""Combine verified r48/r49 mapping exports into one offline analysis."""
import json
from pathlib import Path

from rocell.application.first_motion_contract import canonical
from rocell.application.local_pair_mapping_analysis import analyze_mapping_rows
from rocell.application.product_ghost_export_review import _read
from rocell.application.wizard_diagnostic_export import WizardDiagnosticExporter,verify_export


R48="wizard-20260920T214732246917Z-16d2099d2e1747f5bc0d6082c99501bf"
R49="wizard-20260920T224608597099Z-151dafd0c1d547a9bc323d28db5cc550"


def main():
    root=Path(__file__).resolve().parents[1];exports=root/'runs/wizard-exports'
    r48,_=_read(exports,R48,'attachment-local-pair-mapping-result.json')
    r49,_=_read(exports,R49,'attachment-separated-pair-mapping-result.json')
    if r48.get('schema')!='rocell.local_pair_mapping_result.v1':
        raise ValueError('Unexpected r48 mapping schema')
    if r49.get('schema')!='rocell.separated_pair_mapping_result.v1':
        raise ValueError('Unexpected r49 mapping schema')
    analysis=analyze_mapping_rows([{"label":"r48-partial","rows":r48["rows"]},
                                   {"label":"r49-complete","rows":r49["rows"]}])
    analysis['source_exports']=[R48,R49]
    exporter=WizardDiagnosticExporter(exports);exporter.prepare(create=True)
    saved=exporter.export({'mode':'local-pair-mapping-analysis'},[],attachments={
        'local-pair-mapping-analysis.json':canonical(analysis)})
    if not verify_export(Path(saved['path']))['valid']:
        raise ValueError('Mapping analysis export invalid')
    print(json.dumps({'export_path':saved['path'],'rows':analysis['rows'],
                      'observed_primary_range':analysis['observed_primary_range'],
                      'model_fitted':False,'compensation_promoted':False}))


if __name__=='__main__':main()
