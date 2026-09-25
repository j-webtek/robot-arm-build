"""1:1 US Letter board transfer sheets; anchor bores intentionally unreleased."""
from pathlib import Path
import json, hashlib, csv, math
from reportlab.pdfgen import canvas
from reportlab.lib.units import mm
from reportlab.lib.pagesizes import landscape, letter
from pypdf import PdfReader
import pdfplumber

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / 'active-project/RoCell_v0_3'
OUT = ROOT / 'output/pdf'
QA = ROOT / 'tmp/pdfs/board_transfer_20260918'
LAYOUT = SRC / 'config/workcell_layout.json'
DATA = json.loads(LAYOUT.read_text())
FEATURES = sorted(DATA['board_features'], key=lambda f:(f['x'], f['y']))
BW, BH = 609.6, 457.2  # purchased nominal 24 x 18 inch sheet, not measured
TW, TH, SX, SY = 220, 164, 208, 152
MX, MY = 18, 30
PW, PH = landscape(letter)
FILE = OUT / 'BOARD_24x18_LETTER_TEMPLATES_2026-09-18.pdf'
INK=(.08,.13,.19); BLUE=(.02,.25,.62); ORANGE=(.65,.23,.02); GREY=(.65,.67,.70)
AUDIT=[]

def txt(c,x,y,s,size=9,bold=False,color=INK):
    c.setFillColorRGB(*color)
    c.setFont('Helvetica-Bold' if bold else 'Helvetica',size)
    c.drawString(x*mm,y*mm,s)

def lines(c,x,y,ss,size=10,step=6,color=INK):
    for s in ss:
        txt(c,x,y,s,size,color=color); y-=step
    return y

def head(c,title,sub):
    txt(c,16,200,title,19,True)
    txt(c,16,190,sub,10)

def tile_id(f):
    return chr(65+min(2,int(f['y']//SY)))+str(min(2,int(f['x']//SX))+1)

def grid(c,x,y,w=45,h=28,active=None):
    for r in range(3):
        for col in range(3):
            name=chr(65+r)+str(col+1)
            c.setFillColorRGB(*((.80,.89,.98) if name==active else (.95,.96,.97)))
            c.setStrokeColorRGB(*GREY)
            c.rect((x+col*w)*mm,(y+r*h)*mm,w*mm,h*mm,fill=1)
            txt(c,x+col*w+4,y+r*h+h/2,name,12,True)
    txt(c,x,y-6,'FRONT / operator side',9,True)
    txt(c,x,y+3*h+4,'REAR / robot side',9,True)

def intro(c):
    head(c,'Board templates | 24 x 18 inches','US Letter landscape | September 18, 2026 | front-left datum | no scaling')
    lines(c,16,178,[
        'This set transfers the saved RC03 station layout. It does not approve unknown anchor holes.',
        'All hole centers retain the CAD coordinates; the pattern has NOT been stretched to the board.',
        'Nominal purchased board: 609.6 x 457.2 mm, listed as 18 mm thick. Measure the real board first.',
        'Saved CAD board: 610 x 457 mm. Align FRONT and LEFT; do not force the rear/right edge to fit.',
    ],10,7)
    grid(c,18,51)
    lines(c,165,143,[
        'PAPER ORDER',
        'Pages 4-6: A1, A2, A3 (front)',
        'Pages 7-9: B1, B2, B3 (middle)',
        'Pages 10-12: C1, C2, C3 (rear)',
        '',
        'Work LEFT to RIGHT in each row.',
        'Overlap adjacent drawing rectangles',
        'by 12 mm. Do not butt paper edges.',
        '',
        'Only circles/squares with feature IDs',
        'are mounting-hole centers.',
        'Diamond MATCH marks are NOT holes.'
    ],9,6)
    lines(c,16,35,[
        'FOUR blue circles: nominal 6 mm blind locator bores; read the depth controls on page 3.',
        'NINE orange squares: MARK ONLY. Anchor type, bore diameter and depth are not confirmed.',
        'No board drilling for camera saddles, factory robot clamp or adhesive fiducial tags.',
        'Dry-fit the actual printed stations over the full pattern before making permanent holes.'
    ],10,6)
    c.showPage()

def schedule(c):
    head(c,'Every center | left to right','X from LEFT edge; Y from FRONT edge. Units mm. Printed-part holes are not wood-anchor bore sizes.')
    widths=[15,42,32,24,24,106]; x0=16; y=177
    labels=['TILE','FEATURE ID','COMPONENT','X / LEFT','Y / FRONT','BOARD ACTION / DEPTH']
    xx=x0
    for name,w in zip(labels,widths): txt(c,xx,y,name,8,True); xx+=w
    for i,f in enumerate(FEATURES):
        y-=10
        if i%2==0:
            c.setFillColorRGB(.95,.96,.97); c.rect(x0*mm,(y-3)*mm,247*mm,10*mm,fill=1,stroke=0)
        loc=f['type']=='locator_pin_blind'
        vals=[tile_id(f),f['id'],{'keyboard_left':'Keyboard left','keyboard_right':'Keyboard right','phone_tcp':'Phone / TCP'}[f['station']],f"{f['x']:.2f}",f"{f['y']:.2f}", '6.0 dia x 15.0 blind*; never through' if loc else 'MARK ONLY; bit / depth / pilot TBD']
        xx=x0
        for value,w in zip(vals,widths): txt(c,xx,y,value,8,color=BLUE if loc else ORANGE); xx+=w
    lines(c,16,34,[
        '* Locator depth is usable seating depth; include drill-point penetration in the floor check (page 3).',
        'Both ROUND and RADIAL locators use ROUND board holes. The relief slot is in the printed station.',
        'M4 denotes the screw thread, NOT the required wood-anchor drill size. No anchor pilots released.',
        'Sources: RC03 workcell_layout.json / generate_cad.py; FASTENER_MAP.csv has unselected anchors.'
    ],9,6)
    c.showPage()

def controls(c):
    head(c,'Print, tape, verify, then mark','The paper provides center locations; the physical board, hardware and printed stations must agree.')
    items=[
        ('1  PRINT', ['Print pages 4-12 on US Letter, landscape, one-sided, Actual Size / 100%.',
                       'Disable Fit, Shrink, Poster and borderless enlargement. Do not mix these tiles with older guides.']),
        ('2  CHECK SCALE', ['Measure BOTH 100 mm bars on EVERY sheet before trimming: accept 100.0 +/- 0.2 mm.',
                            'Reject distorted prints. A correct PDF cannot guarantee your printer\'s physical output scale.']),
        ('3  TAPE', ['Trim to each drawing rectangle. Overlap drawing content 12 mm using matching diamond IDs.',
                     'Align at least two matching targets per seam; tape without stretching. A row is left-to-right.',
                     'Check the assembled nominal outline is 609.6 x 457.2 mm, diagonal 762.0 mm.']),
        ('4  VERIFY / MARK', ['Put FRONT toward the operator, REAR toward the robot. Align the real front-left corner.',
                              'Measure every center independently from the front/left edges using page 2. Dry-fit stations.',
                              'Make shallow awl marks only after agreement. Remove paper and electronics before drilling.']),
        ('5  LOCATORS', ['Four nominal 6 mm holes, 15 mm usable blind depth, for 6 x 20 mm pins projecting 5 mm.',
                          'Measure local board thickness. Deepest drill tip must leave at least 2 mm wood underneath.',
                          'An 18 mm board allows only 16 mm total penetration: a 15 mm bore leaves 1 mm for the tip.',
                          'Test the actual bit, depth stop and pin in scrap of the same thickness. If that cannot leave',
                          'the required floor AND seat the pin, STOP: depth/tool or pin specification needs revision.',
                          'Keep the drill square. Any pilot must also remain blind. Do not glue pins before full dry fit.']),
        ('6  ANCHORS: HOLD', ['Nine orange centers have no approved wood-anchor diameter, depth, pilot or installation face.',
                                'Do not drill them yet. Screws and loose nuts do not define a threaded wood-anchor installation.',
                                'Do not substitute through-bolts: underside nuts could lift the board off the tabletop.']),
    ]
    y=179
    for title,ss in items:
        txt(c,16,y,title,10,True); y-=6
        y=lines(c,20,y,ss,9,5); y-=5
    txt(c,16,9,'No drilling into the white table. Move the board to a secured sacrificial backing before drilling.',9,True)
    c.showPage()

def marks():
    result=[]
    for seam in (1,2):
        for row in range(3):
            for n,yy in enumerate((35,110)):
                result.append((f'V{seam}{row}{n}', seam*SX+6, row*SY+yy))
        for col in range(3):
            for n,xx in enumerate((55,165)):
                result.append((f'H{seam}{col}{n}', col*SX+xx, seam*SY+6))
    return result

def tile(c,row,col):
    name=chr(65+row)+str(col+1); x0=col*SX; y0=row*SY
    txt(c,18,204,f'{name} | '+('FRONT','MIDDLE','REAR')[row]+f' ROW | COLUMN {col+1} | TRUE SIZE 1:1',13,True)
    txt(c,18,198,f'X {x0} to {x0+TW} / Y {y0} to {y0+TH} mm | Trim rectangle; overlap 12 mm | +Y toward REAR',8)
    c.saveState()
    p=c.beginPath(); p.rect(MX*mm,MY*mm,TW*mm,TH*mm); c.clipPath(p,stroke=0)
    c.translate((MX-x0)*mm,(MY-y0)*mm); c.scale(mm,mm)
    c.setStrokeColorRGB(.88,.89,.90); c.setLineWidth(.10)
    for x in range(0,610,25): c.line(x,0,x,BH)
    for y in range(0,458,25): c.line(0,y,BW,y)
    c.setStrokeColorRGB(*INK); c.setLineWidth(.4); c.rect(0,0,BW,BH)
    c.setStrokeColorRGB(.65,.70,.76); c.setDash(2,2)
    for st in DATA['stations'].values(): c.rect(*st['origin_xy'],*st['outer_envelope'])
    c.setDash()
    for tag in DATA['direct_tags']['tags'].values():
        c.setStrokeColorRGB(.55,.65,.57); c.setDash(1,2); c.rect(*tag['tile_origin_xy'],55,55); c.setDash()
    c.setStrokeColorRGB(.6,.2,.2); c.setDash(2,2); c.rect(225,BH-30,160,30); c.setDash()
    c.restoreState()
    # Labels and symbols in local page coordinates, with clipped map graphics above.
    for mid,x,y in marks():
        if x0+4<=x<=x0+TW-4 and y0+4<=y<=y0+TH-4:
            xx=MX+x-x0; yy=MY+y-y0
            c.setStrokeColorRGB(.40,.35,.46); c.setLineWidth(.4)
            p=c.beginPath(); p.moveTo(xx*mm,(yy+2)*mm)
            for a,b in [(xx+2,yy),(xx,yy-2),(xx-2,yy),(xx,yy+2)]: p.lineTo(a*mm,b*mm)
            c.drawPath(p)
            label_x=xx-18 if xx>MX+TW-22 else xx+3
            txt(c,label_x,yy,f'MATCH {mid}',5.5,color=(.40,.35,.46))
    for tagname,tag in DATA['direct_tags']['tags'].items():
        x,y=tag['tile_origin_xy']
        label_dy=35 if tagname=='T1' else 27
        if x0+3<=x+10<=x0+TW-32 and y0+5<=y+label_dy<=y0+TH-5:
            txt(c,MX+x+10-x0,MY+y+label_dy-y0,f'{tagname}: TAG ONLY',7,color=(.3,.45,.33))
            txt(c,MX+x+10-x0,MY+y+label_dy-4-y0,'NO DRILL',7,color=(.3,.45,.33))
    if row==0: txt(c,MX+5,MY+4,'FRONT EDGE / Y=0 / OPERATOR SIDE',7,True)
    if row==2:
        txt(c,MX+5,MY+BH-y0-5,'REAR BOARD EDGE / ROBOT SIDE',7,True)
        if col==1: txt(c,MX+35,MY+BH-y0-19,'FACTORY ARM CLAMP: NO BOARD HOLES',8,True,color=(.6,.2,.2))
    if col==2:
        xx=MX+BW-x0
        c.saveState(); c.translate((xx+4)*mm,(MY+(90 if row==1 else 45))*mm); c.rotate(90)
        txt(c,0,0,'NOMINAL RIGHT BOARD EDGE',7,True); c.restoreState()
    owned=[]
    for f in FEATURES:
        x,y=f['x'],f['y']; loc=f['type']=='locator_pin_blind'
        if not (x0+4<=x<=x0+TW-4 and y0+4<=y<=y0+TH-4): continue
        xx=MX+x-x0; yy=MY+y-y0
        c.setStrokeColorRGB(*(BLUE if loc else ORANGE)); c.setLineWidth(.6)
        if loc: c.circle(xx*mm,yy*mm,3*mm)
        else: c.rect((xx-3)*mm,(yy-3)*mm,6*mm,6*mm)
        c.line((xx-4)*mm,yy*mm,(xx+4)*mm,yy*mm); c.line(xx*mm,(yy-4)*mm,xx*mm,(yy+4)*mm)
        AUDIT.append({'tile':name,'id':f['id'],'x_page_pt':xx*mm,'y_page_pt':yy*mm,'x':x,'y':y,'locator':loc})
        # Repeat every visible feature's ID/action, including overlap targets.
        owned.append(f)
        label=f['id']; action='6 mm / 15 mm BLIND*' if loc else 'MARK ONLY / NO DRILL'
        lx=xx+6; ly=min(yy+7,MY+TH-5)
        if lx+len(action)*1.45>MX+TW: lx=xx-6-max(len(label),len(action))*1.45
        txt(c,lx,ly,label,7,True,color=BLUE if loc else ORANGE)
        txt(c,lx,ly-3.5,action,7,color=BLUE if loc else ORANGE)
    c.setStrokeColorRGB(*INK); c.setLineWidth(.6); c.rect(MX*mm,MY*mm,TW*mm,TH*mm)
    # Orthogonal, exactly 100 mm physical check bars outside trimmed content.
    c.line(18*mm,26*mm,118*mm,26*mm)
    for xx in (18,118): c.line(xx*mm,25*mm,xx*mm,27*mm)
    txt(c,122,25,'X SCALE: 100 mm | verify BEFORE trimming',7)
    c.line(250*mm,65*mm,250*mm,165*mm)
    for yy in (65,165): c.line(249*mm,yy*mm,251*mm,yy*mm)
    c.saveState(); c.translate(255*mm,65*mm); c.rotate(90); txt(c,0,0,'Y SCALE: 100 mm | Actual Size / 100%',8); c.restoreState()
    if owned:
        for i,f in enumerate(owned):
            action='6 dia / 15 usable blind; depth checks p3' if f['type']=='locator_pin_blind' else 'MARK ONLY; diameter/depth TBD'
            txt(c,18,21-i*4,f"{f['id']}  X={f['x']:g} Y={f['y']:g} mm | {action}",7)
    else: txt(c,18,20,'NO DRILL CENTERS ON THIS TILE. Tag outlines and MATCH diamonds are not holes.',8,True)
    txt(c,18,3.5,f'{name} | page {4+row*3+col}/12 | Front-left datum | SRC {hashlib.sha256(LAYOUT.read_bytes()).hexdigest()[:12]} | Nominal board 609.6 x 457.2',6)
    c.showPage()

def validate():
    reader=PdfReader(FILE); assert len(reader.pages)==12
    for page in reader.pages:
        assert abs(float(page.mediabox.width)-PW)<.001
        assert abs(float(page.mediabox.height)-PH)<.001
    with pdfplumber.open(FILE) as pdf:
        for i,page in enumerate(pdf.pages[3:]):
            horiz=[l for l in page.lines if abs(abs(l['x1']-l['x0'])-100*mm)<.02 and abs(l['y1']-l['y0'])<.02]
            vert=[l for l in page.lines if abs(abs(l['y1']-l['y0'])-100*mm)<.02 and abs(l['x1']-l['x0'])<.02]
            assert horiz and vert
            for a in [a for a in AUDIT if a['tile']==chr(65+i//3)+str(i%3+1)]:
                assert any(abs((l['x0']+l['x1'])/2-a['x_page_pt'])<.02 and abs(l['y0']-a['y_page_pt'])<.02 and abs(l['y1']-a['y_page_pt'])<.02 for l in page.lines)
    assert set(a['id'] for a in AUDIT)==set(f['id'] for f in FEATURES)
    assert sum(f['type']=='locator_pin_blind' for f in FEATURES)==4
    # Compare fresh source layout to the earlier independent coordinate schedule.
    old=list(csv.DictReader((SRC/'drawings/board_hole_coordinates.csv').open()))
    for f in FEATURES:
        r=next(r for r in old if r['id']==f['id'])
        assert (float(r['x']),float(r['y']))==(f['x'],f['y'])
        st=DATA['stations'][f['station']]
        assert all(abs(st['origin_xy'][k]+f['local_xy'][k]-f['board_xy'][k])<1e-6 for k in (0,1))
    QA.mkdir(parents=True,exist_ok=True)
    (QA/'validation.json').write_text(json.dumps({'pages':12,'scale':'72/25.4 points per mm; both 100 mm vectors verified on every tile','centers':'13/13 compared with layout, station transforms and prior schedule; PDF center strokes verified','anchors':'HOLD: nine diameters/depths unselected','board':'609.6 x 457.2 nominal; physical measurements pending','targets':AUDIT},indent=2))
    print(FILE)
    print('PASS: 12 pages, 9 exact-scale tiles, all 13 centers, station transforms, PDF center positions and scale bars')

if __name__=='__main__':
    OUT.mkdir(parents=True,exist_ok=True)
    c=canvas.Canvas(str(FILE),pagesize=(PW,PH),pageCompression=1)
    c.setTitle('24x18 Board | 1:1 Letter transfer templates | anchors on hold')
    intro(c); schedule(c); controls(c)
    for r in range(3):
        for col in range(3): tile(c,r,col)
    c.save(); validate()
