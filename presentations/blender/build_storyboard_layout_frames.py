"""Build layout-accurate storyboard frames from the authoritative Blender render.

These are communication mockups, not engineering evidence.  The underlying
keyboard, phone, station, robot, board, and fiducial placements come directly
from the production Blender scene; this script adds only crops and graphics.
"""

from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageDraw, ImageEnhance, ImageFilter, ImageFont


ROOT = Path(__file__).resolve().parent
OUT = ROOT / "storyboard_v2"
SOURCE = OUT / "source" / "workcell-layout-authoritative.jpg"
SIZE = (1920, 1080)

INK = (242, 246, 250, 255)
MUTED = (176, 188, 202, 255)
CYAN = (52, 195, 255, 255)
AMBER = (255, 178, 64, 255)
RED = (255, 83, 83, 255)
GREEN = (68, 220, 143, 255)
PANEL = (8, 15, 25, 224)
PANEL_SOFT = (8, 15, 25, 184)


def font(size: int, bold: bool = False, mono: bool = False) -> ImageFont.FreeTypeFont:
    windows = Path("C:/Windows/Fonts")
    if mono:
        name = "consolab.ttf" if bold else "consola.ttf"
    else:
        name = "segoeuib.ttf" if bold else "segoeui.ttf"
    return ImageFont.truetype(str(windows / name), size=size)


def base(exposure: float = 0.78) -> Image.Image:
    image = Image.open(SOURCE).convert("RGB").resize(SIZE, Image.Resampling.LANCZOS)
    image = ImageEnhance.Brightness(image).enhance(exposure)
    return image.convert("RGBA")


def cover_legacy_labels(image: Image.Image, *, footer_text: str = "SIMULATED WORKCELL SEQUENCE") -> None:
    """Cover text baked into the source QA render without altering hardware."""
    draw = ImageDraw.Draw(image, "RGBA")
    draw.rounded_rectangle((708, 77, 1214, 119), radius=8, fill=(5, 9, 15, 232))
    draw.text((961, 98), "RC03 · MEASURED WORKCELL", font=font(19, True, True),
              fill=CYAN, anchor="mm")
    draw.rectangle((565, 1000, 1365, 1068), fill=(5, 9, 15, 226))
    draw.text((965, 1034), footer_text, font=font(19, True, True), fill=MUTED,
              anchor="mm")


def phone_messages_ui(draw: ImageDraw.ImageDraw, *, sent: bool = False,
                      draft: str | None = None) -> None:
    """Place a conceptual Messages state inside the measured phone screen."""
    draw.rounded_rectangle((1374, 508, 1509, 829), radius=10,
                           fill=(12, 20, 30, 246), outline=(86, 104, 124, 255), width=2)
    draw.text((1441, 535), "MESSAGES", font=font(14, True, True), fill=INK, anchor="mm")
    draw.line((1388, 558, 1495, 558), fill=(74, 91, 109, 255), width=2)
    if sent:
        draw.rounded_rectangle((1393, 594, 1494, 650), radius=14, fill=(40, 111, 245, 255))
        draw.multiline_text((1405, 606), "on my\nway", font=font(16, True), fill=INK,
                            spacing=2)
        draw.text((1490, 657), "sent", font=font(10, True, True), fill=GREEN, anchor="ra")
    else:
        draw.rounded_rectangle((1390, 747, 1493, 782), radius=13,
                               fill=(30, 42, 56, 255), outline=(92, 109, 127, 255), width=1)
        draw.text((1400, 757), draft or "Message", font=font(11, bold=bool(draft)),
                  fill=INK if draft else MUTED)
        draw.ellipse((1466, 749, 1490, 773), fill=CYAN)
        draw.text((1478, 761), ">", font=font(14, True, True), fill=(5, 9, 15, 255), anchor="mm")


def rounded(draw: ImageDraw.ImageDraw, box: tuple[int, int, int, int], *,
            fill=PANEL, outline=None, radius=18, width=2) -> None:
    draw.rounded_rectangle(box, radius=radius, fill=fill, outline=outline, width=width)


def header(image: Image.Image, stage: str, title: str, accent=CYAN) -> ImageDraw.ImageDraw:
    draw = ImageDraw.Draw(image, "RGBA")
    draw.rectangle((0, 0, 1920, 74), fill=(5, 9, 15, 238))
    draw.text((42, 18), stage, font=font(25, True, True), fill=accent)
    draw.text((300, 15), title, font=font(34, True), fill=INK)
    draw.text((1535, 22), "GEOMETRY REFERENCE", font=font(18, True, True), fill=MUTED)
    draw.rectangle((0, 1070, 1920, 1080), fill=accent)
    return draw


def save(image: Image.Image, name: str) -> None:
    image.convert("RGB").save(
        OUT / name,
        quality=84,
        optimize=True,
        progressive=True,
        subsampling=2,
    )


def marker(draw: ImageDraw.ImageDraw, xy: tuple[int, int], label: str,
           color=AMBER, radius: int = 18) -> None:
    x, y = xy
    draw.ellipse((x - radius, y - radius, x + radius, y + radius),
                 fill=(5, 9, 15, 220), outline=color, width=4)
    draw.ellipse((x - 4, y - 4, x + 4, y + 4), fill=color)
    draw.text((x + radius + 8, y - 14), label, font=font(20, True, True), fill=color)


def frame_01() -> None:
    image = base(0.72)
    cover_legacy_labels(image)
    draw = header(image, "00 · REQUEST", "ONE INTENT, TWO PHYSICAL INTERFACES", AMBER)
    phone_messages_ui(draw, sent=False)
    rounded(draw, (32, 122, 326, 500), fill=PANEL, outline=AMBER)
    draw.text((56, 148), "USER REQUEST", font=font(20, True, True), fill=AMBER)
    draw.multiline_text((56, 202), "Type ready\nin the local test pad.\n\nThen send\non my way\nfrom the phone.",
                        font=font(26, True), fill=INK, spacing=7)
    draw.text((56, 458), "No motor command yet", font=font(17, False, True), fill=MUTED)
    rounded(draw, (1600, 160, 1882, 328), fill=PANEL_SOFT, outline=CYAN)
    draw.text((1624, 187), "FIXED WORKCELL", font=font(20, True, True), fill=CYAN)
    draw.text((1624, 232), "Keyboard · local input\nPhone · separate touch UI\nRobot · rear-center",
              font=font(18), fill=INK, spacing=9)
    save(image, "01-intent-hero-layout-accurate.jpg")


def frame_02() -> None:
    image = base(0.68)
    cover_legacy_labels(image, footer_text="MEASURED RC03 ASSET LAYOUT")
    draw = header(image, "02 · LOCATE", "MEASURED BOARD AND DEVICE PLACEMENTS", CYAN)
    # Pixel bounds are derived from the authoritative 610 x 457 mm board render.
    draw.rounded_rectangle((490, 455, 1168, 870), radius=16, outline=CYAN, width=5)
    draw.rounded_rectangle((1332, 410, 1536, 866), radius=16, outline=CYAN, width=5)
    rounded(draw, (32, 126, 324, 310), fill=PANEL, outline=CYAN)
    draw.text((56, 151), "BOARD FRAME", font=font(20, True, True), fill=CYAN)
    draw.text((56, 196), "610 × 457 mm\norigin · front-left\nrobot · rear-center",
              font=font(23, True), fill=INK, spacing=8)
    rounded(draw, (32, 338, 324, 524), fill=PANEL_SOFT, outline=CYAN)
    draw.text((56, 365), "KEYBOARD", font=font(20, True, True), fill=CYAN)
    draw.text((56, 410), "315 × 147 × 21 mm\norigin · 85, 85 mm", font=font(22), fill=INK, spacing=8)
    rounded(draw, (1594, 362, 1887, 552), fill=PANEL_SOFT, outline=CYAN)
    draw.text((1618, 389), "PHONE", font=font(20, True, True), fill=CYAN)
    draw.text((1618, 434), "77.9 × 164.4 × 7.9 mm\norigin · 499.2, 84.2 mm",
              font=font(20), fill=INK, spacing=8)
    draw.line((335, 185, 490, 455), fill=CYAN, width=3)
    draw.line((1586, 455, 1536, 550), fill=CYAN, width=3)
    draw.text((742, 1014), "SAME BOARD · SAME ASSETS · SAME TRANSFORMS IN EVERY SHOT",
              font=font(22, True, True), fill=INK, anchor="mm")
    save(image, "02-device-maps-layout-accurate.jpg")


def frame_03() -> None:
    image = base(0.64)
    cover_legacy_labels(image, footer_text="NO ADMITTED ROUTE · NO MOTION")
    draw = header(image, "03 · CHECK", "STALE EVIDENCE FAILS CLOSED", RED)
    rounded(draw, (32, 160, 405, 420), fill=PANEL, outline=RED)
    draw.text((58, 190), "SCENE CHECK", font=font(21, True, True), fill=RED)
    draw.text((58, 242), "capture age     41 s\nallowed age      2 s",
              font=font(24, True, True), fill=INK, spacing=10)
    draw.line((58, 324, 375, 324), fill=(95, 110, 126, 255), width=2)
    draw.text((58, 347), "REJECTED · NO MOTION", font=font(25, True, True), fill=RED)
    draw.rounded_rectangle((490, 455, 1168, 870), radius=16, outline=(84, 105, 126, 255), width=3)
    draw.rounded_rectangle((1332, 410, 1536, 866), radius=16, outline=(84, 105, 126, 255), width=3)
    draw.text((1595, 925), "ARM REMAINS STATIONARY", font=font(21, True, True), fill=MUTED)
    save(image, "03-stale-evidence-reject-layout-accurate.jpg")


def frame_04() -> None:
    # Crop only the authoritative render; no asset is regenerated.
    source = base(0.82).crop((400, 350, 1240, 935)).resize(SIZE, Image.Resampling.LANCZOS)
    image = source.convert("RGBA")
    draw = header(image, "04 · ACT", "PHYSICAL KEYBOARD → LOCAL INTERFACE", GREEN)
    # Original-board pixel targets, transformed through crop and resize.
    def tx(x: float, y: float) -> tuple[int, int]:
        return (round((x - 400) * 1920 / 840), round((y - 350) * 1080 / 585))

    # Board mapping from measured key centers in build_workcell_explainer.py.
    board_left, board_front_y = 345.0, 1000.0
    px_per_mm_x, px_per_mm_y = 1230.0 / 610.0, 920.0 / 457.0
    centers_mm = {
        "R": (173.65, 175.0),
        "E": (154.60, 175.0),
        "A": (121.30, 154.0),
        "D": (159.40, 154.0),
        "Y": (211.75, 175.0),
    }
    points: list[tuple[int, int]] = []
    for label, (bx, by) in centers_mm.items():
        p = tx(board_left + bx * px_per_mm_x, board_front_y - by * px_per_mm_y)
        points.append(p)
        marker(draw, p, label, GREEN, 20)
    draw.line(points, fill=GREEN, width=5, joint="curve")
    rounded(draw, (1420, 140, 1886, 310), fill=PANEL, outline=GREEN)
    draw.text((1450, 168), "LOCAL RESULT", font=font(21, True, True), fill=GREEN)
    draw.text((1450, 218), "ready · confirmed", font=font(32, True, True), fill=INK)
    draw.text((1450, 274), "Phone remains unchanged", font=font(18, False, True), fill=MUTED)
    save(image, "04-local-keyboard-action-layout-accurate.jpg")


def frame_05() -> None:
    image = base(0.68)
    cover_legacy_labels(image, footer_text="PHYSICAL TOUCHSCREEN WORKFLOW")
    draw = header(image, "04 · ACT", "PHONE IS A SEPARATE PHYSICAL INTERFACE", AMBER)
    phone_messages_ui(draw, draft="on my way")
    draw.rounded_rectangle((1332, 410, 1536, 866), radius=16, outline=AMBER, width=5)
    marker(draw, (1480, 761), "SEND", GREEN, 15)
    rounded(draw, (32, 150, 365, 342), fill=PANEL, outline=GREEN)
    draw.text((58, 177), "LOCAL WORKFLOW", font=font(20, True, True), fill=GREEN)
    draw.text((58, 224), "ready · confirmed", font=font(27, True, True), fill=INK)
    draw.text((58, 283), "remains unchanged", font=font(20, False, True), fill=MUTED)
    rounded(draw, (1570, 150, 1888, 342), fill=PANEL, outline=AMBER)
    draw.text((1596, 177), "PHONE WORKFLOW", font=font(20, True, True), fill=AMBER)
    draw.multiline_text((1596, 224), "on my way\nready to send", font=font(25, True),
                        fill=INK, spacing=7)
    save(image, "05-phone-action-layout-accurate.jpg")


def frame_06() -> None:
    image = base(0.68)
    cover_legacy_labels(image, footer_text="TWO INDEPENDENT VERIFICATION RECEIPTS")
    draw = header(image, "05 · VERIFY", "TWO RESULTS, VERIFIED INDEPENDENTLY", GREEN)
    phone_messages_ui(draw, sent=True)
    draw.rounded_rectangle((1332, 410, 1536, 866), radius=16, outline=GREEN, width=5)
    rounded(draw, (32, 150, 365, 342), fill=PANEL, outline=GREEN)
    draw.text((58, 177), "LOCAL RECEIPT", font=font(20, True, True), fill=GREEN)
    draw.text((58, 224), "ready · confirmed", font=font(27, True, True), fill=INK)
    draw.text((58, 283), "physical keyboard", font=font(20, False, True), fill=MUTED)
    rounded(draw, (1570, 150, 1888, 366), fill=PANEL, outline=GREEN)
    draw.text((1596, 177), "PHONE RECEIPT", font=font(20, True, True), fill=GREEN)
    draw.multiline_text((1596, 224), "on my way\nsent", font=font(31, True), fill=INK, spacing=7)
    draw.text((1596, 318), "touchscreen taps", font=font(18, False, True), fill=MUTED)
    save(image, "06-dual-verification-layout-accurate.jpg")


def main() -> None:
    if not SOURCE.exists():
        raise SystemExit(f"Missing authoritative source render: {SOURCE}")
    frame_01()
    frame_02()
    frame_03()
    frame_04()
    frame_05()
    frame_06()


if __name__ == "__main__":
    main()
