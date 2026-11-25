import requests
import pandas as pd
from pathlib import Path

# ============================================================
# OUTPUT DIRECTORY
# ============================================================

OUTDIR = Path(
    "/glade/derecho/scratch/zacharys/HAB_Prediction/data/stations"
)

OUTDIR.mkdir(parents=True, exist_ok=True)

# ============================================================
# GET ALL CHESAPEAKE BAY SEGMENTS
# ============================================================

segments = pd.DataFrame(
    requests.get(
        "https://datahub.chesapeakebay.net/api/GeographicAttribute/CBSeg2003",
        timeout=60
    ).json()
)

print(f"Found {len(segments)} Chesapeake Bay segments")

# ============================================================
# DOWNLOAD STATIONS FOR EACH BAY SEGMENT
# ============================================================

all_stations = []

for seg_id in segments["cbSegment2003Id"]:

    url = (
        "https://datahub.chesapeakebay.net/api/"
        f"WaterQuality/Station/CBSeg2003/{seg_id}"
        "?format=json"
    )

    try:

        r = requests.get(
            url,
            timeout=60
        )

        if r.status_code == 200:

            data = r.json()

            if len(data) > 0:
                all_stations.append(
                    pd.DataFrame(data)
                )

        print(f"Segment {seg_id:3d} complete")

    except Exception as e:

        print(f"Segment {seg_id}: {e}")

# ============================================================
# COMBINE RESULTS
# ============================================================

stations = pd.concat(
    all_stations,
    ignore_index=True
)

stations = stations.drop_duplicates(
    subset=["station"]
)

print("\nColumns:")
print(stations.columns)

print(
    f"\nUnique Chesapeake stations: "
    f"{len(stations)}"
)

# ============================================================
# SAVE MASTER FILE
# ============================================================

master_file = OUTDIR / "chesapeake_bay_stations.csv"

stations.to_csv(
    master_file,
    index=False
)

print(f"\nSaved: {master_file}")

# ============================================================
# SPLIT TIDAL / NONTIDAL
# ============================================================

tidal = stations[
    stations["fallLine"] == "B"
].copy()

nontidal = stations[
    stations["fallLine"] != "B"
].copy()

tidal.to_csv(
    OUTDIR / "tidal_stations.csv",
    index=False
)

nontidal.to_csv(
    OUTDIR / "nontidal_stations.csv",
    index=False
)

print(
    f"Tidal stations: {len(tidal)}"
)

print(
    f"Nontidal stations: {len(nontidal)}"
)