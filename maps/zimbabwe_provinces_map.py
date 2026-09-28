"""Map of Zimbabwe highlighting selected provinces.

Boundaries: geoBoundaries gbOpen ZWE ADM1 (simplified), CC BY 4.0.
Run: python3 maps/zimbabwe_provinces_map.py  (expects zw_adm1.geojson next to this file)
"""
import json
from pathlib import Path

import matplotlib.pyplot as plt
from matplotlib.patches import Polygon as MplPolygon
from shapely.geometry import shape

HERE = Path(__file__).parent
features = json.load(open(HERE / "zw_adm1.geojson"))["features"]

HIGHLIGHT = {
    "Harare": "#d62728",
    "Bulawayo": "#9467bd",
    "Masvingo": "#ff7f0e",
    "Mashonaland Central": "#2ca02c",
    "Matabeleland North": "#1f77b4",
    "Matabeleland South": "#17becf",
}
OTHER = "#e6e6e6"
# Label offsets (lon, lat) for the two small metropolitan provinces
CALLOUT = {"Harare": (1.6, 0.6), "Bulawayo": (-1.9, 0.2)}

fig, ax = plt.subplots(figsize=(10, 9))
for f in features:
    name = f["properties"]["shapeName"]
    geom = shape(f["geometry"])
    polys = geom.geoms if geom.geom_type == "MultiPolygon" else [geom]
    color = HIGHLIGHT.get(name, OTHER)
    for p in polys:
        ax.add_patch(MplPolygon(list(p.exterior.coords), closed=True,
                                facecolor=color, edgecolor="white", linewidth=1.2,
                                alpha=0.9 if name in HIGHLIGHT else 1))
    pt = geom.representative_point()
    if name in CALLOUT:
        dx, dy = CALLOUT[name]
        ax.annotate(f"{name} Province", xy=(pt.x, pt.y), xytext=(pt.x + dx, pt.y + dy),
                    ha="center", fontsize=11, fontweight="bold",
                    arrowprops=dict(arrowstyle="-", color="#333", lw=1),
                    bbox=dict(boxstyle="round,pad=0.3", fc="white", ec=color))
    elif name in HIGHLIGHT:
        ax.text(pt.x, pt.y, f"{name}\nProvince", ha="center", va="center",
                fontsize=11, fontweight="bold", color="black",
                bbox=dict(boxstyle="round,pad=0.25", fc="white", ec="none", alpha=0.75))
    else:
        if name == "Mashonaland East":  # keep clear of Harare
            pt = type(pt)(pt.x + 0.3, pt.y - 0.5)
        ax.text(pt.x, pt.y, name, ha="center", va="center", fontsize=9,
                color="#777", style="italic")

ax.autoscale_view()
ax.set_aspect(1 / 0.92)  # approx. cos(latitude) correction for ~19°S
ax.set_title("Zimbabwe – Selected Provinces", fontsize=16, fontweight="bold")
ax.set_xlabel("Longitude (°E)")
ax.set_ylabel("Latitude (°S)")
ax.text(0.01, 0.01, "Grey = other provinces\n"
        "Boundaries: geoBoundaries (CC BY 4.0)", transform=ax.transAxes,
        fontsize=8, color="#555", va="bottom")
ax.grid(alpha=0.2)
plt.tight_layout()
for ext in ("png", "pdf"):
    plt.savefig(HERE / f"zimbabwe_provinces_map.{ext}", dpi=300)
