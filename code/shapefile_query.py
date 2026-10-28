import requests
import geopandas as gpd
import pandas as pd

base_url = (
    "https://gis.chesapeakebay.net/ags/rest/services/Modeling/salinity_surface/MapServer/0/query"
)

all_features = []
offset = 0
chunk = 2000

while True:

    params = {
        "where": "1=1",
        "outFields": "*",
        "returnGeometry": "true",
        "f": "geojson",
        "resultOffset": offset,
        "resultRecordCount": chunk
    }

    r = requests.get(base_url, params=params)
    js = r.json()

    feats = js["features"]

    print(f"offset={offset}  features={len(feats)}")

    if len(feats) == 0:
        break

    all_features.extend(feats)

    offset += chunk

print(f"\nTOTAL FEATURES: {len(all_features)}")

geojson = {
    "type": "FeatureCollection",
    "features": all_features
}

gdf = gpd.GeoDataFrame.from_features(
    geojson,
    crs="EPSG:4326"
)
print(gdf["SEGMENT"].unique())

gdf.to_file(
    "chesapeake_salinity_full.geojson",
    driver="GeoJSON"
)

print("saved")