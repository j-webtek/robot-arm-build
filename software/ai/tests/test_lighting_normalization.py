import hashlib,json,sys
from pathlib import Path
import numpy as np
from PIL import Image
AI=Path(__file__).resolve().parents[1];ROOT=AI.parents[1]
sys.path[:0]=[str(AI),str(AI.parent/'src')]
from vision.evaluate_lighting_normalization import normalize


def test_pixel_transform_bounds_and_no_mutation():
    image=Image.new('RGB',(128,96),(100,100,100));before=image.tobytes()
    result,gain=normalize(image)
    assert image.tobytes()==before
    assert result.getpixel((0,0))==(220,220,220)
    assert abs(gain-2.2)<1e-6
    result,gain=normalize(Image.new('RGB',(128,96),(0,0,0)))
    assert gain==2.5 and result.getpixel((0,0))==(0,0,0)
    result,gain=normalize(Image.new('RGB',(128,96),(255,255,255)))
    assert .5<=gain<=2.5 and result.size==(128,96)


def test_frozen_provenance_cases_and_acceptance():
    path=AI/'eval/lighting_normalization_v0.manifest.json'
    m=json.loads(path.read_text());r=json.loads((AI/'eval/lighting_normalization_v0_scorecard.json').read_text())
    assert hashlib.sha256(path.read_bytes()).hexdigest()==r['manifest_sha256']
    for f,h in m['file_sha256'].items():assert hashlib.sha256((ROOT/f).read_bytes()).hexdigest()==h
    assert len(r['cases'])==800
    for condition in m['conditions']:
        cases=[c for c in r['cases'] if c['condition']==condition]
        assert [c['seed'] for c in cases]==list(range(15000000,15000200))
        assert all(.5<=c['gain']<=2.5 for c in cases)
        for arm in ('control','normalized'):
            summary=r['summaries'][condition][arm]
            assert abs(np.mean([c['arms'][arm]['mean_mm'] for c in cases])-summary['mean_mm'])<1e-12
            assert sum(c['arms'][arm]['maximum_mm']>3 for c in cases)==summary['above_3mm_images']
            assert abs(np.percentile([c['arms'][arm]['yaw_degrees'] for c in cases],95)-summary['yaw_p95_degrees'])<1e-12
        a,b=r['summaries'][condition]['control'],r['summaries'][condition]['normalized']
        expected=dict(mean_error=b['mean_mm']<a['mean_mm'] if condition=='darkened_standard' else b['mean_mm']/a['mean_mm']<=1.05,
            tail=b['above_3mm_images']<a['above_3mm_images'] if condition=='darkened_standard' else b['above_3mm_images']<=a['above_3mm_images'],
            yaw=b['yaw_p95_degrees']/a['yaw_p95_degrees']<=1.10)
        assert r['checks'][condition]==expected
    assert r['development_rule_passed']==all(all(c.values()) for c in r['checks'].values())
    assert r['hardware_writes']==r['physical_movements']==0
    assert not r['qualification_installed']
