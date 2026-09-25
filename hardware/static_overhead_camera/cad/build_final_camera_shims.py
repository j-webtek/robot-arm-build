"""Add user-selected final shims to a welded copy of the cage/keeper plate."""
from pathlib import Path
import copy
import hashlib
import json
import os
import zipfile
import xml.etree.ElementTree as ET
import numpy as np
import trimesh
import cadquery as cq
from cadquery import exporters
import generate_printable_frame as g
from repair_00g_c1_mesh import inspect, NS

BASE = Path(__file__).resolve().parent.parent
SOURCE = BASE / 'cad/output/plates_3mf/08D-C1_ABS_camera_cage_and_keeper.3mf'
OUT = BASE / 'cad/output/revisions/08D-C1_final_shims_v1'
NAME = '08D-C1_ABS_camera_cage_keeper_SHIMS_1p0_1p1_v1'


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    cfg = json.loads((BASE / 'config/printable_frame_design.json').read_text())['camera']
    with zipfile.ZipFile(SOURCE) as archive:
        files = {n: archive.read(n) for n in archive.namelist()}
    root = ET.fromstring(files['3D/3dmodel.model'])
    source_build = ET.tostring(root.find(NS + 'build'))
    records = inspect(root, True)
    assert ET.tostring(root.find(NS + 'build')) == source_build
    resources, build = root.find(NS + 'resources'), root.find(NS + 'build')
    next_id = max(int(o.get('id')) for o in resources) + 1
    extra_objects = []
    meshes = []
    for thickness in cfg['final_shim_options_mm']:
        name = 'camera_final_shim_' + str(thickness).replace('.', 'p')
        # Preserve the original useful flat strip: 38 x 7 mm. The bold label is
        # on a separate tab joined by a thin neck, never on the contact face.
        shape = g.rounded_plate(38, 7, thickness, 0.7)
        shape = shape.union(g.box_ll(1.0, 1.2, thickness, 38, 2.9))
        shape = shape.union(g.rounded_plate(19, 10, 1.2, 1, 39, -1.5))
        shape = g.bold_plate_label(shape, f'{thickness:.1f}', 48.5, 3.5, 1.2, size=6).clean()
        assert shape.val().isValid() and len(shape.solids().vals()) == 1
        exporters.export(shape, str(OUT / (name + '.step')))
        exporters.export(shape, str(OUT / (name + '.stl')), tolerance=0.04, angularTolerance=0.06)
        raw = trimesh.load_mesh(OUT / (name + '.stl'), process=False)
        vertices, inverse = np.unique(raw.vertices, axis=0, return_inverse=True)
        mesh = trimesh.Trimesh(vertices, inverse[raw.faces], process=False)
        assert mesh.is_volume and len(mesh.split()) == 1
        flat = mesh.section(plane_origin=[0, 0, thickness / 2], plane_normal=[0, 0, 1])
        assert flat is not None
        # Verify designed useful strip thickness away from the detachable label.
        useful = g.box_ll(36, 5, thickness + 4, 1, 1, -2)
        intersection = shape.val().intersect(useful.val())
        assert abs(intersection.Volume() - 36 * 5 * thickness) < 1e-5
        for index in range(cfg['final_shim_quantity_each']):
            moved = mesh.copy()
            moved.apply_translation((10 + 80 * index, 130 + 30 * len(extra_objects), 0))
            # Each size occupies a row, with duplicates spaced along X.
            assert np.all(moved.bounds[0] >= [6, 6, -1e-6])
            assert np.all(moved.bounds[1] <= [289, 289, 275])
            object_id = str(next_id)
            next_id += 1
            obj = ET.SubElement(resources, NS + 'object', id=object_id, type='model', name=f'{name}__{index+1:02}')
            xml_mesh = ET.SubElement(obj, NS + 'mesh')
            xml_vertices = ET.SubElement(xml_mesh, NS + 'vertices')
            for v in moved.vertices:
                ET.SubElement(xml_vertices, NS + 'vertex', **dict(zip(('x','y','z'), map(str, v))))
            xml_faces = ET.SubElement(xml_mesh, NS + 'triangles')
            for f in moved.faces:
                ET.SubElement(xml_faces, NS + 'triangle', **dict(zip(('v1','v2','v3'), map(str, f))))
            ET.SubElement(build, NS + 'item', objectid=object_id)
            meshes.append(moved)
        extra_objects.append(dict(part=name, stl=name+'.stl', quantity=cfg['final_shim_quantity_each'], nominal_thickness_mm=thickness))
    data = ET.tostring(root, encoding='utf-8', xml_declaration=True)
    assert b'<model ' in data and b'<mesh>' in data and b'<ns0:' not in data
    files['3D/3dmodel.model'] = data
    target = OUT / (NAME + '.3mf')
    with zipfile.ZipFile(target, 'w', zipfile.ZIP_DEFLATED) as archive:
        for name, content in files.items():
            archive.writestr(name, content)
    with zipfile.ZipFile(target) as archive:
        final_records = inspect(ET.fromstring(archive.read('3D/3dmodel.model')), False)
    assert len(final_records) == 6
    scene = trimesh.load(target, process=False)
    assert len(scene.geometry) == 6
    bounds = [m.bounds for m in scene.geometry.values()]
    for i, a in enumerate(bounds):
        for b in bounds[i+1:]:
            separation = np.maximum(a[0,:2]-b[1,:2], b[0,:2]-a[1,:2])
            assert max(separation) >= 12 - 1e-4, (a, b)
    sidepath = BASE / 'print_jobs/08D-C1_ABS_camera_cage_and_keeper.print.json'
    info = json.loads(sidepath.read_text())
    for obj in info['objects']:
        obj['stl'] = os.path.relpath((sidepath.parent / obj['stl']).resolve(), OUT).replace('\\','/')
    info['objects'].extend(extra_objects)
    info['expected_object_count'] = 6
    info['geometry_3mf'] = target.name
    info['geometry_sha256'] = hashlib.sha256(target.read_bytes()).hexdigest()
    info['sidecar'] = NAME + '.print.json'
    info['print']['process_file'] = os.path.relpath((sidepath.parent / info['print']['process_file']).resolve(), OUT).replace('\\','/')
    info['native_save_as_pattern'] = '08D-C1_final_shims_QIDI_native_vNN.3mf'
    (OUT / info['sidecar']).write_text(json.dumps(info, indent=2)+'\n')
    report = dict(topology='PASS', objects=final_records, cage_keeper_geometry_and_placement='UNCHANGED',
                  nominal_shim_sizes_mm=cfg['final_shim_options_mm'], useful_strip_xy_mm=[38,7],
                  native_slicer_verification='PENDING', physical_final_fit='PENDING_ASSEMBLY',
                  output_sha256=info['geometry_sha256'], original_cage_keeper_plate_preserved=True)
    (OUT / (NAME+'.validation.json')).write_text(json.dumps(report, indent=2)+'\n')
    print(str(target))
    print('PASS: six closed meshes, unchanged cage/keeper, four labelled shims, >=12 mm XY separation.')


if __name__ == '__main__':
    main()
