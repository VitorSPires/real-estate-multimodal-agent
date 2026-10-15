"""Matplotlib renderers: floor plans, fake 'photos' for brochures, and the price chart."""

from io import BytesIO
from pathlib import Path

import matplotlib

matplotlib.use("Agg")  # no GUI, files only

import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
from matplotlib.patches import Rectangle  # noqa: E402
from matplotlib.ticker import StrMethodFormatter  # noqa: E402

from dataset.spec import Listing, Room  # noqa: E402

WALL = "#222222"


def render_floor_plan(listing: Listing, path: Path) -> None:
    """Architectural-style plan: walls, abbreviated labels, dimensions, furniture symbols.

    Labels use real-estate shorthand (MBR, BR, WC, KIT) on purpose, so reading the plan takes
    interpretation, not just OCR.
    """
    width = max(r.x + r.w for r in listing.rooms)
    height = max(r.y + r.h for r in listing.rooms)

    fig, ax = plt.subplots(figsize=(width * 0.9 + 1, height * 0.9 + 1.6), dpi=130)
    for room in listing.rooms:
        _draw_room(ax, room)

    ax.set_title(
        f"{listing.title.upper()}  ·  FLOOR PLAN  ·  {listing.area_m2} m²",
        fontsize=11, fontweight="bold", loc="left", pad=12,
    )
    _draw_scale_bar(ax, y=-0.7)
    ax.set_xlim(-0.4, width + 0.4)
    ax.set_ylim(-1.1, height + 0.3)
    ax.set_aspect("equal")
    ax.axis("off")
    fig.savefig(path, bbox_inches="tight", facecolor="white")
    plt.close(fig)


def _draw_room(ax, room: Room) -> None:
    ax.add_patch(Rectangle((room.x, room.y), room.w, room.h, fill=False, lw=3, ec=WALL))
    cx, cy = room.x + room.w / 2, room.y + room.h / 2

    if "bed" in room.furniture:
        # Wide room: bed against the right wall, labels centered in what's left.
        # Narrow room: bed against the bottom wall, labels near the top.
        if room.w >= 3.8:
            _draw_bed(ax, room.x + room.w - 1.75, cy - 0.8)
            cx = room.x + (room.w - 1.9) / 2
        else:
            _draw_bed(ax, cx - 0.7, room.y + 0.15)
            cy = room.y + room.h - 0.75

    ax.text(cx, cy + 0.25, room.label, ha="center", va="center", fontsize=8.5, fontweight="bold")
    ax.text(cx, cy - 0.15, f"{room.w:.1f} x {room.h:.1f}", ha="center", va="center", fontsize=7, color="#555")
    if "desk" in room.furniture:
        ax.add_patch(Rectangle((room.x + 0.2, room.y + 0.2), 1.4, 0.6, fill=False, lw=1, ec="#777"))
    if "bbq" in room.furniture:
        gx, gy = room.x + room.w - 1.1, room.y + 0.3
        ax.add_patch(Rectangle((gx, gy), 0.8, 0.8, fill=True, fc="#eee", lw=1, ec="#555"))
        ax.text(gx + 0.4, gy + 0.4, "BBQ", ha="center", va="center", fontsize=6.5)


def _draw_bed(ax, x: float, y: float) -> None:
    """Double bed (1.4 x 1.6 m) with two pillows at the head, bottom-left corner at (x, y)."""
    ax.add_patch(Rectangle((x, y), 1.4, 1.6, fill=False, lw=1, ec="#777"))
    for px in (x + 0.12, x + 0.75):
        ax.add_patch(Rectangle((px, y + 1.2), 0.53, 0.3, fill=False, lw=0.8, ec="#777"))


def _draw_scale_bar(ax, y: float) -> None:
    ax.plot([0, 2], [y, y], color=WALL, lw=2)
    ax.text(1, y - 0.3, "2 m", ha="center", va="center", fontsize=7)


def render_hero_photo(listing: Listing) -> BytesIO:
    """A stylized 'photo' of a building: sky gradient + facade with lit windows. Seeded per listing.

    Returned in memory: it only exists to be embedded in the brochure PDF.
    """
    rng = np.random.default_rng(listing.seed)
    fig, ax = plt.subplots(figsize=(6, 3.4), dpi=110)

    sky_top, sky_bottom = rng.uniform(0.35, 0.6), rng.uniform(0.75, 0.95)
    gradient = np.linspace(sky_top, sky_bottom, 100).reshape(-1, 1)
    ax.imshow(gradient, extent=(0, 10, 0, 6), cmap="Blues_r", aspect="auto", vmin=0, vmax=1)

    for left in np.arange(0.3, 10, rng.uniform(2.2, 3.2)):
        floors = int(rng.integers(5, 12))
        tone = rng.uniform(0.35, 0.65)
        ax.add_patch(Rectangle((left, 0), 2.0, floors * 0.45, color=(tone, tone * 0.95, tone * 0.9)))
        for floor in range(floors):
            for col in range(3):
                lit = rng.random() > 0.55
                ax.add_patch(Rectangle(
                    (left + 0.25 + col * 0.6, 0.15 + floor * 0.45), 0.3, 0.22,
                    color="#f6d77a" if lit else "#3b4a5a",
                ))

    ax.set_xlim(0, 10)
    ax.set_ylim(0, 6)
    ax.axis("off")
    image = BytesIO()
    fig.savefig(image, format="jpg", bbox_inches="tight", pad_inches=0, pil_kwargs={"quality": 85})
    plt.close(fig)
    return image


def render_price_chart(listing: Listing) -> BytesIO:
    """Neighborhood price-per-m² trend. Points are NOT annotated: reading values is the task."""
    years = [year for year, _ in listing.price_trend]
    values = [value for _, value in listing.price_trend]

    fig, ax = plt.subplots(figsize=(5.5, 3), dpi=130)
    ax.plot(years, values, marker="o", lw=2, color="#1f5f99")
    ax.set_title(f"{listing.neighborhood}: average price per m² (USD)", fontsize=10, loc="left")
    ax.set_xticks(years)
    ax.set_ylim(min(values) - 400, max(values) + 400)
    ax.yaxis.set_major_formatter(StrMethodFormatter("{x:,.0f}"))
    ax.grid(axis="y", alpha=0.3)
    ax.spines[["top", "right"]].set_visible(False)
    image = BytesIO()
    fig.savefig(image, format="png", bbox_inches="tight", facecolor="white")
    plt.close(fig)
    return image
