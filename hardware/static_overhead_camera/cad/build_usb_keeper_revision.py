"""Export a cover-only, photo-informed USB clearance revision; preserve old plates."""
from pathlib import Path
import hashlib
import json
import zipfile
import xml.etree.ElementTree as ET
import numpy as np
import trimesh
from cadquery import exporters
import generate_printable_frame as g
from repair_00g_c1_mesh import NS, inspect

BASE = Path(__file__).resolve().parent.parent
OUT = BASE / 'cad/output/revisions/08D-C2_usb_keeper_v1'
NAME = '08D-C2_ABS_USB_clearance_keeper_v1'


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    original = g.camera_cage_keeper()
    # Camera USB is on the back face, near the edge opposite the tether wing.
    # Retain the original upper window; union it with a rounded lower opening.
    # Bounds: x31..65, y20..48. Original window: x/y33.5..62.5.
    # This extends the lower opening by 13.5 mm and widens it by 5 mm total.
    relief = g.rounded_plate(34, 28, 8, 2, 31, 20, -1)
    revised = original.cut(relief).clean()
    assert revised.val().isValid() and len(revised.solids().vals()) == 1
    assert original.val().Volume() > revised.val().Volume()
    # Only the intended relief is removed; no geometry is added elsewhere.
    assert revised.val().cut(original.val()).Volume() < 1e-6
    assert original.val().cut(revised.val()).cut(relief.val()).Volume() < 1e-6
    # Preserve all closure holes, counterbores, leveling/tool bays and perimeter.
    zones = [(x-6, y-6, 12, 12) for x,y in ((14,38),(82,38),(14,74),(82,74))]
    zones += [(5,0,22,29),(69,0,22,29),(37,76,22,15)]
    for x,y,w,h in zones:
        region = g.box_ll(w,h,8,x,y,-1).val()
        a, b = original.val().intersect(region), revised.val().intersect(region)
        assert a.cut(b).Volume() + b.cut(a).Volume() < 1e-6
    # Conservative DESIGN allowance, not a precision measurement from photos:
    # a 30 x 16 plug envelope at x33..63,y23..39 is wholly unobstructed.
    envelope = g.box_ll(30,16,8,33,23,-1).val()
    assert revised.val().intersect(envelope).Volume() < 1e-6
    exporters.export(revised, str(OUT / (NAME+'.step')))
    exporters.export(revised, str(OUT / (NAME+'.stl')), tolerance=.035, angularTolerance=.06)
    raw = trimesh.load_mesh(OUT / (NAME+'.stl'), process=False)
    vertices, inverse = np.unique(raw.vertices, axis=0, return_inverse=True)
    mesh = trimesh.Trimesh(vertices, inverse[raw.faces], process=False)
    assert mesh.is_volume and len(mesh.split()) == 1
    mesh.apply_translation([10-mesh.bounds[0,0],10-mesh.bounds[0,1],-mesh.bounds[0,2]])
    assert np.all(mesh.bounds[0] >= [6,6,-1e-6]) and np.all(mesh.bounds[1] <= [289,289,275])
    source = BASE / 'cad/output/plates_3mf/08D-C1_ABS_camera_cage_and_keeper.3mf'
    with zipfile.ZipFile(source) as archive:
        # Retain only generic package descriptors; discard stale plate metadata.
        files = {n:archive.read(n) for n in ('[Content_Types].xml','_rels/.rels')}
    root = ET.Element(NS+'model', unit='millimeter')
    resources = ET.SubElement(root,NS+'resources')
    obj = ET.SubElement(resources,NS+'object',id='1',type='model',name=NAME)
    xmlmesh = ET.SubElement(obj,NS+'mesh')
    vs,ts = ET.SubElement(xmlmesh,NS+'vertices'),ET.SubElement(xmlmesh,NS+'triangles')
    for v in mesh.vertices:
        ET.SubElement(vs,NS+'vertex',**dict(zip(('x','y','z'),map(str,v))))
    for f in mesh.faces:
        ET.SubElement(ts,NS+'triangle',**dict(zip(('v1','v2','v3'),map(str,f))))
    ET.SubElement(ET.SubElement(root,NS+'build'),NS+'item',objectid='1')
    data = ET.tostring(root,encoding='utf-8',xml_declaration=True)
    assert b'<model ' in data and b'<mesh>' in data and b'<ns0:' not in data
    files['3D/3dmodel.model'] = data
    target = OUT / (NAME+'.3mf')
    with zipfile.ZipFile(target,'w',zipfile.ZIP_DEFLATED) as archive:
        for name,content in files.items():
            archive.writestr(name,content)
    with zipfile.ZipFile(target) as archive:
        records = inspect(ET.fromstring(archive.read('3D/3dmodel.model')),False)
    scene = trimesh.load(target,process=False)
    assert len(records) == len(scene.geometry) == 1
    assert all(m.is_volume for m in scene.geometry.values())
    report = dict(status='PASS_GEOMETRY_ONLY', objects=records,
        revision='Cover only; existing cage and selected physical shims unchanged',
        relief_bounds_xy_mm=[[31,20],[65,48]], relief_corner_radius_mm=2,
        lower_extension_mm=13.5, widening_total_mm=5,
        design_plug_envelope_mm=[30,16], design_plug_envelope_bounds_xy_mm=[[33,23],[63,39]],
        dimension_basis='Oblique tape photos; thickness approximately 10-12 mm, not metrology. Envelope includes design allowance.',
        preserved_features='All closure and leveling/tool features; verified local Boolean equality',
        original_volume_mm3=original.val().Volume(), revised_volume_mm3=revised.val().Volume(),
        sha256=hashlib.sha256(target.read_bytes()).hexdigest(),
        physical_plug_insertion_and_thumb_access='PENDING', native_QIDI_preview='PENDING',
        full_carriage_route='NOT_VALIDATED: old 56 mm carriage aperture must be reviewed for back-exiting plug at all offsets',
        retention='User reports spacers secure camera; no load or overhead qualification implied')
    (OUT/(NAME+'.validation.json')).write_text(json.dumps(report,indent=2)+'\n')
    side = dict(geometry_3mf=target.name,expected_object_count=1,quantity=1,material='QIDI ABS Rapido',
        process='RoCell ABS Rapido Camera Holder Precision 0.16',scale_percent=100,
        orientation='Flat as supplied; counterbores upward',supports=False,layer_height_mm=.16,
        walls=5,top_layers=7,bottom_layers=7,infill='45% gyroid',brim='Outer 6 mm; gap 0.05 mm',
        filament='Keep existing validated ABS filament preset',geometry_sha256=report['sha256'])
    (OUT/(NAME+'.print.json')).write_text(json.dumps(side,indent=2)+'\n')
    # Orthographic mesh-section drawing for visual review of the delivered STL.
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    fig,ax = plt.subplots(figsize=(7,7))
    localmesh = trimesh.Trimesh(vertices,inverse[raw.faces],process=False)
    for z,color in ((.8,'black'),(4,'#2375ae')):
        section = localmesh.section(plane_origin=[0,0,z],plane_normal=[0,0,1])
        for loop in section.discrete:
            ax.plot(loop[:,0],loop[:,1],color=color,linewidth=1)
    ax.add_patch(plt.Rectangle((33,23),30,16,fill=False,color='#d47b16',linestyle='--',label='Design plug allowance'))
    ax.annotate('Extended USB clearance',xy=(48,21),xytext=(48,10),ha='center',arrowprops={'arrowstyle':'->'})
    ax.set(xlim=(-3,99),ylim=(0,96),aspect='equal',xlabel='mm',ylabel='mm',title='Replacement keeper — top view\nBlack: lower section; blue: upper counterbores')
    ax.legend(loc='upper right',fontsize=8)
    fig.tight_layout()
    fig.savefig(OUT/'keeper_review.png',dpi=170)
    print(target)
    print('PASS: one closed solid; enlarged USB relief; fastener interfaces unchanged.')


if __name__ == '__main__':
    main()
