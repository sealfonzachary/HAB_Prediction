cbp = df[
    df["stationName"].str.contains(
        r"^CB",
        na=False
    )
]

print(len(cbp))

cbp.to_csv(
    "/glade/derecho/scratch/zacharys/HAB_Prediction/data/stations/cbp_stations.csv",
    index=False
)