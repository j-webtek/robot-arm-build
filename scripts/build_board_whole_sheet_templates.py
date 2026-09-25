"""Untrimmed Letter sheets abut physically: 3 columns x 2 rows, no overlaps."""
from pathlib import Path
import json, textwrap
from collections import Counter
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import letter
from reportlab.lib.units import mm
from pypdf import PdfReader
import pdfplumber
from build_board_paper_templates import DATA, FEATURES, ROOT, BLUE, ORANGE, INK

PW, PH = letter
W, H = 215.9, 279.4
BW, BH = 609.6, 457.2
OX = -25.4
FILE = ROOT/'output/pdf/BOARD_WHOLE_SHEETS_NO_TRIM_LETTER.pdf'
QA = ROOT/'tmp/pdfs/board_whole_sheets'
AUDIT = []

def text(c,x,y,s,size=9,bold=False,color=INK):
    c.setFillColorRGB(*color)
    c.setFont('Helvetica-Bold' if bold else 'Helvetica',size)
    c.drawString(x*mm,y*mm,s)

def para(c,y,title,body):
    text(c,15,y,title,11,True); y-=7
    for line in textwrap.wrap(body,94):
        text(c,15,y,line,9); y-=5
    return y-7

def pagehead(c,title,subtitle):
    text(c,15,263,title,17,True)
    text(c,15,253,subtitle,9)

def tile_id(f):
    return chr(65+int(f['y']//H))+str(int((f['x']-OX)//W)+1)

def intro(c):
    pagehead(c,'Whole sheets. No trimming.','24 x 18 inch board | US Letter PORTRAIT | exact scale 1:1')
    y=para(c,238,'Use this new pack instead of the overlap version.',
        'Print pages 4-9 at Actual Size / 100%, one-sided, on 8.5 x 11 inch US Letter. '
        'Do not use Fit, Shrink, Poster, multiple pages per sheet, or borderless enlargement. '
        'Blank printer margins are already included in the geometry: leave them attached.')
    y=para(c,y,'Six complete sheets: paper edges touch.',
        'The paper rectangle is 25.5 inches wide x 22 inches deep. Set its FRONT edge flush '
        'with the board FRONT edge. Its LEFT edge extends 1 inch beyond the board; '
        'the right extends 1/2 inch and the rear extends 4 inches. Do not fold or trim the overhang.')
    # Scaled assembly diagram; explicitly NOT a drilling template.
    gx,gy,s=45,71,.18
    c.setLineWidth(.6)
    for r in range(2):
        for col in range(3):
            x=gx+col*W*s; yy=gy+r*H*s
            c.setStrokeColorRGB(.55,.58,.63); c.setFillColorRGB(.95,.96,.98)
            c.rect(x*mm,yy*mm,W*s*mm,H*s*mm,fill=1)
            text(c,x+14,yy+23,chr(65+r)+str(col+1),14,True)
    c.setStrokeColorRGB(*BLUE); c.setLineWidth(1.4)
    c.rect((gx+25.4*s)*mm,gy*mm,BW*s*mm,BH*s*mm)
    text(c,gx,gy-7,'FRONT / OPERATOR: paper and board edges flush',9,True)
    text(c,gx,gy+2*H*s+5,'REAR / ROBOT SIDE',9,True)
    text(c,20,48,'Diagram only, not to scale. Blue outline = plywood.',9)
    text(c,20,41,'A1-A3 = pages 4-6. B1-B3 = pages 7-9.',9)
    text(c,20,30,'No cuts. No overlaps. No gaps. Do not rotate individual sheets.',10,True)
    text(c,15,13,'1 / 9 | Layout coordinates preserved; physical print and fit checks required.',8)
    c.showPage()

def schedule(c):
    pagehead(c,'All 13 marking locations','X measured from LEFT board edge; Y from FRONT board edge. Millimeters.')
    text(c,15,238,'SHEET / ID',9,True); text(c,81,238,'X',9,True)
    text(c,102,238,'Y',9,True); text(c,125,238,'BOARD ACTION',9,True)
    y=227
    for i,f in enumerate(FEATURES):
        loc=f['type']=='locator_pin_blind'; color=BLUE if loc else ORANGE
        if i%2==0:
            c.setFillColorRGB(.96,.97,.98); c.rect(13*mm,(y-5)*mm,189*mm,12*mm,fill=1,stroke=0)
        text(c,15,y,f"{tile_id(f)} / {f['id']}",8,True,color)
        text(c,81,y,f"{f['x']:g}",8,color=color); text(c,102,y,f"{f['y']:g}",8,color=color)
        text(c,125,y,'6 mm dia / 15 mm blind*' if loc else 'MARK ONLY / DO NOT DRILL',8,color=color)
        y-=12
    para(c,61,'* Depth is NOT unconditional drilling approval.',
         'Read page 3 before drilling. Four blue circles are locator bores. Nine orange squares '
         'are anchor centers only: their bore diameter, pilot and depth remain unconfirmed. '
         'M4 is the screw thread, not the wood-anchor drill size.')
    text(c,15,23,'No board holes for the camera saddles, factory arm clamp or adhesive tags.',8,True)
    text(c,15,13,'2 / 9 | Source: RC03 workcell_layout.json; anchor selection remains on hold.',8)
    c.showPage()

def controls(c):
    pagehead(c,'Tape, mark, remove','Read before placing the first sheet. Do not drill through the paper.')
    y=240
    for title,body in [
        ('1. Verify the paper and print.',
         'Paper must be 215.9 x 279.4 mm. On EVERY template measure both 100 mm bars '
         '(100.0 +/- 0.2 mm). Check the edge-position ruler: its two ticks must be exactly '
         '25.4 and 50.8 mm from the physical left paper edge; check the 1 and 2 inch bottom-edge ticks too. Scale bars alone cannot detect '
         'a printer shifting the image. Reject any page that fails; do not shift sheets to compensate.'),
        ('2. Place all six sheets before marking.',
         'A1 bottom edge is flush with the board front. Its vertical LEFT BOARD EDGE line is '
         'on the real left wood edge, leaving 25.4 mm of paper overhanging. Butt A2 and A3 '
         'against A1 and each other, with their bottom edges flush. Place B1-B3 immediately '
         'behind A1-A3: bottom paper edges touch the A-row top edges. All printed headers '
         'point toward the rear. Tape each sheet independently so removing one cannot move another.'),
        ('3. Check positions, mark, then remove one sheet at a time.',
         'Verify centers against page 2 using the real board edges; dry-fit the actual printed '
         'stations over them. Use only shallow awl marks at labeled crosses. Tick each ID after '
         'marking, lift that sheet without disturbing its neighbors, and keep it as your record. '
         'B-row sheets have no holes; they complete the board layout. Never position a later sheet '
         'by eye across an empty space left by an already removed sheet.'),
        ('4. Blind locator holes: check the actual board and tool.',
         'Nominal design: four 6 mm round bores, 15 mm usable seating depth; 6 x 20 mm pins '
         'project 5 mm. Measure local board thickness. Leave at least 2 mm of wood beneath '
         'the DEEPEST drill point. In 18 mm wood, total penetration cannot exceed 16 mm. '
         'Scrap-test the actual bit, stop and pin. If the pin cannot seat while keeping that '
         'floor, STOP and revise the tool/depth/pin combination. ROUND and RADIAL both have '
         'round wood bores; radial relief is in the printed station.'),
        ('5. Anchor bores remain HOLD.',
         'Do not drill the nine orange marks until the wood-anchor type, diameter, depth, '
         'pilot and installation face are confirmed. Do not substitute through-bolts. Remove '
         'electronics and paper, and secure the board on sacrificial backing before any drilling. '
         'Never drill into the white table.'),
    ]:
        y=para(c,y,title,body)
    text(c,15,13,'3 / 9 | Nominal board 609.6 x 457.2 mm; use front-left datum, never stretch pattern.',8)
    c.showPage()

def tile(c,r,col):
    name=chr(65+r)+str(col+1); x0=OX+col*W; y0=r*H
    owned=[f for f in FEATURES if tile_id(f)==name]
    # Map coordinate origin is the physical paper corner, not a printable-area corner.
    c.saveState()
    p=c.beginPath(); p.rect(7*mm,7*mm,(W-14)*mm,(H-14)*mm); c.clipPath(p,stroke=0)
    c.translate(-x0*mm,-y0*mm); c.scale(mm,mm)
    c.setStrokeColorRGB(.78,.82,.87); c.setLineWidth(.22); c.setDash(2,2)
    for st in DATA['stations'].values(): c.rect(*st['origin_xy'],*st['outer_envelope'])
    c.setDash(); c.setStrokeColorRGB(*BLUE); c.setLineWidth(.35); c.rect(0,0,BW,BH)
    c.restoreState()
    c.setFillColorRGB(1,1,1); c.rect(10*mm,257*mm,195*mm,16*mm,fill=1,stroke=0)
    text(c,12,266,f'{name} | '+('FRONT ROW' if r==0 else 'REAR ROW'),15,True)
    text(c,12,259,'WHOLE LETTER SHEET | 100% | NO CUT / NO OVERLAP',8,True)
    for f in owned:
        x=f['x']-x0; y=f['y']-y0; loc=f['type']=='locator_pin_blind'; color=BLUE if loc else ORANGE
        c.setStrokeColorRGB(*color); c.setLineWidth(.7)
        if loc: c.circle(x*mm,y*mm,3*mm)
        else: c.rect((x-3)*mm,(y-3)*mm,6*mm,6*mm)
        c.line((x-4)*mm,y*mm,(x+4)*mm,y*mm); c.line(x*mm,(y-4)*mm,x*mm,(y+4)*mm)
        lx=x+6 if x<145 else x-48
        ly=y+10 if y<130 else y-9
        if f['id'] in ('KBL-LOC-ROUND','KBL-HOLD-R','KBR-CLAMP'): lx=x-50
        text(c,lx,ly,f['id'],8,True,color)
        text(c,lx,ly-4,'6 dia / 15 blind*' if loc else 'MARK ONLY / NO DRILL',7,color=color)
        text(c,lx,ly-8,f"X {f['x']:g} / Y {f['y']:g} mm",7,color=color)
        AUDIT.append(dict(id=f['id'],tile=name,x=x,y=y,x0=x0,y0=y0))
    if not owned:
        text(c,35,220,'NO HOLE CENTERS ON THIS SHEET',12,True)
        text(c,35,212,'Keep in position until the whole layout is checked.',9)
        text(c,35,204,'Blank areas are intentional. Do not add holes.',9)
    if col==0:
        c.saveState(); c.translate(22*mm,130*mm); c.rotate(90)
        text(c,0,0,'LEFT BOARD EDGE | 1 inch of paper outside wood',8,True,BLUE); c.restoreState()
    if col==2:
        c.saveState(); c.translate(200*mm,45*mm); c.rotate(90)
        text(c,0,0,'RIGHT BOARD EDGE',8,True,BLUE); c.restoreState()
    if r==1:
        text(c,40,BH-y0+4,'REAR BOARD EDGE | paper continues 4 inches beyond wood',8,True,BLUE)
    # All calibration graphics are inside normal printer margins.
    c.setStrokeColorRGB(*INK); c.setLineWidth(.6)
    c.line(45*mm,35*mm,145*mm,35*mm)
    for x in (45,145): c.line(x*mm,34*mm,x*mm,36*mm)
    text(c,66,29,'X SCALE = 100 mm',8)
    c.line(195*mm,90*mm,195*mm,190*mm)
    for yy in (90,190): c.line(194*mm,yy*mm,196*mm,yy*mm)
    c.saveState(); c.translate(198*mm,101*mm); c.rotate(90)
    text(c,0,0,'Y SCALE = 100 mm',8); c.restoreState()
    c.line(25.4*mm,48*mm,50.8*mm,48*mm)
    for x in (25.4,50.8): c.line(x*mm,46*mm,x*mm,50*mm)
    text(c,22,41,'1 in',7); text(c,48,41,'2 in',7)
    text(c,58,47,'Ticks: 1 and 2 inches from LEFT PAPER EDGE',7)
    c.line(155*mm,25.4*mm,155*mm,50.8*mm)
    for yy in (25.4,50.8): c.line(153*mm,yy*mm,157*mm,yy*mm)
    text(c,159,24,'1 in from bottom',7)
    text(c,159,51,'2 in from bottom',7)
    c.setFillColorRGB(1,1,1); c.rect(10*mm,10*mm,195*mm,12*mm,fill=1,stroke=0)
    text(c,12,19,('BOTTOM PAPER EDGE = FRONT BOARD EDGE' if r==0 else f'BOTTOM PAPER EDGE touches TOP of A{col+1}'),8,True)
    text(c,12,13,f'{name} | page {4+r*3+col}/9 | board X origin {x0:g}, Y origin {y0:g} mm',7)
    c.showPage()

def validate():
    pdf=PdfReader(FILE); assert len(pdf.pages)==9
    assert Counter(a['id'] for a in AUDIT)==Counter(f['id'] for f in FEATURES)
    assert abs(3*W-647.7)<1e-8 and abs(2*H-558.8)<1e-8
    with pdfplumber.open(FILE) as doc:
        for i,p in enumerate(doc.pages):
            assert abs(p.width-PW)<.001 and abs(p.height-PH)<.001
            if i<3: continue
            name=chr(65+(i-3)//3)+str((i-3)%3+1)
            assert any(abs(l['x1']-l['x0']-100*mm)<.02 and abs(l['y1']-l['y0'])<.02 for l in p.lines)
            assert any(abs(l['y1']-l['y0']-100*mm)<.02 and abs(l['x1']-l['x0'])<.02 for l in p.lines)
            for a in [a for a in AUDIT if a['tile']==name]:
                f=next(f for f in FEATURES if f['id']==a['id'])
                assert abs(a['x']+a['x0']-f['x'])<1e-8 and abs(a['y']+a['y0']-f['y'])<1e-8
                assert min(a['x'],W-a['x'],a['y'],H-a['y'])-4>=7
                assert any(abs((l['x0']+l['x1'])/2-a['x']*mm)<.02 and abs(l['y0']-a['y']*mm)<.02 and abs(l['y1']-a['y']*mm)<.02 for l in p.lines)
    QA.mkdir(parents=True,exist_ok=True)
    (QA/'validation.json').write_text(json.dumps({'pages':9,'templates':6,'unique_centers':13,'scale':'100 mm XY vectors verified each sheet','placement':'page corner = board (-25.4 + col*215.9, row*279.4) mm','targets':AUDIT},indent=2))
    print(FILE); print('PASS: six whole-sheet tiles, 13 unique centers, no cuts/overlaps, printable target clearance, exact PDF geometry.')

if __name__=='__main__':
    FILE.parent.mkdir(parents=True,exist_ok=True)
    c=canvas.Canvas(str(FILE),pagesize=letter,pageCompression=1)
    c.setTitle('Whole-sheet board templates | Letter portrait | no trim or overlap')
    intro(c); schedule(c); controls(c)
    for row in range(2):
        for col in range(3): tile(c,row,col)
    c.save(); validate()
