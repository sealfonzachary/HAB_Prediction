import requests
import pandas as pd
from pathlib import Path

# ============================================================
# CHANGE ONLY THESE VALUES
# ============================================================

START_YEAR = 2000
END_YEAR   = 2009

# ============================================================
# INPUT FILE
# ============================================================

stations = pd.read_csv(
    "/glade/derecho/scratch/zacharys/HAB_Prediction/data/stations/tidal_stations.csv"
)

OUTPUT_ROOT = Path(
    "/glade/derecho/scratch/zacharys/HAB_Prediction/data/stations/tidal"
)

OUTPUT_ROOT.mkdir(
    parents=True,
    exist_ok=True
)

# ============================================================
# DOWNLOAD
# ============================================================

for _, row in stations.iterrows():

    station = row["station"]

    station_dir = OUTPUT_ROOT / station

    station_dir.mkdir(
        exist_ok=True
    )

    for year in range(
        START_YEAR,
        END_YEAR + 1
    ):

        outfile = (
            station_dir /
            f"{station}_{year}.csv"
        )

        if outfile.exists():

            print(
                f"SKIP {outfile.name}"
            )

            continue

        url = (
            "https://datahub.chesapeakebay.net/api/"
            f"WaterQuality/"
            f"01-01-{year}/12-31-{year}/"
            f"0,1/2/12/"
            f"Station/{station}/71"
            "?format=json"
        )

        try:

            r = requests.get(
                url,
                timeout=120
            )

            if r.status_code != 200:

                print(
                    f"FAIL {station} {year}"
                )

                continue

            data = r.json()

            if len(data) == 0:

                print(
                    f"EMPTY {station} {year}"
                )

                continue

            pd.DataFrame(
                data
            ).to_csv(
                outfile,
                index=False
            )

            print(
                f"SAVED {station} {year}"
            )

        except Exception as e:

            print(
                f"ERROR {station} {year}: {e}"
            )