#!/usr/bin/env python3
"""Generate exact-size AprilTag tiles and a ChArUco camera-calibration board."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "fiducials"
OUT.mkdir(parents=True, exist_ok=True)

TAG_FAMILY = "tag36h11"
TAG_DETECTION_MM = 40.0
TAG_TILE_MM = 55.0
QUIET_MM = (TAG_TILE_MM - TAG_DETECTION_MM) / 2
TAG_IDS = list(range(6))


def marker_grid(tag_id: int) -> np.ndarray:
    dictionary = cv2.aruco.getPredefinedDictionary(cv2.aruco.DICT_APRILTAG_36h11)
    n = dictionary.markerSize + 2  # one black border cell on each side
    side = n * 100
    img = cv2.aruco.generateImageMarker(dictionary, tag_id, side, borderBits=1)
    cell = side // n
    grid = np.zeros((n, n), dtype=np.uint8)
    for r in range(n):
        for c in range(n):
            grid[r, c] = img[r*cell + cell//2, c*cell + cell//2]
    return grid


def write_tag_svg(tag_id: int, path: Path):
    grid = marker_grid(tag_id)
    n = grid.shape[0]
    cell = TAG_DETECTION_MM / n
    dwg = svgwrite.Drawing(str(path), size=(f"{TAG_TILE_MM}mm", f"{TAG_TILE_MM}mm"), viewBox=f"0 0 {TAG_TILE_MM} {TAG_TILE_MM}")
    dwg.add(dwg.rect(insert=(0,0),size=(TAG_TILE_MM,TAG_TILE_MM),fill="white"))
    for r in range(n):
        for c in range(n):
            if grid[r,c] < 128:
                dwg.add(dwg.rect(insert=(QUIET_MM+c*cell, QUIET_MM+r*cell), size=(cell,cell), fill="black", stroke="none"))
    dwg.save()


def write_tag_png(tag_id: int, path: Path, dpi: int = 600):
    pixels = int(round(TAG_TILE_MM / 25.4 * dpi))
    marker_px = int(round(TAG_DETECTION_MM / 25.4 * dpi))
    q = (pixels-marker_px)//2
    dictionary = cv2.aruco.getPredefinedDictionary(cv2.aruco.DICT_APRILTAG_36h11)
    marker = cv2.aruco.generateImageMarker(dictionary, tag_id, marker_px, borderBits=1)
    canvas_img = np.full((pixels,pixels),255,np.uint8)
    canvas_img[q:q+marker_px,q:q+marker_px]=marker
    im=Image.fromarray(canvas_img,mode="L")
    im.save(path,dpi=(dpi,dpi))


def write_tag_sheet_pdf():
    path = OUT / "apriltag36h11_ID0-5_40mm_detection_edge.pdf"
    c = canvas.Canvas(str(path), pagesize=letter)
    pw,ph=letter
    c.setTitle("RoCell AprilTag 36h11 set")
    c.setFont("Helvetica-Bold",16); c.drawString(16*mm,ph-16*mm,"RoCell runtime AprilTags - family tag36h11")
    c.setFont("Helvetica",8)
    c.drawString(16*mm,ph-23*mm,"Print at 100% / Actual Size. Each black marker detection edge is 40.0 mm; each paper tile is 55.0 mm.")
    c.drawString(16*mm,ph-29*mm,"Do not use Fit, Shrink, or borderless scaling. Measure the 40 mm edge before use.")
    cols=2; rows=3
    start_x=35*mm; start_y=ph-55*mm
    gap_x=85*mm; gap_y=70*mm
    for idx,tag_id in enumerate(TAG_IDS):
        col=idx%cols; row=idx//cols
        x=start_x+col*gap_x; y=start_y-row*gap_y-TAG_TILE_MM*mm
        png=OUT/f"tag36h11_id{tag_id:02d}_tile55_marker40.png"
        c.drawImage(str(png),x,y,TAG_TILE_MM*mm,TAG_TILE_MM*mm,mask="auto")
        c.setFont("Helvetica-Bold",8); c.drawCentredString(x+TAG_TILE_MM*mm/2,y-4*mm,f"ID {tag_id}")
    # 100 mm scale bar.
    bx=55*mm; by=12*mm
    c.setLineWidth(1); c.line(bx,by,bx+100*mm,by)
    for k in range(11):
        hh=4*mm if k in (0,10) else 2*mm
        c.line(bx+k*10*mm,by-hh/2,bx+k*10*mm,by+hh/2)
    c.setFont("Helvetica",7); c.drawString(bx,by+4*mm,"100 mm print-scale check")
    c.save()


def write_tag_sheet_svg():
    width=190.0; height=225.0
    dwg=svgwrite.Drawing(str(OUT/"apriltag36h11_ID0-5_sheet.svg"),size=(f"{width}mm",f"{height}mm"),viewBox=f"0 0 {width} {height}")
    dwg.add(dwg.rect(insert=(0,0),size=(width,height),fill="white"))
    positions=[]
    for idx,tag_id in enumerate(TAG_IDS):
        col=idx%2; row=idx//2
        x=20+col*90; y=15+row*68
        positions.append((tag_id,x,y))
        grid=marker_grid(tag_id); n=grid.shape[0]; cell=TAG_DETECTION_MM/n
        dwg.add(dwg.rect(insert=(x,y),size=(TAG_TILE_MM,TAG_TILE_MM),fill="white",stroke="#999",stroke_width=0.2))
        for r in range(n):
            for c in range(n):
                if grid[r,c]<128:
                    dwg.add(dwg.rect(insert=(x+QUIET_MM+c*cell,y+QUIET_MM+r*cell),size=(cell,cell),fill="black"))
        dwg.add(dwg.text(f"ID {tag_id}",insert=(x+TAG_TILE_MM/2,y+TAG_TILE_MM+5),text_anchor="middle",font_size="4px",font_family="sans-serif"))
    dwg.add(dwg.line(start=(45,218),end=(145,218),stroke="black",stroke_width=0.5))
    for k in range(11):
        hh=4 if k in (0,10) else 2
        dwg.add(dwg.line(start=(45+k*10,218-hh/2),end=(45+k*10,218+hh/2),stroke="black",stroke_width=0.4))
    dwg.add(dwg.text("100 mm",insert=(95,214),text_anchor="middle",font_size="4px",font_family="sans-serif"))
    dwg.save()


def write_charuco():
    # 5 x 7 squares, 25 mm squares, 17.5 mm markers; physical board 125 x 175 mm.
    squares_x,squares_y=5,7
    square_mm,marker_mm=25.0,17.5
    board_w,board_h=squares_x*square_mm,squares_y*square_mm
    dictionary=cv2.aruco.getPredefinedDictionary(cv2.aruco.DICT_5X5_100)
    board=cv2.aruco.CharucoBoard((squares_x,squares_y),square_mm,marker_mm,dictionary)
    px_per_mm=24  # ~610 dpi
    img=board.generateImage((int(board_w*px_per_mm),int(board_h*px_per_mm)),marginSize=0,borderBits=1)
    png=OUT/"charuco_5x7_square25_marker17_5.png"
    Image.fromarray(img,mode="L").save(png,dpi=(px_per_mm*25.4,px_per_mm*25.4))

    pdf=OUT/"charuco_5x7_square25_marker17_5_1to1.pdf"
    c=canvas.Canvas(str(pdf),pagesize=letter)
    pw,ph=letter
    c.setTitle("RoCell ChArUco calibration board")
    c.setFont("Helvetica-Bold",15); c.drawString(14*mm,ph-15*mm,"RoCell camera calibration board - ChArUco")
    c.setFont("Helvetica",8)
    c.drawString(14*mm,ph-22*mm,"5 x 7 squares; square side 25.0 mm; ArUco marker side 17.5 mm; dictionary DICT_5X5_100.")
    c.drawString(14*mm,ph-28*mm,"Print at 100% / Actual Size on matte paper and mount perfectly flat to rigid card/foam board.")
    x=(pw-board_w*mm)/2; y=45*mm
    c.drawImage(str(png),x,y,board_w*mm,board_h*mm,mask="auto")
    c.setLineWidth(0.5); c.rect(x,y,board_w*mm,board_h*mm,stroke=1,fill=0)
    bx=(pw-100*mm)/2; by=25*mm
    c.setLineWidth(1); c.line(bx,by,bx+100*mm,by)
    for k in range(11):
        hh=4*mm if k in (0,10) else 2*mm
        c.line(bx+k*10*mm,by-hh/2,bx+k*10*mm,by+hh/2)
    c.setFont("Helvetica",7); c.drawString(bx,by+4*mm,"100 mm print-scale check")
    c.save()

    meta={
        "type":"ChArUco",
        "dictionary":"DICT_5X5_100",
        "squares_x":squares_x,"squares_y":squares_y,
        "square_length_mm":square_mm,"marker_length_mm":marker_mm,
        "physical_width_mm":board_w,"physical_height_mm":board_h,
    }
    (OUT/"charuco_board_definition.json").write_text(json.dumps(meta,indent=2))


def write_tag_map():
    layout = json.loads((ROOT / "config" / "workcell_layout.json").read_text(encoding="utf-8"))
    frame_origins = layout["tags"]
    frame_size = float(json.loads(
        (ROOT / "config" / "parameters.json").read_text(encoding="utf-8")
    )["tag_frame_size"])
    tag_map={
        "family":TAG_FAMILY,
        "detection_edge_mm":TAG_DETECTION_MM,
        "tile_size_mm":TAG_TILE_MM,
        "frame_size_mm":frame_size,
        "board_axes":{"+x":"right","+y":"rear/toward arm","+z":"up"},
        "paper_top_edge_faces":"+Y / board rear for every tag",
        "tags":{
            name:{
                "id":tag_id,
                "frame_origin_xy_mm":frame_origins[name],
                "detection_center_xy_mm":[frame_origins[name][0]+frame_size/2, frame_origins[name][1]+frame_size/2],
                "expected_yaw_deg_in_board_frame":0.0,
            }
            for name,tag_id in {"T0":0,"T1":1,"T2":2,"T3":3,"K0":4,"P0":5}.items()
        },
        "ids":{"T0":0,"T1":1,"T2":2,"T3":3,"K0":4,"P0":5},
        "note":"Configure tag size as the measured 40 mm detection edge (0.040 m). Before cutting, mark each tile's page-top edge on the back; install every marked edge toward board +Y/rear."
    }
    (OUT/"apriltag_map.json").write_text(json.dumps(tag_map,indent=2))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--map-only", action="store_true",
                        help="Regenerate only apriltag_map.json from the current workcell layout")
    args = parser.parse_args()
    if not args.map_only:
        # Keep map-only regeneration independent of the optional OpenCV image
        # stack, which may use a different NumPy ABI than the CAD environment.
        global cv2, np, Image, letter, mm, canvas, svgwrite
        import cv2
        import numpy as np
        from PIL import Image
        from reportlab.lib.pagesizes import letter
        from reportlab.lib.units import mm
        from reportlab.pdfgen import canvas
        import svgwrite
        for tag_id in TAG_IDS:
            write_tag_svg(tag_id,OUT/f"tag36h11_id{tag_id:02d}_tile55_marker40.svg")
            write_tag_png(tag_id,OUT/f"tag36h11_id{tag_id:02d}_tile55_marker40.png")
        write_tag_sheet_pdf(); write_tag_sheet_svg(); write_charuco()
    write_tag_map()
    print("generated fiducials")

if __name__=="__main__":
    main()
