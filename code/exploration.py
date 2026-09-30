#MODISA_L3m_CHL_2022.0-20260930_155709
import glob
import xarray as xr
import matplotlib.pyplot as plt
import os

data_dir = "/glade/derecho/scratch/zacharys/MODISA_L3m_CHL_2022.0-20260930_155709"
outdir = "/glade/u/home/zacharys/HAB_Prediction/results/exploratory_plots"
os.makedirs(outdir, exist_ok=True)

files = sorted(glob.glob(f"{data_dir}/*4km.nc"))
with xr.open_dataset(files[0]) as ds:
    filename = os.path.basename(files[0])
    chl = ds["chlor_a"]

    chl_box = chl.sel(
        lat=slice(40.0, 36.0),
        lon=slice(-78.0, -74.0)
    )

    print(chl_box)

    print("Min:", chl_box.min().values)
    print("Max:", chl_box.max().values)
    print("Mean:", chl_box.mean().values)



plt.figure(figsize=(10, 8))

chl_box.plot(
    cmap="viridis",
    vmin=0,
    vmax=20,
    cbar_kwargs={"label": "Chlorophyll-a (mg/3"}
)

plt.title(f"MODIS-Aqua Chlorophyll-a\n{filename}")
plt.xlabel("Longitude")
plt.ylabel("Latitude")

#plt.show()
plt.savefig(os.path.join(outdir, "first_plot.png"))