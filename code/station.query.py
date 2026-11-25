from pathlib import Path
import pandas as pd

BASE = Path(
    "/glade/derecho/scratch/zacharys/HAB_Prediction/data/stations/tidal"
)

TARGET_YEARS = set(range(2000, 2026))

records = []

for station_dir in BASE.iterdir():

    if not station_dir.is_dir():
        continue

    station = station_dir.name

    years = []

    for f in station_dir.glob("*.csv"):

        try:
            year = int(f.stem.split("_")[-1])
            years.append(year)

        except Exception:
            pass

    years = sorted(set(years))

    missing = sorted(TARGET_YEARS - set(years))

    records.append(
        {
            "station": station,
            "start": min(years) if years else None,
            "end": max(years) if years else None,
            "nyears": len(years),
            "missing_years": ",".join(map(str, missing))
        }
    )

coverage = pd.DataFrame(records)

coverage = coverage.sort_values(
    ["nyears", "station"],
    ascending=[False, True]
)

coverage.to_csv(
    "station_coverage_report.csv",
    index=False
)

incomplete = coverage[
    coverage["nyears"] < 26
]

incomplete.to_csv(
    "stations_missing_years.csv",
    index=False
)

print()
print("Total stations:", len(coverage))
print("Complete stations:", (coverage["nyears"] == 26).sum())
print("Incomplete stations:", len(incomplete))
print()

print(coverage.head(20))