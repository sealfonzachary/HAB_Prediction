import geopandas as gpd
import matplotlib.pyplot as plt
import os

gdf_path = r"C:\Users\zseal\capstone\HAB_Prediction\data\chesapeake_salinity_full.geojson"
outfile = r"C:\Users\zseal\capstone\HAB_Prediction\results"
print(os.path.exists(gdf_path))

gdf = gpd.read_file(gdf_path)

print(len(gdf))
print(gdf["SEGMENT"].unique())
gdf["zone"] = gdf["SEGMENT"].str.extract(
    r"(TF|OH|MH|PH)"
)

print(gdf["zone"].value_counts())

fig, ax = plt.subplots(figsize=(8,10))

gdf.plot(
    column="zone",
    categorical=True,
    legend=True,
    ax=ax,
    linewidth=0
)

ax.set_title("Chesapeake Bay Salinity Regions")
ax.set_xlim(-77.8, -75.0)
ax.set_ylim(36.8, 39.8)

plt.savefig(
    outfile,
    dpi=300,
)
plt.show()
