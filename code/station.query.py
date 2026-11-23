import pandas as pd

url = "https://datahub.chesapeakebay.net/api/Stations"

df = pd.read_json(url)

print(df.columns)
print(df.head())
print(len(df))

df.to_csv(
    "../data/stations/all_stations.csv",
    index=False
)