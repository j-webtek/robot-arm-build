"""Build a standalone corrected 00G-S1 package without overwriting original artifacts."""
from pathlib import Path
import os
import sys
import json
import hashlib
import zipfile
import xml.etree.ElementTree as ET
import numpy as np
import trimesh
import cadquery as cq
from cadquery import exporters
import generate_printable_frame as g

ROOT = Path(__file__).resolve().parents[3]
OUT = g.OUTPUT_DIR / 'revisions' / '00G-S1_readable_v2'
OUT.mkdir(parents=True, exist_ok=True)
NAME = '00G-S1_ABS_board_splice_fit_tests_REPAIRED_LABELS_v2'
NS = {'m': 'http://schemas.microsoft.com/3dmanufacturing/core/2015/02'}


def exact_weld(mesh):
    vertices, inverse = np.unique(mesh.vertices, axis=0, return_inverse=True)
    result = trimesh.Trimesh(vertices, inverse[mesh.faces], process=False)
    assert np.array_equal(mesh.vertices[mesh.faces], result.vertices[result.faces])
    return result


def volume(shape):
    return sum(s.Volume() for s in shape.solids().vals())


def unchanged_in(old, new, region):
    # Use explicit Shapes: Workplane can fall back to parent-stack solids
    # after an empty boolean and accidentally report the original body.
    removed_shape = old.val().cut(new.val())
    added_shape = new.val().cut(old.val())
    removed = removed_shape.intersect(region.val()).Volume() if removed_shape.Solids() else 0.0
    added = added_shape.intersect(region.val()).Volume() if added_shape.Solids() else 0.0
    assert removed < 1e-5 and added < 1e-5, (removed, added)
    return {'removed_mm3': removed, 'added_mm3': added, 'status': 'PASS'}


def main():
    print('Building four revised solids...', flush=True)
    parts = {
        'u_truss_splice': g.u_truss_splice(readable_labels=True),
        'u_splice_fit_coupon': g.u_splice_fit_coupon(readable_labels=True),
        'board_saddle_fit_coupon': g.board_saddle_fit_coupon(readable_labels=True),
        'm6_nut_retainer': g.m6_nut_retainer(),
    }
    print('Checking unchanged functional interfaces...', flush=True)
    old_board = cq.importers.importStep(str(g.STEP_DIR / 'board_saddle_fit_coupon.step'))
    old_collar = cq.importers.importStep(str(g.STEP_DIR / 'u_truss_splice.step'))
    old_retainer = cq.importers.importStep(str(g.STEP_DIR / 'm6_nut_retainer.step'))
    bare_truss = g.truss_segment(86.0, 'TEST', markings=False)
    checks = {
        'board_jaws_and_nut_channel': unchanged_in(old_board, parts['board_saddle_fit_coupon'],
            g.box_ll(104, 32.65, 12).union(g.box_ll(30,45,18.65,74,0,0))),
        'collar_load_bearing_body_and_bores': unchanged_in(old_collar, parts['u_truss_splice'],g.box_ll(104,62.8,74)),
        'truss_test_envelope': unchanged_in(bare_truss, parts['u_splice_fit_coupon'],g.box_ll(86,50,64)),
        'retainer_unchanged': unchanged_in(old_retainer, parts['m6_nut_retainer'],g.box_ll(40,50,30,-20,-10,-5)),
    }
    inserted = parts['u_splice_fit_coupon'].translate((52,6.4,4))
    overlap = volume(inserted.intersect(parts['u_truss_splice']))
    assert overlap < 1e-5, overlap
    checks['coupon_inserted_to_aligned_bolt_station'] = {'interference_mm3': overlap, 'status':'PASS'}
    # Keep the existing origins; label additions extend into unused plate area.
    shifts = {'u_truss_splice': (10,10,0), 'u_splice_fit_coupon': (134,10,0),
              'board_saddle_fit_coupon': (10,105.8,0), 'm6_nut_retainer': (159.8,112.4,-2)}
    scene = trimesh.Scene()
    records = []
    for name, shape in parts.items():
        assert shape.val().isValid() and len(shape.solids().vals()) == 1, name
        exporters.export(shape, str(OUT / (name+'.step')))
        exporters.export(shape, str(OUT / (name+'.stl')), tolerance=0.04, angularTolerance=0.06)
        raw = trimesh.load_mesh(OUT / (name+'.stl'), process=False)
        mesh = exact_weld(raw)
        assert mesh.is_volume and len(mesh.split(only_watertight=False)) == 1, name
        if name == 'm6_nut_retainer':
            mesh.apply_transform(trimesh.transformations.rotation_matrix(np.pi/2,(0,0,1)))
        mesh.apply_translation(shifts[name])
        scene.add_geometry(mesh, geom_name=name+'__01', node_name='print_item__'+name+'__01')
        records.append({'part':name, 'triangle_count':len(mesh.faces), 'vertices':len(mesh.vertices),
            'volume_mm3':float(mesh.volume), 'bounds_mm':mesh.bounds.tolist(), 'translation_mm':shifts[name]})
    for i, a in enumerate(records):
        lo,hi = np.array(a['bounds_mm'])
        assert min(lo[:2]) >= 10-1e-6 and max(hi[:2]) <= 285+1e-6 and lo[2] >= -1e-6 and hi[2] <=275
        for b in records[i+1:]:
            blo,bhi=np.array(b['bounds_mm'])
            gaps=np.maximum(blo[:2]-hi[:2],lo[:2]-bhi[:2])
            assert np.max(gaps) >= 20-1e-4, (a['part'],b['part'],gaps)
    target=OUT/(NAME+'.3mf')
    target.write_bytes(scene.export(file_type='3mf'))
    with zipfile.ZipFile(target) as archive:
        model=ET.fromstring(archive.read('3D/3dmodel.model'))
    raw_checks=[]
    for obj in model.findall('./m:resources/m:object',NS):
        v=np.array([[float(e.get(k)) for k in ('x','y','z')] for e in obj.findall('m:mesh/m:vertices/m:vertex',NS)])
        f=np.array([[int(e.get(k)) for k in ('v1','v2','v3')] for e in obj.findall('m:mesh/m:triangles/m:triangle',NS)])
        mesh=trimesh.Trimesh(v,f,process=False)
        counts=np.bincount(mesh.edges_unique_inverse)
        assert np.all(counts==2) and mesh.is_volume and len(mesh.split())==1
        raw_checks.append({'object':obj.get('name'),'open_edges':int(np.sum(counts==1)),
            'nonmanifold_edges':int(np.sum(counts>2)), 'watertight':mesh.is_watertight,'consistent_winding':mesh.is_winding_consistent})
    assert len(raw_checks)==4 and len(model.findall('./m:build/m:item',NS))==4
    sha=hashlib.sha256(target.read_bytes()).hexdigest()
    report={'status':'PASS','scope':'raw packaged mesh topology, CAD functional interfaces, count, placement and brim envelope',
        'native_qidi_slice':'NOT_YET_VERIFIED','physical_fit_and_load':'NOT_TESTED',
        'file':target.name,'sha256':sha,'objects':records,'raw_3mf_checks':raw_checks,'functional_checks':checks,
        'labels':{'font':'Arial Black','font_size_mm':[7.5,8,9],'raised_height_mm':1.2,
                  'retainer':'unchanged and unlettered to preserve fit'},
        'original_file_preserved':True}
    (OUT/(NAME+'.validation.json')).write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8')
    side=json.loads((g.ROOT/'print_jobs/00G-S1_ABS_board_splice_fit_tests.print.json').read_text())
    side['geometry_3mf']=target.name
    side['geometry_sha256']=sha
    side['sidecar']=NAME+'.print.json'
    side['native_save_as_pattern']='00G-S1_REPAIRED_LABELS_v2_QIDI_native_vNN.3mf'
    side['revision']='connectivity-and-readable-labels-v2'
    side['print']['process_name']='RoCell 00G-S1 ABS Rapido Structural 0.20 v1'
    side['print']['process_file']='../../../../slicer_profiles/QIDI_PLUS4/abs_rapido_00G_S1_structural_v1.process.json'
    for item in side['objects']: item['stl']=item['part']+'.stl'
    (OUT/(NAME+'.print.json')).write_text(json.dumps(side,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(report,indent=2),flush=True)


if __name__=='__main__':
    main()
    sys.stdout.flush()
    if sys.platform=='win32': os._exit(0)
