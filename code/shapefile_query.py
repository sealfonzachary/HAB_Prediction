import geopandas as gpd

url = (
    "https://gis.chesapeakebay.net/ags/rest/services/"
    "Modeling/salinity_surface/MapServer/0/query"
    "?where=1=1"
    "&outFields=*"
    "&f=geojson"
)

gdf = gpd.read_file(url)

print(gdf.head())
print(gdf.columns)