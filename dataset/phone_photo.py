"""A printed price sheet, 'photographed' with a phone: no text layer, tilted, shadowed, blurry.

Built in two steps so each is easy to read: draw a clean page, then degrade it like a photo.
"""

from pathlib import Path

import matplotlib
import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageFont

from dataset.spec import Listing

_FONT_DIR = Path(matplotlib.get_data_path()) / "fonts" / "ttf"  # bundled, works on any OS
PAGE_SIZE = (1240, 1754)  # A4 at 150 dpi


def render_price_sheet_photo(listing: Listing, path: Path) -> None:
    page = _draw_price_sheet(listing)
    photo = _degrade_like_phone_photo(page, seed=listing.seed)
    photo.save(path, quality=72)


def _draw_price_sheet(listing: Listing) -> Image.Image:
    page = Image.new("RGB", PAGE_SIZE, "white")
    draw = ImageDraw.Draw(page)
    title = ImageFont.truetype(str(_FONT_DIR / "DejaVuSans-Bold.ttf"), 54)
    text = ImageFont.truetype(str(_FONT_DIR / "DejaVuSans.ttf"), 38)
    small = ImageFont.truetype(str(_FONT_DIR / "DejaVuSans.ttf"), 28)

    draw.text((110, 140), "PRICE SHEET", font=title, fill="black")
    draw.text((110, 220), f"{listing.title} · {listing.neighborhood}", font=text, fill="#444")

    rows = [
        ("List price", f"USD {listing.price_usd:,}"),
        ("Condo fee (monthly)", f"USD {listing.condo_fee_usd:,}"),
        ("Property tax (yearly)", f"USD {listing.property_tax_usd:,}"),
        ("Parking", f"{listing.parking_spots} spots included"),
        ("Down payment", "20% at signing"),
    ]
    y = 380
    for label, value in rows:
        draw.text((110, y), label, font=text, fill="black")
        draw.text((720, y), value, font=text, fill="black")
        draw.line((110, y + 62, 1130, y + 62), fill="#bbb", width=2)
        y += 110

    draw.text((110, y + 60), "Values valid for 30 days. Ask your broker for details.", font=small, fill="#666")
    return page


def _degrade_like_phone_photo(page: Image.Image, seed: int) -> Image.Image:
    rng = np.random.default_rng(seed)
    w, h = page.size

    # 1) Perspective: the phone wasn't parallel to the paper.
    a, b, c, d = rng.uniform(40, 110, size=4)
    corners = [(a, b), (w - c, 0), (w, h), (0, h - d)]
    page = page.transform(
        page.size, Image.Transform.PERSPECTIVE, _perspective_coeffs(corners, w, h),
        Image.Resampling.BICUBIC, fillcolor=(92, 74, 60),  # wooden table behind the paper
    )

    # 2) Uneven light: a soft shadow from the left.
    shade = np.linspace(0.62, 1.0, w).reshape(1, -1, 1)
    pixels = np.asarray(page).astype(float) * shade

    # 3) Sensor noise + slight blur.
    pixels += rng.normal(0, 7, pixels.shape)
    photo = Image.fromarray(np.clip(pixels, 0, 255).astype("uint8"))
    photo = photo.filter(ImageFilter.GaussianBlur(1.1)).rotate(-2.5, expand=False, fillcolor=(92, 74, 60))
    return photo.resize((w * 2 // 3, h * 2 // 3))


def _perspective_coeffs(src_corners: list[tuple[float, float]], w: int, h: int) -> list[float]:
    """Coefficients that map the output rectangle onto the given (distorted) corners."""
    dst = [(0, 0), (w, 0), (w, h), (0, h)]
    matrix, vector = [], []
    for (x, y), (u, v) in zip(dst, src_corners):
        matrix.append([x, y, 1, 0, 0, 0, -u * x, -u * y])
        matrix.append([0, 0, 0, x, y, 1, -v * x, -v * y])
        vector += [u, v]
    return np.linalg.solve(np.array(matrix, float), np.array(vector, float)).tolist()
