import glob
import os

import geopandas as gpd
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
import xarray as xr

data_dir = r"C:\Users\zseal\capstone\HAB_Prediction\data\MODIS"

geojson = r"C:\Users\zseal\capstone\HAB_Prediction\data\chesapeake_salinity_full.geojson"

outdir = r"C:\Users\zseal\capstone\HAB_Prediction\results"

os.makedirs(outdir, exist_ok=True)
files = sorted(
    glob.glob(
        os.path.join(data_dir, "*.nc")
    )
)

with xr.open_dataset(files[0]) as ds:

    filename = os.path.basename(files[0])

    chl = ds["chlor_a"]

    chl_box = chl.sel(
        lat=slice(40.0, 36.0),
        lon=slice(-78.0, -74.0)
    )

# ------------------------------------------------------------
# LOAD CHESAPEAKE SALINITY POLYGONS
# ------------------------------------------------------------

gdf = gpd.read_file(geojson)

gdf = gdf.set_crs(
    "EPSG:4326",
    allow_override=True
)

gdf["zone"] = gdf["SEGMENT"].str.extract(
    r"(TF|OH|MH|PH)"
)


zone_colors = {
    "TF": "#2166ac",    # blue
    "OH": "#4daf4a",    # green
    "MH": "#ff7f00",    # orange
    "PH": "#d73027"     # red
}

# ------------------------------------------------------------
# PLOT
# ------------------------------------------------------------

fig, ax = plt.subplots(
    figsize=(10, 12)
)

# MODIS chlorophyll background

chl_box.plot(
    ax=ax,
    cmap="viridis",
    vmin=0,
    vmax=20,
    cbar_kwargs={
        "label": "Chlorophyll-a (µg/L)"
    }
)

# colored salinity regions

for zone in ["TF", "OH", "MH", "PH"]:

    subset = gdf[gdf["zone"] == zone]

    subset.plot(
        ax=ax,
        color=zone_colors[zone],
        alpha=0.18,
        edgecolor="none"
    )

# boundaries

gdf.boundary.plot(
    ax=ax,
    color="black",
    linewidth=0.15,
    alpha=0.7
)

# labels

for zone in ["TF", "OH", "MH", "PH"]:

    subset = gdf[gdf["zone"] == zone]

    x = subset.geometry.centroid.x.mean()
    y = subset.geometry.centroid.y.mean()

    ax.text(
        x,
        y,
        zone,
        fontsize=15,
        weight="bold",
        color="white",
        ha="center",
        va="center",
        bbox=dict(
            facecolor="black",
            alpha=0.6,
            pad=2
        )
    )

# legend

handles = [
    mpatches.Patch(
        color=zone_colors[z],
        alpha=0.5,
        label=z
    )
    for z in ["TF", "OH", "MH", "PH"]
]

ax.legend(
    handles=handles,
    title="Salinity Zones",
    loc="lower left"
)

# Chesapeake extent

ax.set_xlim(-77.8, -75.0)
ax.set_ylim(36.7, 39.8)

ax.set_title(
    f"MODIS Aqua Chlorophyll-a with Chesapeake Salinity Regimes\n{filename}",
    fontsize=14
)

ax.set_xlabel("Longitude")
ax.set_ylabel("Latitude")

plt.tight_layout()

outfile = os.path.join(
    outdir,
    "chlorophyll_salinity_overlay.png"
)

plt.savefig(
    outfile,
    dpi=300,
    bbox_inches="tight"
)

plt.show()

print(f"\nSaved:\n{outfile}")