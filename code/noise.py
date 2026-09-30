import glob
import os
import pandas as pd
import xarray as xr
import geopandas as gpd
import regionmask

data_dir = "/glade/derecho/scratch/zacharys/MODISA_L3m_CHL_2022.0-20260930_155709"
outdir = "/glade/u/home/zacharys/HAB_Prediction/results"
shapefile = "/glade/derecho/scratch/zacharys/bay_shapefile/P7TidalShorelineDec23.shp"

os.makedirs(outdir, exist_ok=True)

# Load Chesapeake Bay polygon
bay = gpd.read_file(shapefile).to_crs("EPSG:4326")

files = sorted(glob.glob(
    f"{data_dir}/AQUA_MODIS.2016*.L3m.DAY.CHL.chlor_a.4km.nc"
))

results = []

for file in files:

    filename = os.path.basename(file)
    date = pd.to_datetime(filename.split(".")[1], format="%Y%m%d")

    with xr.open_dataset(file) as ds:

        chl = ds["chlor_a"].sel(
            lat=slice(39.620046, 36.719954),
            lon=slice(-77.430046, -75.609954)
        )

        # Chesapeake Bay mask
        mask = regionmask.mask_geopandas(
            bay,
            chl.lon,
            chl.lat
        )

        # Keep only pixels inside Chesapeake Bay
        chl_bay = chl.where(mask.notnull())

        # Mean chlorophyll over observed Bay pixels
        mean_chl = chl_bay.mean(skipna=True).item()

        # Coverage = observed Bay pixels / total Bay pixels
        bay_pixels = mask.notnull()
        valid_pixels = chl_bay.notnull().sum().item()
        total_bay_pixels = bay_pixels.sum().item()

        coverage = (valid_pixels / total_bay_pixels) * 100

    results.append({
        "Date": date,
        "Mean_Chlorophyll": mean_chl,
        "Coverage_Percent": coverage
    })

df = pd.DataFrame(results)

df.to_csv(
    os.path.join(outdir, "MODIS_chlorophyll_coverage_2016.csv"),
    index=False
)