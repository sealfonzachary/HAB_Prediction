import requests
'''
url = (
    "https://gis.chesapeakebay.net/ags/rest/services/"
    "Modeling/salinity_surface/MapServer/0/query"
    "?where=1=1"
    "&outFields=*"
    "&f=geojson"
)

r = requests.get(url)

with open("chesapeake_salinity.geojson", "w", encoding="utf-8") as f:
    f.write(r.text)

print("saved")
'''

import geopandas as gpd

gdf = gpd.read_file("chesapeake_salinity.geojson")

print(gdf.columns)

print(gdf[[
    "SEGMENT",
    "SALINITY"
]].head())
gdf["zone"] = gdf["SEGMENT"].str.extract(
    r"(TF|OH|MH|PH)"
)