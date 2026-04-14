"""
Generate neutral placeholder logos for the portfolio repo.

Produces:
- admin/public/logo-full.png      — wide wordmark (1400x420)
- admin/public/logo-icon.jpeg     — square icon (512x512)
- admin/src/assets/logo-icon.jpeg — same as above (duplicated for Vite import)
"""

from pathlib import Path
from PIL import Image, ImageDraw, ImageFont


ROOT = Path(__file__).resolve().parent.parent
PUBLIC = ROOT / "admin" / "public"
ASSETS = ROOT / "admin" / "src" / "assets"

BG = (15, 23, 42)        # slate-900
FG = (226, 232, 240)     # slate-200
ACCENT = (99, 102, 241)  # indigo-500


def _load_font(size: int) -> ImageFont.FreeTypeFont:
    candidates = [
        "C:/Windows/Fonts/segoeuib.ttf",
        "C:/Windows/Fonts/arialbd.ttf",
        "C:/Windows/Fonts/arial.ttf",
    ]
    for path in candidates:
        if Path(path).exists():
            return ImageFont.truetype(path, size)
    return ImageFont.load_default()


def build_icon(path: Path, size: int = 512) -> None:
    img = Image.new("RGB", (size, size), BG)
    draw = ImageDraw.Draw(img)

    pad = size // 10
    draw.rounded_rectangle(
        (pad, pad, size - pad, size - pad),
        radius=size // 8,
        outline=ACCENT,
        width=size // 40,
    )

    font = _load_font(size // 2)
    text = "AB"
    bbox = draw.textbbox((0, 0), text, font=font)
    tw, th = bbox[2] - bbox[0], bbox[3] - bbox[1]
    draw.text(
        ((size - tw) / 2 - bbox[0], (size - th) / 2 - bbox[1] - size // 40),
        text,
        font=font,
        fill=FG,
    )

    img.save(path, "JPEG", quality=92)


def build_wordmark(path: Path, w: int = 1400, h: int = 420) -> None:
    img = Image.new("RGB", (w, h), BG)
    draw = ImageDraw.Draw(img)

    icon_size = int(h * 0.62)
    icon_x = int(h * 0.25)
    icon_y = (h - icon_size) // 2
    draw.rounded_rectangle(
        (icon_x, icon_y, icon_x + icon_size, icon_y + icon_size),
        radius=icon_size // 7,
        outline=ACCENT,
        width=icon_size // 30,
    )
    ifont = _load_font(int(icon_size * 0.55))
    ibbox = draw.textbbox((0, 0), "AB", font=ifont)
    itw, ith = ibbox[2] - ibbox[0], ibbox[3] - ibbox[1]
    draw.text(
        (
            icon_x + (icon_size - itw) / 2 - ibbox[0],
            icon_y + (icon_size - ith) / 2 - ibbox[1] - icon_size // 30,
        ),
        "AB",
        font=ifont,
        fill=FG,
    )

    text = "AgencyBot"
    tfont = _load_font(int(h * 0.42))
    tbbox = draw.textbbox((0, 0), text, font=tfont)
    tw, th = tbbox[2] - tbbox[0], tbbox[3] - tbbox[1]
    tx = icon_x + icon_size + int(h * 0.22)
    ty = (h - th) / 2 - tbbox[1]
    draw.text((tx, ty), text, font=tfont, fill=FG)

    img.save(path, "PNG", optimize=True)


def main() -> None:
    PUBLIC.mkdir(parents=True, exist_ok=True)
    ASSETS.mkdir(parents=True, exist_ok=True)
    build_wordmark(PUBLIC / "logo-full.png")
    build_icon(PUBLIC / "logo-icon.jpeg")
    build_icon(ASSETS / "logo-icon.jpeg")
    print("Generated:")
    for p in (PUBLIC / "logo-full.png", PUBLIC / "logo-icon.jpeg", ASSETS / "logo-icon.jpeg"):
        print(f"  {p}  ({p.stat().st_size} bytes)")


if __name__ == "__main__":
    main()
