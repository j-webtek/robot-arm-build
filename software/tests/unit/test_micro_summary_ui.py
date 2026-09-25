"""Render saved summary through the real application JS with GET-only fixtures."""
import json
import runpy
from pathlib import Path
import pytest
from test_wizard_activity_ui import render, view, operation
from test_micro_result_summary import fixture
from rocell.application.micro_result_summary import summarize_micro_result
from rocell.application.wizard_diagnostic_export import WizardDiagnosticExporter


def test_summary_labels_values_and_collapsible_original():
    report=fixture(); report['summary']=summarize_micro_result(report)
    op=operation(action_id='run_micro_commissioning',result=dict(steps=[dict(report=report)]))
    page=render(view([op]),steps=[dict(load='op-0')],results={'op-0':op})
    text=json.dumps(page,ensure_ascii=False)
    for expected in ('0.95000°','1.25000°','1.23047°','-0.01953°','0.28047°',
                     '418.209','Inspect full commissioning report','reported minus desired'):
        assert expected in text


def test_historical_preview_requires_verified_export_and_preserves_original(tmp_path):
    preview=runpy.run_path(str(Path(__file__).resolve().parents[2]/'scripts/camera_ui_preview.py'))
    report=fixture(); report['schema']='rocell.micro_commissioning.v1'
    exporter=WizardDiagnosticExporter(tmp_path.resolve()); exporter.prepare(create=True)
    receipt=exporter.export({},[],attachments={'result-commissioning.json':json.dumps(report).encode()})
    folder=Path(receipt['path']); original=folder/'attachment-result-commissioning.json'
    before=original.read_bytes()
    snapshot,op=preview['saved_micro_preview'](folder)
    assert snapshot['actions']==[] and not snapshot['physical_authority']
    assert op['result']['steps'][0]['report']['summary']['legs'][0]['hold_samples']==119
    assert original.read_bytes()==before
    original.write_bytes(before+b' ')  # Intentional tamper in temporary test fixture.
    with pytest.raises(ValueError):preview['saved_micro_preview'](folder)
