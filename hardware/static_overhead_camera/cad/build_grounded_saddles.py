"""Fix saddle floating rib starts; check layers/interfaces; export paired revision."""
from pathlib import Path
import sys
import json
import hashlib
import math
import zipfile
import xml.etree.ElementTree as ET
import shutil
import numpy as np
import cadquery as cq
from cadquery import exporters
import trimesh

WORKSPACE=Path(__file__).resolve().parents[3]
sys.path.insert(0,str(WORKSPACE/'tmp/coupon_rebuild_deps'))
from shapely.geometry import Polygon, GeometryCollection
import generate_printable_frame as g
from repair_00g_c1_mesh import NS,inspect

BASE=Path(__file__).resolve().parent.parent
OUT=BASE/'cad/output/revisions/SADDLES_GROUNDED_v2'


def section(mesh,z):
    cut=mesh.section(plane_origin=[0,0,z],plane_normal=[0,0,1])
    result=GeometryCollection()
    if cut is None: return result
    for loop in cut.discrete:
        if len(loop)<4: continue
        p=Polygon(loop[:,:2])
        if not p.is_valid: p=p.buffer(0)
        result=result.symmetric_difference(p)
    return result


def layer_check(mesh,layer_height):
    previous=section(mesh,.1)
    islands=[]
    max_components=0
    # Sample actual layer centers: first layer 0.2 mm, then chosen height.
    heights=np.arange(.2+layer_height/2,mesh.bounds[1,2],layer_height)
    for z in heights:
        current=section(mesh,float(z))
        regions=list(current.geoms) if hasattr(current,'geoms') else [current]
        max_components=max(max_components,len(regions))
        for region in regions:
            # A disconnected slice is not necessarily a floating island:
            # check support against the immediately preceding layer.
            if region.area>.01 and not region.intersects(previous):
                islands.append(dict(z_mm=round(float(z),4),area_mm2=round(region.area,5),bounds_xy_mm=list(region.bounds)))
        previous=current
    return dict(layer_height_mm=layer_height,first_layer_mm=.2,sampled_layers=len(heights)+1,
                unsupported_new_regions=islands,max_slice_components=max_components,
                status='PASS_NO_NEW_ISLANDS' if not islands else 'FAIL')


def mesh_for(shape,path):
    exporters.export(shape,str(path),tolerance=.035,angularTolerance=.06)
    raw=trimesh.load_mesh(path,process=False)
    vertices,inverse=np.unique(raw.vertices,axis=0,return_inverse=True)
    mesh=trimesh.Trimesh(vertices,inverse[raw.faces],process=False)
    assert mesh.is_volume and len(mesh.split())==1
    return mesh


def main():
    OUT.mkdir(parents=True,exist_ok=True)
    upright=cq.importers.importStep(str(BASE/'cad/output/step/upright_truss_segment_240.step'))
    reports=[]
    for hand,prefix,x_axis in [('left','08A-S1',60),('right','08B-S1',130)]:
        name=f'{prefix}_ABS_{hand}_bench_saddle_GROUNDED_v2'
        original=cq.importers.importStep(str(BASE/f'cad/output/step/board_corner_saddle_{hand}.step'))
        fixed=g.saddle_printability_correction(original,hand)
        assert fixed.val().isValid() and len(fixed.solids().vals())==1
        feet=g.box_ll(10,30,16,10,116,0).union(g.box_ll(10,30,16,72,116,0))
        pocket=g.box_ll(65,52,37,27.5,34,68)
        if hand=='right':
            feet=feet.mirror('YZ').translate((190,0,0))
            pocket=pocket.mirror('YZ').translate((190,0,0))
        added=fixed.val().cut(original.val())
        removed=original.val().cut(fixed.val())
        assert added.cut(feet.val()).Volume()<1e-5
        assert removed.cut(pocket.val()).Volume()<1e-5
        # Every surface outside those precise zones is unmodified. Explicit
        # checks protect lower M6 hardware and ledges/receiver bolt stations.
        clamp_zone=g.box_ll(96,70,40,94 if hand=='left' else 0,95,0)
        a=original.val().intersect(clamp_zone.val()); b=fixed.val().intersect(clamp_zone.val())
        assert a.cut(b).Volume()+b.cut(a).Volume()<1e-5
        placed_upright=g._placed_upright(upright,x_axis,60,68)
        upright_overlap=g.intersection_volume(fixed,placed_upright)
        assert upright_overlap<.02,upright_overlap
        # Vertical insertion clearance above both original bearing ledges.
        assert g.intersection_volume(fixed,pocket)<1e-5
        # Preserve each M5 bore and its two exterior washer-bearing seats.
        receiver_x=(61,73) if hand=='left' else (131,143)
        for x,z in zip(receiver_x,(78,90)):
            for y in (26,86):
                zone=g.box_ll(14,8,14,x-7,y,z-7).val()
                a=original.val().intersect(zone); b=fixed.val().intersect(zone)
                assert a.cut(b).Volume()+b.cut(a).Volume()<1e-5
        mesh=mesh_for(fixed,OUT/(name+'.stl'))
        exporters.export(fixed,str(OUT/(name+'.step')))
        checks=[layer_check(mesh,h) for h in (.2,.16)]
        print(hand,[(c['layer_height_mm'],c['status'],c['unsupported_new_regions']) for c in checks],flush=True)
        assert all(c['status']=='PASS_NO_NEW_ISLANDS' for c in checks)
        # Keep the original stored 90-degree XY rotation and 10 mm margin.
        placed=mesh.copy()
        placed.apply_transform(trimesh.transformations.rotation_matrix(math.pi/2,(0,0,1)))
        placed.apply_translation([10-placed.bounds[0,0],10-placed.bounds[0,1],-placed.bounds[0,2]])
        assert np.allclose(placed.bounds,[[10,10,0],[260,200,104]],atol=.001)
        source=BASE/f'cad/output/plates_3mf/{prefix}_ABS_{hand}_bench_saddle.3mf'
        with zipfile.ZipFile(source) as archive:
            files={n:archive.read(n) for n in ('[Content_Types].xml','_rels/.rels')}
        root=ET.Element(NS+'model',unit='millimeter')
        resources=ET.SubElement(root,NS+'resources')
        obj=ET.SubElement(resources,NS+'object',id='1',type='model',name=name)
        xm=ET.SubElement(obj,NS+'mesh')
        vs,ts=ET.SubElement(xm,NS+'vertices'),ET.SubElement(xm,NS+'triangles')
        for v in placed.vertices:
            ET.SubElement(vs,NS+'vertex',**dict(zip(('x','y','z'),map(str,v))))
        for f in placed.faces:
            ET.SubElement(ts,NS+'triangle',**dict(zip(('v1','v2','v3'),map(str,f))))
        ET.SubElement(ET.SubElement(root,NS+'build'),NS+'item',objectid='1')
        data=ET.tostring(root,encoding='utf-8',xml_declaration=True)
        assert b'<model ' in data and b'<ns0:' not in data
        files['3D/3dmodel.model']=data
        target=OUT/(name+'.3mf')
        with zipfile.ZipFile(target,'w',zipfile.ZIP_DEFLATED) as archive:
            for n,content in files.items(): archive.writestr(n,content)
        with zipfile.ZipFile(target) as archive:
            topology=inspect(ET.fromstring(archive.read('3D/3dmodel.model')),False)
        scene=trimesh.load(target,process=False)
        assert len(scene.geometry)==1 and all(m.is_volume for m in scene.geometry.values())
        report=dict(name=name,status='PASS_CAD_MESH_AND_LAYER_START_CHECKS',topology=topology,
                    added_material_mm3=added.Volume(),removed_receiver_intrusion_mm3=removed.Volume(),
                    nominal_upright_interference_mm3=upright_overlap,original_interfaces='UNCHANGED outside explicit feet and insertion pocket',
                    first_layer_contact='Both rib feet begin at z=0 and overlap original base by 4mm in Y',
                    layer_checks=checks,placed_bounds_mm=placed.bounds.tolist(),
                    sha256=hashlib.sha256(target.read_bytes()).hexdigest(),
                    native_QIDI_slice='PENDING: reopen and reslice revised model; do not ignore residual warnings',
                    limitations='Layer-overlap checks detect new floating regions, not all overhang, bridge, adhesion, strength or creep failures. Physical qualification remains required.')
        (OUT/(name+'.validation.json')).write_text(json.dumps(report,indent=2)+'\n')
        side=dict(geometry_3mf=target.name,expected_object_count=1,scale_percent=100,
                  orientation='Foot-down; stored 90-degree XY rotation; do not auto-orient',
                  profile='RoCell ABS Rapido Camera Frame Structural 0.20 Print Pack v1',
                  layer_height_mm=.2,first_layer_mm=.2,walls=6,top_layers=7,bottom_layers=7,
                  infill='40% gyroid',supports=False,brim='10 mm outer, 0.05 mm gap',geometry_sha256=report['sha256'])
        (OUT/(name+'.print.json')).write_text(json.dumps(side,indent=2)+'\n')
        reports.append(report)
        # Mesh-based side view makes grounding and cleared receiver inspectable.
        if hand=='left':
            import matplotlib
            matplotlib.use('Agg')
            import matplotlib.pyplot as plt
            fig,axs=plt.subplots(1,2,figsize=(12,5))
            old_mesh=trimesh.load_mesh(BASE/'cad/output/stl/board_corner_saddle_left.stl')
            for ax,m,title in zip(axs,(old_mesh,mesh),('Original: floating rib tip','v2: grounded tip / clear upright pocket')):
                s=m.section(plane_origin=[77,0,0],plane_normal=[1,0,0])
                for loop in s.discrete:
                    ax.plot(loop[:,1],loop[:,2],color='#244e6b',linewidth=1.4)
                ax.axhline(0,color='black',linewidth=1)
                ax.set(xlim=(15,155),ylim=(-5,110),aspect='equal',xlabel='Local Y (mm)',ylabel='Height (mm)',title=title)
            fig.tight_layout(); fig.savefig(OUT/'saddle_side_comparison.png',dpi=160)
    (OUT/'MANIFEST.json').write_text(json.dumps(dict(revision='GROUNDED_v2',saddles=reports),indent=2)+'\n')
    print('PASS: both revised saddles exported.',flush=True)


if __name__=='__main__':
    main()
