"""Read-only geometry review; write layer-screening report and CAD previews."""
from pathlib import Path
import sys
import json
import numpy as np
import trimesh

ROOT=Path(__file__).resolve().parents[3]
sys.path.insert(0,str(ROOT/'tmp/coupon_rebuild_deps'))
from shapely.geometry import Polygon, GeometryCollection

OUT=Path(__file__).resolve().parent/'output/revisions/00G-S1_readable_v2'
NAME='00G-S1_ABS_board_splice_fit_tests_REPAIRED_LABELS_v2'
scene=trimesh.load(OUT/(NAME+'.3mf'),force='scene',process=False)
rows=[]
for name, mesh in scene.geometry.items():
    heights=np.arange(0.1,mesh.bounds[1,2],0.2)
    paths=mesh.section_multiplane([0,0,0],[0,0,1],heights)
    previous=None
    unsupported=[]
    for z,path in zip(heights,paths):
        area=GeometryCollection()
        if path is not None:
            for points in path.discrete:
                assert np.linalg.norm(points[0]-points[-1])<1e-5
                ring=Polygon(points).buffer(0)
                area=area.symmetric_difference(ring)
        if previous is not None:
            pieces=[area] if area.geom_type=='Polygon' else list(area.geoms)
            for piece in pieces:
                if piece.area>0.1 and piece.intersection(previous.buffer(0.02)).area<1e-7:
                    unsupported.append({'z_mm':float(z),'area_mm2':float(piece.area),'bounds':list(piece.bounds)})
        previous=area
    rows.append({'object':name,'sampled_layer_count':len(paths),'unanchored_islands':unsupported})
    print(name, 'layer samples',len(paths),'unanchored islands',len(unsupported),flush=True)
report={'status':'PASS' if all(not r['unanchored_islands'] for r in rows) else 'REVIEW',
        'method':'0.20 mm cross-section sampling at layer midplanes; new regions >0.1 mm2 must intersect previous layer with 0.02 mm numerical buffer',
        'limitations':'Geometric island screen, not QIDI toolpath validation. Does not qualify bridge performance, support-free printing, or physical strength.',
        'objects':rows}
(OUT/'LAYER_SCREEN.json').write_text(json.dumps(report,indent=2)+'\n')

# Real CAD geometry, with raised lettering highlighted only for illustration.
from vtkmodules.vtkCommonCore import vtkPoints
from vtkmodules.vtkCommonDataModel import vtkCellArray, vtkPolyData
from vtkmodules.vtkIOImage import vtkPNGWriter
from vtkmodules.vtkRenderingCore import vtkRenderer,vtkRenderWindow,vtkPolyDataMapper,vtkActor,vtkWindowToImageFilter
import vtkmodules.vtkRenderingOpenGL2
from vtkmodules.util.numpy_support import numpy_to_vtk,numpy_to_vtkIdTypeArray
renderer=vtkRenderer();renderer.SetBackground(0.93,0.94,0.96)
window=vtkRenderWindow();window.SetOffScreenRendering(1);window.SetSize(1700,1250);window.SetMultiSamples(8);window.AddRenderer(renderer)

def add(mesh,color):
    pts=vtkPoints();pts.SetData(numpy_to_vtk(mesh.vertices,deep=True))
    faces=np.column_stack([np.full(len(mesh.faces),3),mesh.faces]).astype(np.int64).ravel()
    cells=vtkCellArray();cells.SetCells(len(mesh.faces),numpy_to_vtkIdTypeArray(faces,deep=True))
    data=vtkPolyData();data.SetPoints(pts);data.SetPolys(cells)
    mapper=vtkPolyDataMapper();mapper.SetInputData(data)
    actor=vtkActor();actor.SetMapper(mapper);actor.GetProperty().SetColor(*color)
    actor.GetProperty().SetAmbient(0.4);actor.GetProperty().SetDiffuse(0.6);renderer.AddActor(actor)

for name,mesh in scene.geometry.items():
    centers=mesh.triangles_center
    if name.startswith('board_saddle'):
        mask=((centers[:,1]>138.5)&np.isclose(centers[:,2],4.2,atol=0.001))|(np.isclose(centers[:,2],19.85,atol=0.001)&(centers[:,0]>84))
    elif name.startswith('u_truss_splice'):
        mask=(centers[:,1]>72.8)&np.isclose(centers[:,2],5.2,atol=0.001)
    elif name.startswith('u_splice_fit'):
        mask=(centers[:,0]>220)&np.isclose(centers[:,2],5.2,atol=0.001)
    else:mask=np.zeros(len(mesh.faces),dtype=bool)
    add(mesh.submesh([np.flatnonzero(~mask)],append=True),(0.18,0.23,0.28))
    if mask.any():add(mesh.submesh([np.flatnonzero(mask)],append=True),(0.95,0.72,0.14))

camera=renderer.GetActiveCamera();camera.SetFocalPoint(127,88,20);camera.SetViewUp(0,1,0);camera.ParallelProjectionOn();camera.SetParallelScale(99)
for filename,position in [('LABELS_TOP_VIEW.png',(127,88,800)),('PLATE_CAD_PREVIEW.png',(210,370,470))]:
    camera.SetPosition(*position);renderer.ResetCameraClippingRange();window.Render()
    capture=vtkWindowToImageFilter();capture.SetInput(window);capture.Update()
    writer=vtkPNGWriter();writer.SetFileName(str(OUT/filename));writer.SetInputConnection(capture.GetOutputPort());writer.Write()
print('CAD previews saved',flush=True)
