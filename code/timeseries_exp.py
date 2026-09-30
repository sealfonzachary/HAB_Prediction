import glob
import os
import pandas as pd
import xarray as xr
import matplotlib.pyplot as plt

data_dir = "/glade/derecho/scratch/zacharys/MODISA_L3m_CHL_2022.0-20260930_155709"
outdir = "/glade/u/home/zacharys/HAB_Prediction/results/exploratory_plots"

os.makedirs(outdir, exist_ok=True)

# Get daily 4-km files from 2016
files = sorted(glob.glob(
    f"{data_dir}/AQUA_MODIS.2016*.L3m.DAY.CHL.chlor_a.9km.nc"
))

dates = []
mean_chl = []

for file in files:

    # Get date from filename
    filename = os.path.basename(file)
    date_str = filename.split(".")[1]
    date = pd.to_datetime(date_str, format="%Y%m%d")

    with xr.open_dataset(file) as ds:
#[South, West, North, East]: [36.719954, -77.430046, 39.620046, -75.609954]
        chl_box = ds["chlor_a"].sel(
            lat=slice(39.620046, 36.719954),
            lon=slice(-77.430046, -75.609954)
        )

        mean = chl_box.mean(skipna=True).item()

    dates.append(date)
    mean_chl.append(mean)


# Plot
plt.figure(figsize=(12, 6))

plt.plot(dates, mean_chl)

plt.xlabel("Date")
plt.ylabel("Mean Chlorophyll-a (mg/m^3)")
plt.title("Daily MODIS-Aqua Chlorophyll-a, 2016")
plt.grid(alpha=0.3)

plt.savefig(
    os.path.join(outdir, "chlorophyll_timeseries_2016_9km.png"),
    dpi=300,
    bbox_inches="tight"
)

plt.close()