# download_stations.py

import requests
import pandas as pd
from pathlib import Path

OUTDIR = Path(
    "/glade/derecho/scratch/zacharys/HAB_Prediction/data/stations"
)

OUTDIR.mkdir(parents=True, exist_ok=True)

# Download station catalog
r = requests.get(
    "https://datahub.chesapeakebay.net/api/GeographicAttribute/Station",
    timeout=120
)

r.raise_for_status()

stations = pd.DataFrame(r.json())

print(stations.columns)
print(stations.head())
print(f"\nStations found: {len(stations)}")

stations.to_csv(
    OUTDIR / "all_station_ids.csv",
    index=False
)

print(
    f"Saved {OUTDIR/'all_station_ids.csv'}"
)