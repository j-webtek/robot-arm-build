"""Check nominal socket-cap + flat-washer geometry, NOT printed-part strength."""
import json
from pathlib import Path
import cadquery as cq
import generate_printable_frame as g

BASE=Path(__file__).resolve().parent.parent
OUT=BASE/'cad/output/revisions/SYSTEM_PRINT_PACK_v1'


def main():
    cases=[]
    def add(part,points,direction):
        for point in points:
            cases.append((part,point,direction))
    add('board_corner_saddle_left',[(61,26,78),(73,26,90)],(0,-1,0))
    add('board_corner_saddle_right',[(131,26,78),(143,26,90)],(0,-1,0))
    add('portal_corner_node_left',[(43,86,0),(31,74,0),(52,45,0),(40,33,0)],(0,0,-1))
    add('portal_corner_node_right',[(83,86,0),(71,74,0),(48,45,0),(60,33,0)],(0,0,-1))
    for name,half in [('u_truss_splice',g.SPLICE_HALF),('u_truss_splice_crossbar_2bolt',g.CROSS_SPLICE_HALF)]:
        add(name,[(half-22,0,35),(half+22,0,35)],(0,-1,0))
    h=g.CROSS_SPLICE_HALF
    add('u_truss_splice_center_4bolt',[(h-22,0,23),(h-10,0,35),(h+10,0,35),(h+22,0,23)],(0,-1,0))
    strap_y0=float(g.CFG['layout']['boom_root_y_mm'])-g.ROOT_STRAP_D/2
    add('boom_crossbar_node',[(g.ROOT_STRAP_W/2+x,y-strap_y0,8) for x in g.ROOT_BOLT_X_OFFSETS for y in (g.ROOT_CROSSBAR_BOLT_Y,g.ROOT_BOOM_BOLT_Y)],(0,0,1))
    # Carriage geometry is on HOLD for USB, but evaluate both bolt index rows.
    add('camera_xy_carriage',[(x+off-g.CARRIAGE_X0,g.CAMERA_Y-g.CARRIAGE_Y0+dy,10) for x in g.BOOM_AXES_X for off in (-17,17) for dy in (0,21)],(0,0,1))
    parts={name:cq.importers.importStep(str(BASE/'cad/output/step'/f'{name}.step')) for name,_,_ in cases}
    reports=[]
    for part,p,d in cases:
        def start(offset):
            return tuple(p[i]+offset*d[i] for i in range(3))
        shape=parts[part]
        # Ring is evaluated outside the actual 5.5 mm clearance bore. A 5.3 mm
        # washer ID necessarily slightly overhangs that bore's edge.
        outer=g.axis_cylinder(start(-.15),d,.15,5)
        inner=g.axis_cylinder(start(-.16),d,.17,g.M5_CLEAR/2)
        support=outer.cut(inner)
        fill=g.intersection_volume(support,shape)/support.val().Volume()
        washer=g.axis_cylinder(start(.001),d,1.2,5).cut(g.axis_cylinder(start(0),d,1.203,2.65))
        head=g.axis_cylinder(start(1.201),d,5,4.25)
        driver=g.axis_cylinder(start(6.202),d,20,2.5)
        overlaps=[g.intersection_volume(s,shape) for s in (washer,head,driver)]
        ok=fill>.98 and max(overlaps)<.02
        reports.append(dict(part=part,head_contact_xyz_mm=p,outward=d,supported_annulus_fraction=fill,
                            maximum_intersection_mm3=max(overlaps),status='PASS' if ok else 'FAIL'))
        print(f'{part} {p}: {reports[-1]["status"]}',flush=True)
    lengths=[]
    for joint,count,length,grip in [('saddle receivers',4,80,68),('portal corners',8,75,66),('upright/boom splices',16,75,62.8),('crossbar splices',8,75,62.8),('boom roots',8,90,80),('carriage',4,85,74)]:
        projection=length-grip-1.2-6
        lengths.append(dict(joint=joint,quantity=count,bolt_length_mm=length,printed_grip_mm=grip,
                            washer_max_thickness_mm=1.2,nut_assumed_height_mm=6,post_nut_projection_mm=round(projection,3),
                            status='PASS_NOMINAL' if projection>=1.6 else 'FAIL'))
    result=dict(status='PASS_GEOMETRY_CONDITIONAL' if all(r['status']=='PASS' for r in reports) and all(r['status']=='PASS_NOMINAL' for r in lengths) else 'FAIL',
        scope='Nominal external hardware envelopes, local bearing support and nominal bolt stack only. NOT strength, torque, creep, material grade, received hardware or full assembly qualification.',
        socket_head=dict(standard='DIN 912 / ISO 4762 M5-0.8',diameter_mm=8.5,height_mm=5,hex_key_mm=4),
        washer=dict(quantity_final=48,material='metal',nominal_ID_mm=5.3,OD_mm=10,max_thickness_mm=1.2,placement='One under each socket head; retain specified flanged nuts'),
        bearing_seats=reports,bolt_stacks=lengths,
        conditions=['Actual head/washer dimensions must fit these envelopes; do not use bare socket heads against ABS as an equivalent flange.',
                    'Actual flanged nut height <=6 mm for tabulated projections; verify full nylon engagement and at least two full threads beyond each nut.',
                    'Use specified bolt lengths; do not substitute 75/80/85/90 mm indiscriminately.',
                    'Existing stainless/12.9 packages differ in grade; load qualification remains outstanding. No torque approval is given.'],
        sources=['https://bossard-embedded.partcommunity.com/3d-cad-models/bn-612-hex-socket-head-cap-screws-fully-threaded-din-912-iso-4762-stainless-steel-a4-bossard-catalog?info=bossard%2F01%2F01_100%2F01_100_100%2F01_100_100_10%2Fbn_610_612_31101%2Fbn_612.prj',
                 'https://www.accu.co.uk/metric-flat-washers/404043-HPW-M5-V1-A4-BL'])
    OUT.mkdir(parents=True,exist_ok=True)
    (OUT/'M5_SOCKET_HEAD_CHECK.json').write_text(json.dumps(result,indent=2)+'\n')
    print(result['status'],flush=True)


if __name__=='__main__':
    main()
