import pandas as pd
from pathlib import Path

stations = pd.read_csv(
    "chesapeake_bay_stations.csv"
)

Path("../data/stations/tidal").mkdir(
    parents=True,
    exist_ok=True
)

Path("../data/stations/nontidal").mkdir(
    parents=True,
    exist_ok=True
)

tidal = stations[
    stations["fallLine"] == "B"
].copy()

nontidal = stations[
    stations["fallLine"] != "B"
].copy()

tidal.to_csv(
    "../data/stations/tidal/stations.csv",
    index=False
)

nontidal.to_csv(
    "../data/stations/nontidal/stations.csv",
    index=False
)

print(f"Tidal: {len(tidal)}")
print(f"Nontidal: {len(nontidal)}")