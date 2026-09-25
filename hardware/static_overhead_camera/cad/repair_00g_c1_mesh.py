"""Repair only duplicate-vertex topology; preserve all triangle coordinates and placement."""
from pathlib import Path
import hashlib
import json
import os
import zipfile
import xml.etree.ElementTree as ET
import xml.parsers.expat
from collections import Counter
import numpy as np
import trimesh

BASE = Path(__file__).resolve().parent.parent
SOURCE = BASE / 'cad/output/plates_3mf/00G-C1_ABS_received_camera_fit_tests.3mf'
OUT = BASE / 'cad/output/revisions/00G-C1_welded_v2'
NAME = '00G-C1_ABS_received_camera_fit_tests_WELDED_v2'
NS = '{http://schemas.microsoft.com/3dmanufacturing/core/2015/02}'
# QIDI's importer expects unprefixed core element names. ElementTree otherwise
# emits ns0:model/ns0:mesh, which passed our XML checks but loaded as no geometry.
ET.register_namespace('', NS[1:-1])
ET.register_namespace('p', 'http://schemas.microsoft.com/3dmanufacturing/production/2015/06')


def inspect(root, repair):
    records = []
    for obj in root.iter(NS + 'object'):
        mesh = obj.find(NS + 'mesh')
        if mesh is None:
            continue
        vs, ts = mesh.find(NS + 'vertices'), mesh.find(NS + 'triangles')
        vertices = np.array([[float(v.attrib[k]) for k in ('x', 'y', 'z')] for v in vs])
        faces = np.array([[int(t.attrib[k]) for k in ('v1', 'v2', 'v3')] for t in ts])
        unique, first, inverse = np.unique(vertices, axis=0, return_index=True, return_inverse=True)
        welded_faces = inverse[faces]
        assert np.array_equal(vertices[faces], unique[welded_faces])
        checked = trimesh.Trimesh(unique, welded_faces, process=False)
        counts = np.bincount(checked.edges_unique_inverse)
        assert np.all(counts == 2) and checked.is_volume, obj.attrib
        assert len(checked.split(only_watertight=False)) == 1, obj.attrib
        if repair:
            old = list(vs)
            vs.clear()
            for index in first:
                vs.append(old[index])
            for t, f in zip(ts, welded_faces):
                for key, index in zip(('v1', 'v2', 'v3'), f):
                    t.set(key, str(index))
        else:
            # Verify serialized topology directly, with no implicit vertex merging.
            raw = trimesh.Trimesh(vertices, faces, process=False)
            assert raw.is_watertight and raw.is_winding_consistent and raw.is_volume
        records.append(dict(name=obj.get('name', obj.get('id')), original_vertices=len(vertices),
                            welded_vertices=len(unique), triangles=len(faces),
                            open_edges=0, nonmanifold_edges=0, geometry_unchanged=True))
    return records


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    target = OUT / (NAME + '.3mf')
    reports = []
    with zipfile.ZipFile(SOURCE) as src, zipfile.ZipFile(target, 'w', zipfile.ZIP_DEFLATED) as dst:
        for entry in src.infolist():
            data = src.read(entry.filename)
            if entry.filename.lower().endswith('.model'):
                root = ET.fromstring(data)
                reports.extend(inspect(root, True))
                data = ET.tostring(root, encoding='utf-8', xml_declaration=True)
                assert b'<model ' in data and b'<mesh>' in data
                assert b'<ns0:' not in data
            dst.writestr(entry, data)
    literal_tags = Counter()
    with zipfile.ZipFile(target) as archive:
        for name in archive.namelist():
            if name.lower().endswith('.model'):
                data = archive.read(name)
                inspect(ET.fromstring(data), False)
                parser = xml.parsers.expat.ParserCreate()
                parser.StartElementHandler = lambda tag, attrs: literal_tags.update([tag])
                parser.Parse(data, True)
    assert len(reports) == 2
    assert literal_tags['mesh'] == 2 and literal_tags['item'] == 2
    assert literal_tags['triangle'] == sum(r['triangles'] for r in reports)
    scene = trimesh.load(target, process=False)
    assert len(scene.geometry) == 2
    assert all(m.is_watertight and m.is_volume for m in scene.geometry.values())
    side = BASE / 'print_jobs/00G-C1_ABS_received_camera_fit_tests.print.json'
    info = json.loads(side.read_text())
    for obj in info['objects']:
        obj['stl'] = os.path.relpath((side.parent / obj['stl']).resolve(), OUT).replace('\\', '/')
    info['print']['process_file'] = os.path.relpath((side.parent / info['print']['process_file']).resolve(), OUT).replace('\\', '/')
    info['geometry_3mf'] = target.name
    info['geometry_sha256'] = hashlib.sha256(target.read_bytes()).hexdigest()
    info['sidecar'] = NAME + '.print.json'
    info['native_save_as_pattern'] = '00G-C1_WELDED_v2_QIDI_native_vNN.3mf'
    (OUT / info['sidecar']).write_text(json.dumps(info, indent=2) + '\n')
    report = dict(source=str(SOURCE), output=str(target), objects=reports,
                  source_sha256=hashlib.sha256(SOURCE.read_bytes()).hexdigest(),
                  output_sha256=info['geometry_sha256'],
                  literal_xml_tag_counts=dict(literal_tags),
                  scene_import_objects=len(scene.geometry),
                  scope='Exact-coordinate weld with default core XML namespace; dimensions, labels, transforms and placement unchanged.',
                  topology='PASS', native_slicer_preview='PENDING', physical_fit='PENDING')
    (OUT / (NAME + '.validation.json')).write_text(json.dumps(report, indent=2) + '\n')
    print(json.dumps(report, indent=2))


if __name__ == '__main__':
    main()
