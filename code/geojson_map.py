
import geopandas as gpd
import matplotlib.pyplot as plt

gdf = gpd.read_file("data/chesapeake_salinity.geojson")

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

ax.set_title(
    "Chesapeake Bay Salinity Regions"
)

plt.show()