"""Native composition tests replace the coordinator; no native providers run."""
from rocell.providers.windows import micro_commissioning_native as module
import pytest


def test_missing_declaration_rejected_before_providers(tmp_path,monkeypatch):
    def forbidden(*a,**k):raise AssertionError('provider unexpectedly used')
    monkeypatch.setattr(module,'WizardDiagnosticExporter',forbidden)
    with pytest.raises(ValueError):module.run_native_micro_commissioning(root=tmp_path,export_root=tmp_path)


def test_native_composition_exports_under_assigned_folder(tmp_path,monkeypatch):
    calls=[]
    class Coordinator:
        def run(self,**kwargs):
            assert kwargs['lease_factory'] is module.arm_transport_lock
            assert kwargs['observe_hold'] is module.observe_bounded
            receipt=kwargs['save_outcome'](dict(status='NO_CORRECTION_NEEDED'))
            calls.append(receipt)
            return dict(status='NO_CORRECTION_NEEDED')
    monkeypatch.setattr(module,'MicroCommissioningCoordinator',Coordinator)
    result=module.run_native_micro_commissioning(root=tmp_path,export_root=tmp_path,
                                                exclusive_controller_declared=True)
    assert result['status']=='NO_CORRECTION_NEEDED' and len(calls)==1
    assert result['exports'][0]['valid']


def test_source_recheck_failure_prevents_composition(tmp_path):
    def changed():raise ValueError('source changed')
    with pytest.raises(ValueError,match='source changed'):
        module.run_native_micro_commissioning(root=tmp_path,export_root=tmp_path,
            exclusive_controller_declared=True,check_current=changed)
