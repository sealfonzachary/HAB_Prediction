import glob
import xarray as xr
import matplotlib.pyplot as plt
import os
import geopandas as gpd
import regionmask

data_dir = "/glade/derecho/scratch/zacharys/MODISA_L3m_CHL_2022.0-20260930_155709"
outdir = "/glade/u/home/zacharys/HAB_Prediction/results/exploratory_plots"
shapefile = "/glade/derecho/scratch/zacharys/bay_shapefile/P7TidalShorelineDec23.shp"

os.makedirs(outdir, exist_ok=True)

files = sorted(glob.glob(f"{data_dir}/*4km.nc"))

# Read Chesapeake Bay shapefile
bay = gpd.read_file(shapefile)
bay = bay.to_crs("EPSG:4326")

with xr.open_dataset(files[0]) as ds:

    chl = ds["chlor_a"]

    # First restrict to Chesapeake region
    chl_box = chl.sel(
        lat=slice(40.0, 36.0),
        lon=slice(-78.0, -74.0)
    )

    # Create Chesapeake Bay shapefile mask
    mask = regionmask.mask_geopandas(
        bay,
        chl_box.lon,
        chl_box.lat
    )

    # Keep only pixels inside the shapefile
    chl_bay = chl_box.where(mask.notnull())

    print("Min:", chl_bay.min().values)
    print("Max:", chl_bay.max().values)
    print("Mean:", chl_bay.mean().values)

    # Get filename for title
    filename = os.path.basename(files[0])

    plt.figure(figsize=(10, 8))

    chl_bay.plot(
        cmap="viridis",
        vmin=0,
        vmax=20,
        cbar_kwargs={"label": "Chlorophyll-a (mg m$^{-3}$)"}
    )

    plt.title(f"MODIS-Aqua Chlorophyll-a\n{filename}")
    plt.xlabel("Longitude")
    plt.ylabel("Latitude")

    plt.savefig(
        os.path.join(outdir, "first_plot_masked.png"),
        dpi=300,
        bbox_inches="tight"
    )

    plt.close()