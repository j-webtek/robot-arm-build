"""Export the reviewed r54 re-anchor endpoint as REFERENCE_A; no hardware I/O."""
import json
from pathlib import Path

from rocell.application.fixed_pair_reanchor import plan_fixed_pair_reanchor
from rocell.application.product_ghost_export_review import _read
from rocell.application.standard_start_reference import freeze_standard_start_reference


REANCHOR = 'wizard-20260921T222923014318Z-d559019a180d41eaa9c43c62c39e6c48'
PLAN = 'wizard-20260921T221915958401Z-02c0a7ba6b3f42e980a67f89b7ff80a4'
BOOT = '7e99400240967f278bc05886d7770abd'


def main():
    root = Path(__file__).resolve().parents[1] / 'runs/wizard-exports'
    plan, _ = _read(root, PLAN, 'attachment-fixed-pair-reanchor-plan.json')
    if plan != plan_fixed_pair_reanchor(root, plan['source_export_id']):
        raise ValueError('Frozen r54 re-anchor plan changed')
    path, reference = freeze_standard_start_reference(root, REANCHOR, boot=BOOT, plan=plan)
    print(json.dumps(dict(export_path=path, joints=reference['joints'],
                          physical_park_verified=False, hardware_access=False)))


if __name__ == '__main__':
    main()
