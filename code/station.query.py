import pandas as pd

url = (
    "https://datahub.chesapeakebay.net/api/WaterQuality/"
    "01-01-2020/12-31-2020/"
    "0,1/2/12/HUC8/20/71?format=json"
)

df = pd.read_json(url)

print(df.columns)
print(df[["station","latitude","longitude"]].head())
print(len(df))