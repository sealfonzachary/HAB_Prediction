import requests
import pandas as pd

# Get Chesapeake Bay segment metadata
segments = requests.get(
    "https://datahub.chesapeakebay.net/api/GeographicAttribute/CBSeg2003"
).json()

segments = pd.DataFrame(segments)

print(segments.head())
print(f"Segments: {len(segments)}")

# Pull station metadata for Chesapeake segments
all_stations = []

for seg_id in segments["cbSegment2003Id"]:

    url = (
        "https://datahub.chesapeakebay.net/api/"
        f"WaterQuality/Station/CBSeg2003/{seg_id}"
        "?format=json"
    )

    try:
        r = requests.get(url, timeout=60)

        if r.status_code == 200:
            data = r.json()

            if len(data):
                all_stations.append(
                    pd.DataFrame(data)
                )

        print(f"Segment {seg_id} complete")

    except Exception as e:
        print(seg_id, e)

stations = pd.concat(
    all_stations,
    ignore_index=True
)

stations = stations.drop_duplicates(
    subset=["station"]
)

stations.to_csv(
    "chesapeake_bay_stations.csv",
    index=False
)

print(stations.columns)
print(stations.head())
print(f"Unique stations: {len(stations)}")