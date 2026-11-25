import pandas as pd
from pathlib import Path

BASE = Path(
    "/glade/derecho/scratch/zacharys/HAB_Prediction/data/stations/tidal"
)

records = []

for station_dir in BASE.iterdir():

    if not station_dir.is_dir():
        continue

    years = []

    for f in station_dir.glob("*.csv"):

        try:
            year = int(
                f.stem.split("_")[-1]
            )
            years.append(year)

        except:
            pass

    if len(years):

        records.append({
            "station": station_dir.name,
            "start": min(years),
            "end": max(years),
            "nyears": len(years)
        })

coverage = pd.DataFrame(records)

coverage = coverage.sort_values(
    "nyears",
    ascending=False
)

print(coverage.head(50))