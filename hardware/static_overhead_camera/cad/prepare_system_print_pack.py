"""Exact-coordinate topology repair and scoped remaining-system print package."""
from pathlib import Path
import hashlib
import json
import os
import shutil
import zipfile
import xml.etree.ElementTree as ET
import xml.parsers.expat
from collections import Counter
import numpy as np
import trimesh
from repair_00g_c1_mesh import NS, inspect

BASE = Path(__file__).resolve().parent.parent
OUT = BASE / 'cad/output/revisions/SYSTEM_PRINT_PACK_v1'


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def package_archive():
    revision_notes=OUT/'SADDLE_REVISION_NOTES'
    revision_notes.mkdir(exist_ok=True)
    saddle_source=BASE/'cad/output/revisions/SADDLES_GROUNDED_v2'
    for filename in ('PRINT_THIS_REVISION.md','MANIFEST.json','saddle_side_comparison.png'):
        shutil.copy2(saddle_source/filename,revision_notes/filename)
    with zipfile.ZipFile(OUT.parent/'SYSTEM_PRINT_PACK_v1.zip','w',zipfile.ZIP_DEFLATED) as archive:
        for path in sorted(OUT.rglob('*')):
            if path.is_file():
                archive.write(path,path.relative_to(OUT.parent))


def main():
    OUT.mkdir(parents=True,exist_ok=True)
    (OUT/'profiles').mkdir(exist_ok=True)
    (OUT/'STL_fallback').mkdir(exist_ok=True)
    records=[]
    paths=sorted((BASE/'cad/output/plates_3mf').glob('08[ABC]-*.3mf'))
    paths.insert(0,BASE/'cad/output/plates_3mf/00G-P1_TPU_camera_portal_pads.3mf')
    for source in paths:
        original_side=BASE/'print_jobs'/(source.stem+'.print.json')
        side=json.loads(original_side.read_text())
        geometry_revision=None
        if side['subplate_id'] in ('08A-S1','08B-S1'):
            hand='left' if side['subplate_id']=='08A-S1' else 'right'
            source=BASE/'cad/output/revisions/SADDLES_GROUNDED_v2'/f"{side['subplate_id']}_ABS_{hand}_bench_saddle_GROUNDED_v2.3mf"
            assert source.exists(), 'Generate corrected saddle first; old floating-tip model is not printable as instructed.'
            geometry_revision='GROUNDED_v2: permanent rib feet and cleared upright pocket'
        hold=side['subplate_id']=='08C-C1'
        folder=OUT/('HOLD_camera_carriage' if hold else 'PRINT_TPU_board_pads' if side['profile']=='tpu_pads' else 'PRINT_ABS_frame')
        folder.mkdir(parents=True,exist_ok=True)
        name=source.stem if geometry_revision else source.stem.replace('TPU_camera_portal_pads','TPU_board_pads_ONLY')+'_WELDED_v1'
        target=folder/(name+'.3mf')
        with zipfile.ZipFile(source) as archive:
            files={n:archive.read(n) for n in archive.namelist()}
        root=ET.fromstring(files['3D/3dmodel.model'])
        excluded=[]
        if side['subplate_id']=='00G-P1':
            # This revision deliberately excludes the obsolete camera pad.
            resources=root.find(NS+'resources')
            remove={o.get('id') for o in resources if o.get('name','').startswith('camera_top_compression_pad')}
            assert len(remove)==1
            for o in list(resources):
                if o.get('id') in remove:
                    excluded.append(o.get('name')); resources.remove(o)
            build=root.find(NS+'build')
            for item in list(build):
                if item.get('objectid') in remove:
                    build.remove(item)
            side['objects']=[o for o in side['objects'] if o['part']!='camera_top_compression_pad']
            side['expected_object_count']=4
        original_build=ET.tostring(root.find(NS+'build'))
        mesh_records=inspect(root,True)
        assert ET.tostring(root.find(NS+'build'))==original_build
        data=ET.tostring(root,encoding='utf-8',xml_declaration=True)
        assert b'<model ' in data and b'<mesh>' in data and b'<ns0:' not in data
        files['3D/3dmodel.model']=data
        with zipfile.ZipFile(target,'w',zipfile.ZIP_DEFLATED) as archive:
            for entry,content in files.items():
                archive.writestr(entry,content)
        tags=Counter()
        with zipfile.ZipFile(target) as archive:
            disk_data=archive.read('3D/3dmodel.model')
            final_records=inspect(ET.fromstring(disk_data),False)
            parser=xml.parsers.expat.ParserCreate()
            parser.StartElementHandler=lambda tag,attrs:tags.update([tag])
            parser.Parse(disk_data,True)
        scene=trimesh.load(target,process=False)
        expected=side['expected_object_count']
        assert len(final_records)==tags['mesh']==tags['item']==len(scene.geometry)==expected
        bounds=[]
        for mesh in scene.dump():
            assert mesh.is_volume and mesh.is_watertight
            assert np.all(mesh.bounds[0]>=[-1e-5,-1e-5,-1e-5])
            assert np.all(mesh.bounds[1]<=[295.00001,295.00001,275.00001])
            bounds.append(mesh.bounds.tolist())
        for o in side['objects']:
            stl=source.with_suffix('.stl') if geometry_revision else (original_side.parent/o['stl']).resolve()
            assert stl.exists()
            copied_stl=OUT/'STL_fallback'/stl.name
            shutil.copy2(stl,copied_stl)
            o['stl']=os.path.relpath(copied_stl,folder).replace('\\','/')
        process=(original_side.parent/side['print']['process_file']).resolve()
        assert process.exists()
        settings=json.loads(process.read_text())
        settings['type']='process'
        settings['name']=settings['name']+' Print Pack v1'
        settings['print_settings_id']=settings['name']
        settings.pop('wall_sequence',None)
        settings['wall_infill_order']='inner wall/outer wall/infill'
        settings['internal_solid_infill_pattern']='rectilinear'
        packed_process=OUT/'profiles'/process.name
        packed_process.write_text(json.dumps(settings,indent=2)+'\n')
        side.update(geometry_3mf=target.name,geometry_sha256=sha(target),sidecar=name+'.print.json',
                    native_save_as_pattern=side['subplate_id']+'_WELDED_QIDI_native_vNN.3mf')
        side['print']['process_file']=os.path.relpath(packed_process,folder).replace('\\','/')
        side['print']['process_name']=settings['name']
        side['release_scope']='HOLD: camera back-exit USB clearance unresolved' if hold else 'Prepared for prototype slicing/printing; not physical load qualification'
        side['native_slicer_preview']='PENDING: verify object count, stored orientation and toolpaths in QIDI'
        (folder/(name+'.print.json')).write_text(json.dumps(side,indent=2)+'\n')
        report=dict(plate=side['subplate_id'],file=os.path.relpath(target,OUT).replace('\\','/'),
                    geometry_source=str(source),geometry_revision=geometry_revision,
                    source_sha256=sha(source),output_sha256=sha(target),status='HOLD_DESIGN' if hold else 'PASS_MESH',
                    expected_objects=expected,objects=final_records,placed_bounds_mm=bounds,
                    triangle_coordinates='EXACTLY_PRESERVED_FROM_NAMED_GEOMETRY_SOURCE',build_transforms='EXACTLY_PRESERVED',
                    excluded_objects=excluded,namespace='DEFAULT_UNPREFIXED_CORE',
                    native_slicer_preview='PENDING',physical_fit_and_strength='NOT_QUALIFIED')
        (folder/(name+'.validation.json')).write_text(json.dumps(report,indent=2)+'\n')
        records.append(report)
        print(f"{side['subplate_id']}: {report['status']} | {expected} closed objects",flush=True)
    assert len(records)==18
    assert sum(r['status']=='PASS_MESH' for r in records)==17
    manifest=dict(description='16 ABS frame plates plus four TPU board pads on one plate; one repaired carriage plate on HOLD',
                  original_files_preserved=True,plates=records)
    (OUT/'MANIFEST.json').write_text(json.dumps(manifest,indent=2)+'\n')
    # Package all relative dependencies. The README is maintained alongside the
    # generated reports and is included if present. No originals are overwritten.
    package_archive()
    print('PASS: 17 prepared plates, 1 held carriage, original geometry and files preserved.',flush=True)


if __name__=='__main__':
    main()
