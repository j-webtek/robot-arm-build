#!/usr/bin/env python3
"""Generate board fabrication drawings and full-scale drill templates."""
from __future__ import annotations

import csv
import json
from pathlib import Path

import ezdxf
import matplotlib.pyplot as plt
from matplotlib.patches import Rectangle, Circle
from reportlab.lib.pagesizes import letter, landscape
from reportlab.lib.units import mm
from reportlab.pdfgen import canvas
import svgwrite

ROOT = Path(__file__).resolve().parents[1]
DRAW = ROOT / "drawings"
IMAGES = ROOT / "images"
CFG = ROOT / "config"
DRAW.mkdir(parents=True, exist_ok=True)
IMAGES.mkdir(parents=True, exist_ok=True)
layout = json.loads((CFG / "workcell_layout.json").read_text())
B = layout["board"]
BW, BD = B["width"], B["depth"]


def fixture_rects():
    kb = layout["keyboard"]
    ph = layout["phone"]
    cp = layout["calibration_puck"]
    rects = [
        ("KEYBOARD TRAY", kb["origin_xy"][0], kb["origin_xy"][1], kb["outer_envelope"][0], kb["outer_envelope"][1]),
        ("PHONE CRADLE", ph["origin_xy"][0], ph["origin_xy"][1], ph["outer_envelope"][0], ph["outer_envelope"][1]),
        ("TCP CALIBRATION", cp["origin_xy"][0], cp["origin_xy"][1], cp["size"][0], cp["size"][1]),
    ]
    for name, (x, y) in layout["tags"].items():
        rects.append((f"TAG {name}", x, y, 65, 65))
    return rects


def hole_rows():
    names = []
    names += [f"KB-L{i}" for i in range(1,5)]
    names += [f"KB-R{i}" for i in range(1,5)]
    names += ["KB-CLAMP-1", "KB-CLAMP-2"]
    names += [f"PHONE-{i}" for i in range(1,5)]
    names += ["CAL-1", "CAL-2"]
    for tag in ("T0","T1","T2","T3","K0","P0"):
        names += [f"{tag}-A", f"{tag}-B"]
    assert len(names) == len(layout["pilot_holes"])
    return [dict(id=n, **h) for n, h in zip(names, layout["pilot_holes"])]


def generate_csv():
    with (DRAW / "board_hole_coordinates.csv").open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=["id", "x", "y", "diameter", "instruction"])
        w.writeheader()
        for r in hole_rows():
            rr = dict(r)
            rr["instruction"] = "3.0 mm pilot for wood screw OR 4.5-5.0 mm through-hole for M4 bolt"
            w.writerow(rr)


def generate_dxf():
    doc = ezdxf.new("R2010", setup=True)
    doc.units = ezdxf.units.MM
    for layer, color in [("BOARD",7),("FIXTURES",5),("HOLES",1),("TAGS",3),("ARM_ZONE",2),("TEXT",7),("CENTER",4)]:
        if layer not in doc.layers:
            doc.layers.add(layer, color=color)
    msp = doc.modelspace()
    msp.add_lwpolyline([(0,0),(BW,0),(BW,BD),(0,BD),(0,0)], dxfattribs={"layer":"BOARD"})
    for name,x,y,w,h in fixture_rects():
        layer = "TAGS" if name.startswith("TAG") else "FIXTURES"
        msp.add_lwpolyline([(x,y),(x+w,y),(x+w,y+h),(x,y+h),(x,y)], dxfattribs={"layer":layer})
        msp.add_text(name, dxfattribs={"height":5,"layer":"TEXT"}).set_placement((x+3,y+h-8))
    # Keyboard split line.
    kb = layout["keyboard"]
    sx = kb["origin_xy"][0] + kb["outer_envelope"][0]/2
    msp.add_line((sx,kb["origin_xy"][1]),(sx,kb["origin_xy"][1]+kb["outer_envelope"][1]),dxfattribs={"layer":"CENTER"})
    # Arm clamp zone.
    ax0,ax1 = layout["arm_clamp_zone"]["rear_edge_x_range"]
    msp.add_lwpolyline([(ax0,BD-30),(ax1,BD-30),(ax1,BD),(ax0,BD),(ax0,BD-30)],dxfattribs={"layer":"ARM_ZONE"})
    msp.add_text("ROARM FACTORY CLAMP ZONE - NO DRILLING",dxfattribs={"height":5,"layer":"TEXT"}).set_placement((ax0+3,BD-18))
    for r in hole_rows():
        msp.add_circle((r["x"],r["y"]), r["diameter"]/2,dxfattribs={"layer":"HOLES"})
        msp.add_line((r["x"]-4,r["y"]),(r["x"]+4,r["y"]),dxfattribs={"layer":"CENTER"})
        msp.add_line((r["x"],r["y"]-4),(r["x"],r["y"]+4),dxfattribs={"layer":"CENTER"})
        msp.add_text(r["id"],dxfattribs={"height":3,"layer":"TEXT"}).set_placement((r["x"]+3,r["y"]+3))
    msp.add_text("ORIGIN (0,0) FRONT-LEFT; +X RIGHT; +Y REAR",dxfattribs={"height":6,"layer":"TEXT"}).set_placement((10,BD+10))
    doc.saveas(DRAW / "board_610x457_drill_layout.dxf")


def generate_svg():
    dwg = svgwrite.Drawing(str(DRAW / "board_610x457_drill_layout.svg"), size=(f"{BW}mm", f"{BD+25}mm"), viewBox=f"0 -25 {BW} {BD+25}")
    # SVG y is downward, so flip board coordinates around BD.
    g = dwg.g(transform=f"translate(0,{BD}) scale(1,-1)")
    g.add(dwg.rect(insert=(0,0), size=(BW,BD), fill="white", stroke="black", stroke_width=1))
    for name,x,y,w,h in fixture_rects():
        stroke = "#2e6fbb" if not name.startswith("TAG") else "#2a8f55"
        g.add(dwg.rect(insert=(x,y), size=(w,h), fill="none", stroke=stroke, stroke_width=0.8))
    kb=layout["keyboard"]; sx=kb["origin_xy"][0]+kb["outer_envelope"][0]/2
    g.add(dwg.line(start=(sx,kb["origin_xy"][1]),end=(sx,kb["origin_xy"][1]+kb["outer_envelope"][1]),stroke="#777",stroke_dasharray="4,3"))
    ax0,ax1=layout["arm_clamp_zone"]["rear_edge_x_range"]
    g.add(dwg.rect(insert=(ax0,BD-30),size=(ax1-ax0,30),fill="none",stroke="#c33",stroke_dasharray="5,3"))
    for r in hole_rows():
        g.add(dwg.circle(center=(r["x"],r["y"]),r=r["diameter"]/2,fill="none",stroke="#d22",stroke_width=0.5))
        g.add(dwg.line(start=(r["x"]-3,r["y"]),end=(r["x"]+3,r["y"]),stroke="#d22",stroke_width=0.35))
        g.add(dwg.line(start=(r["x"],r["y"]-3),end=(r["x"],r["y"]+3),stroke="#d22",stroke_width=0.35))
    dwg.add(g)
    # Text unflipped.
    for name,x,y,w,h in fixture_rects():
        dwg.add(dwg.text(name, insert=(x+3, BD-(y+h)+9), font_size="5px", font_family="sans-serif"))
    for r in hole_rows():
        dwg.add(dwg.text(r["id"], insert=(r["x"]+3, BD-r["y"]-3), font_size="3px", font_family="sans-serif"))
    dwg.add(dwg.text("RoCell v0.2 board fabrication layout - dimensions in mm", insert=(8,-8), font_size="7px", font_weight="bold", font_family="sans-serif"))
    dwg.add(dwg.text("Origin: front-left. +X right. +Y rear/toward arm.", insert=(8,-16), font_size="5px", font_family="sans-serif"))
    dwg.save()


def draw_reportlab_layout(c, ox_pt=0, oy_pt=0, scale=1.0, labels=True):
    """Draw at physical scale with board origin shifted by ox/oy points."""
    c.saveState()
    c.translate(ox_pt, oy_pt)
    c.setLineWidth(0.5)
    c.setStrokeColorRGB(0,0,0)
    c.rect(0,0,BW*mm*scale,BD*mm*scale,stroke=1,fill=0)
    for name,x,y,w,h in fixture_rects():
        if name.startswith("TAG"):
            c.setStrokeColorRGB(0.1,0.55,0.25)
        else:
            c.setStrokeColorRGB(0.1,0.35,0.7)
        c.rect(x*mm*scale,y*mm*scale,w*mm*scale,h*mm*scale,stroke=1,fill=0)
        if labels:
            c.setFillColorRGB(0,0,0); c.setFont("Helvetica",5.5)
            c.drawString((x+3)*mm*scale,(y+h-8)*mm*scale,name)
    kb=layout["keyboard"]
    sx=kb["origin_xy"][0]+kb["outer_envelope"][0]/2
    c.setStrokeColorRGB(0.45,0.45,0.45); c.setDash(3,2)
    c.line(sx*mm*scale,kb["origin_xy"][1]*mm*scale,sx*mm*scale,(kb["origin_xy"][1]+kb["outer_envelope"][1])*mm*scale)
    c.setDash()
    ax0,ax1=layout["arm_clamp_zone"]["rear_edge_x_range"]
    c.setStrokeColorRGB(0.8,0.1,0.1); c.setDash(4,2)
    c.rect(ax0*mm*scale,(BD-30)*mm*scale,(ax1-ax0)*mm*scale,30*mm*scale,stroke=1,fill=0)
    c.setDash()
    if labels:
        c.setFillColorRGB(0.65,0,0); c.setFont("Helvetica-Bold",6)
        c.drawCentredString(((ax0+ax1)/2)*mm*scale,(BD-18)*mm*scale,"ROARM CLAMP ZONE")
    for r in hole_rows():
        c.setStrokeColorRGB(0.85,0.05,0.05)
        c.circle(r["x"]*mm*scale,r["y"]*mm*scale,r["diameter"]/2*mm*scale,stroke=1,fill=0)
        c.line((r["x"]-3)*mm*scale,r["y"]*mm*scale,(r["x"]+3)*mm*scale,r["y"]*mm*scale)
        c.line(r["x"]*mm*scale,(r["y"]-3)*mm*scale,r["x"]*mm*scale,(r["y"]+3)*mm*scale)
        if labels:
            c.setFillColorRGB(0.7,0,0); c.setFont("Helvetica",4.2)
            c.drawString((r["x"]+3)*mm*scale,(r["y"]+3)*mm*scale,r["id"])
    c.restoreState()


def generate_tiled_pdf():
    path = DRAW / "board_drill_template_letter_1to1.pdf"
    page = landscape(letter)
    pw, ph = page
    # Keep the full-scale drawing inside a 14 mm border so the scale bar and
    # instructions remain outside the board geometry on every tile.
    margin = 14*mm
    usable_w = pw-2*margin
    usable_h = ph-2*margin
    overlap = 12*mm
    stride_x = usable_w-overlap
    stride_y = usable_h-overlap
    cols, rows = 3,3
    c = canvas.Canvas(str(path), pagesize=page)
    c.setTitle("RoCell v0.2 full-scale board drill template")
    # Overview page.
    c.setFont("Helvetica-Bold",18); c.drawString(18*mm,ph-20*mm,"RoCell v0.2 - board drill template")
    c.setFont("Helvetica",9)
    c.drawString(18*mm,ph-28*mm,"Board: 610 x 457 mm. The following 9 pages are printed at 1:1 scale.")
    c.drawString(18*mm,ph-34*mm,"Print with 'Actual size' or 100%. Do not use Fit/Shrink. Verify the 100 mm bar on every tile.")
    scale=min((pw-36*mm)/(BW*mm),(ph-55*mm)/(BD*mm))
    draw_reportlab_layout(c,18*mm,15*mm,scale=scale,labels=True)
    c.showPage()
    # Tiles from front-left to rear-right.
    for row in range(rows):
        for col in range(cols):
            x0_pt=col*stride_x
            y0_pt=row*stride_y
            c.setFont("Helvetica-Bold",12)
            c.drawString(14*mm,ph-8*mm,f"Tile {chr(65+row)}{col+1} - board X {x0_pt/mm:.1f}..{(x0_pt+usable_w)/mm:.1f} mm; Y {y0_pt/mm:.1f}..{(y0_pt+usable_h)/mm:.1f} mm")
            # Clip drawing to usable window.
            c.saveState()
            p=c.beginPath(); p.rect(margin,margin,usable_w,usable_h)
            c.clipPath(p,stroke=1,fill=0)
            draw_reportlab_layout(c, margin-x0_pt, margin-y0_pt, scale=1.0, labels=True)
            c.restoreState()
            # Page registration box and 100 mm scale bar.
            c.setStrokeColorRGB(0,0,0); c.setLineWidth(0.5)
            c.rect(margin,margin,usable_w,usable_h,stroke=1,fill=0)
            # Scale bar is deliberately below the clipped drawing window.
            bar_x=14*mm; bar_y=7*mm
            c.setLineWidth(1); c.line(bar_x,bar_y,bar_x+100*mm,bar_y)
            for k in range(11):
                hh=4*mm if k in (0,10) else 2*mm
                c.line(bar_x+k*10*mm,bar_y-hh/2,bar_x+k*10*mm,bar_y+hh/2)
            c.setFont("Helvetica",7); c.drawString(bar_x,bar_y+3.2*mm,"100 mm scale check")
            c.setFont("Helvetica",6)
            c.drawRightString(pw-14*mm,3*mm,"Print at Actual Size. Align repeated overlap geometry between neighboring tiles.")
            c.showPage()
    c.save()


def generate_preview_png():
    fig,ax=plt.subplots(figsize=(13,9))
    ax.add_patch(Rectangle((0,0),BW,BD,facecolor="#f4f1ea",edgecolor="black",linewidth=2))
    for name,x,y,w,h in fixture_rects():
        ec="#28895a" if name.startswith("TAG") else "#2f6fb0"
        ax.add_patch(Rectangle((x,y),w,h,facecolor="none",edgecolor=ec,linewidth=1.5))
        ax.text(x+w/2,y+h/2,name,ha="center",va="center",fontsize=8)
    kb=layout["keyboard"]; sx=kb["origin_xy"][0]+kb["outer_envelope"][0]/2
    ax.plot([sx,sx],[kb["origin_xy"][1],kb["origin_xy"][1]+kb["outer_envelope"][1]],"--",color="gray")
    ax0,ax1=layout["arm_clamp_zone"]["rear_edge_x_range"]
    ax.add_patch(Rectangle((ax0,BD-30),ax1-ax0,30,facecolor="none",edgecolor="red",linestyle="--",linewidth=1.5))
    ax.text((ax0+ax1)/2,BD-15,"RoArm clamp zone",ha="center",va="center",fontsize=8,color="red")
    for r in hole_rows():
        ax.add_patch(Circle((r["x"],r["y"]),r["diameter"]/2,facecolor="none",edgecolor="red",linewidth=0.7))
        ax.text(r["x"]+3,r["y"]+3,r["id"],fontsize=5,color="darkred")
    ax.set_xlim(-20,BW+20); ax.set_ylim(-20,BD+35); ax.set_aspect("equal")
    ax.set_xlabel("X mm - right"); ax.set_ylabel("Y mm - rear/toward arm")
    ax.set_title("RoCell v0.2 board fabrication layout (610 x 457 mm)")
    ax.grid(True,linewidth=0.25,alpha=0.5)
    fig.tight_layout(); fig.savefig(IMAGES/"board_layout_dimensioned.png",dpi=180); plt.close(fig)


def main():
    generate_csv(); generate_dxf(); generate_svg(); generate_tiled_pdf(); generate_preview_png()
    print("generated board drawings")

if __name__ == "__main__":
    main()
