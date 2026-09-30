import glob
import os
import pandas as pd
import xarray as xr

data_dir = "/glade/derecho/scratch/zacharys/MODISA_L3m_CHL_2022.0-20260930_155709"
outdir = "/glade/u/home/zacharys/HAB_Prediction/results"

os.makedirs(outdir, exist_ok=True)

# Daily 4-km MODIS files for 2016
files = sorted(glob.glob(
    f"{data_dir}/AQUA_MODIS.2016*.L3m.DAY.CHL.chlor_a.4km.nc"
))

results = []

for file in files:

    # Extract YYYYMMDD from filename
    filename = os.path.basename(file)
    date_str = filename.split(".")[1]
    date = pd.to_datetime(date_str, format="%Y%m%d")

    with xr.open_dataset(file) as ds:

        # Chesapeake Bay bounding region
        chl_box = ds["chlor_a"].sel(
            lat=slice(39.620046, 36.719954),
            lon=slice(-77.430046, -75.609954)
        )

        # Mean of available chlorophyll pixels
        mean_chl = chl_box.mean(skipna=True).item()

        # Percent of pixels with valid observations
        valid_pixels = chl_box.notnull().sum().item()
        total_pixels = chl_box.size
        coverage = (valid_pixels / total_pixels) * 100

    results.append({
        "Date": date,
        "Mean_Chlorophyll": mean_chl,
        "Coverage_Percent": coverage
    })


df = pd.DataFrame(results)

df.to_csv(
    os.path.join(outdir, "MODIS_chlorophyll_2016.csv"),
    index=False
)

