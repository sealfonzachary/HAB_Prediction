"""
MODIS Aqua L3 chlor_a (4 km daily) -> Chesapeake Bay maps with salinity-zone divisions

Input : hundreds of files named like AQUA_MODIS.20161202.L3m.DAY.CHL.chlor_a.4km.nc
Output (in OUT_DIR):
  chesapeake_chla_stack.nc        all days cropped to the Bay, one file (reuse this!)
  salinity_zones.nc               zone grid (0=TF, 1=OH, 2=MH, 3=PH)
  zone_map.png                    the four zones on the 4 km grid
  coverage_by_day.csv             fraction of Bay pixels with valid data each day
  zone_timeseries.csv             per day & zone: mean/median chl, n pixels, % exceeding threshold
  composites/summer_YYYY.png      Jun-Sep mean chlorophyll per year with zone lines
  summer_panel.png                all years side by side (good for picking a reference year)
  daily/chl_YYYYMMDD.png          individual clear-ish days (optional)

Install: pip install xarray netcdf4 numpy pandas matplotlib scipy
         (+ geopandas only if you use the shapefile method)
"""
import glob, os, re, warnings
import numpy as np
import pandas as pd
import xarray as xr
import matplotlib.pyplot as plt
from matplotlib.colors import LogNorm, ListedColormap
from matplotlib.patches import Patch

warnings.filterwarnings("ignore")

# ------------------------------------------------------------------ CONFIG
NC_DIR = "modis_files"                       # folder with your .nc files
OUT_DIR = "chesapeake_outputs"
BBOX = dict(lon=(-77.5, -75.5), lat=(36.7, 39.7))
CHL_RANGE = (0.5, 40)                        # color scale, mg/m^3 (= ug/L)
MAKE_DAILY_MAPS = True
DAILY_MIN_COVERAGE = 0.35                    # only map days with >=35% valid water pixels
import xarray as xr

ds = xr.open_dataset(
    "modis_files/AQUA_MODIS.20161202.L3m.DAY.CHL.chlor_a.4km.nc"
)

print(ds)

# --- how to draw salinity zones: "insitu" or "shapefile"
ZONE_METHOD = "insitu"

# insitu method: uses your CBP water-quality CSV (station lat/lon + salinity)
CBP_CSV = "cbp_water_quality.csv"
CBP_COLS = dict(station="Station", lat="Latitude", lon="Longitude", date="SampleDate",
                sal="SALINITY", layer="Layer")        # <-- edit to match your header row
MAX_DIST_DEG = 0.2                           # don't assign zones farther than this from a station

# shapefile method: CBP segmentation polygons (download from the CBP GIS data / Data Hub)
SEGMENT_SHP = "CBSeg2003.shp"
SEGMENT_FIELD = "CBSEG_2003"                 # field whose value ends in TF/OH/MH/PH

ZONES = ["TF", "OH", "MH", "PH"]
ZONE_NAMES = ["Tidal fresh (<0.5)", "Oligohaline (0.5-5)", "Mesohaline (5-18)", "Polyhaline (>18)"]
ZONE_COLORS = ["#2b83ba", "#abdda4", "#fdae61", "#d7191c"]
SAL_BREAKS = [0.5, 5, 18]
THRESH = {"TF": 12.0, "OH": 9.47, "MH": 7.70, "PH": 4.0}   # summer, ug/L (Lacouture et al. 2006)


# ------------------------------------------------------------------ BUILD / LOAD STACK
def file_date(path):
    return pd.to_datetime(re.search(r"\.(\d{8})\.", os.path.basename(path)).group(1))


def crop_one(path):
    with xr.open_dataset(path) as ds:
        lat = ds["lat"].values
        lat_sl = slice(BBOX["lat"][1], BBOX["lat"][0]) if lat[0] > lat[-1] else slice(*BBOX["lat"])
        da = ds["chlor_a"].sel(lat=lat_sl, lon=slice(*BBOX["lon"])).load()
    return da.where((da > 0.01) & (da < 100))          # drop absurd retrievals


def build_stack():
    out = os.path.join(OUT_DIR, "chesapeake_chla_stack.nc")
    if os.path.exists(out):
        return xr.open_dataarray(out).load()
    files = sorted(glob.glob(os.path.join(NC_DIR, "AQUA_MODIS.*.nc")))
    print(f"Cropping {len(files)} files...")
    arrs = []
    for i, f in enumerate(files):
        try:
            da = crop_one(f)
            arrs.append(da.expand_dims(time=[file_date(f)]).drop_vars(
                [c for c in ("palette",) if c in da.coords], errors="ignore"))
        except Exception as e:
            print("  skipped", os.path.basename(f), e)
        if i % 100 == 0:
            print(f"  {i}/{len(files)}")
    stack = xr.concat(arrs, dim="time").sortby("time").rename("chlor_a")
    stack.attrs["units"] = "mg m-3"
    stack.to_netcdf(out)
    return stack


# ------------------------------------------------------------------ SALINITY ZONES
def zones_insitu(stack, water):
    """Zone grid from long-term summer mean surface salinity at CBP stations, interpolated."""
    from scipy.interpolate import griddata
    from scipy.spatial import cKDTree
    c = CBP_COLS
    df = pd.read_csv(CBP_CSV, low_memory=False)
    df[c["date"]] = pd.to_datetime(df[c["date"]], errors="coerce")
    df = df[df[c["date"]].dt.month.isin([6, 7, 8, 9])]
    if c["layer"] in df:
        df = df[df[c["layer"]].astype(str).str.upper().isin(["S", "SURFACE", "AP", "AB"])
                | df[c["layer"]].isna()]
    st = (df.groupby(c["station"])
            .agg(lat=(c["lat"], "first"), lon=(c["lon"], "first"), sal=(c["sal"], "mean"))
            .dropna())
    lon2d, lat2d = np.meshgrid(stack.lon.values, stack.lat.values)
    pts = st[["lon", "lat"]].values
    sal = griddata(pts, st["sal"].values, (lon2d, lat2d), method="linear")
    near = griddata(pts, st["sal"].values, (lon2d, lat2d), method="nearest")
    sal = np.where(np.isnan(sal), near, sal)
    dist, _ = cKDTree(pts).query(np.c_[lon2d.ravel(), lat2d.ravel()])
    sal = np.where(dist.reshape(lon2d.shape) <= MAX_DIST_DEG, sal, np.nan)
    z = np.digitize(sal, SAL_BREAKS).astype(float)
    z[np.isnan(sal) | ~water.values] = np.nan
    return z


def zones_shapefile(stack, water):
    """Zone grid from CBP segment polygons (segment codes end in TF/OH/MH/PH)."""
    import geopandas as gpd
    polys = gpd.read_file(SEGMENT_SHP).to_crs(4326)
    code = polys[SEGMENT_FIELD].astype(str).str.upper().str.extract(r"(TF|OH|MH|PH)\d*$")[0]
    polys["zone"] = code.map({z: i for i, z in enumerate(ZONES)})
    polys = polys.dropna(subset=["zone"])[["zone", "geometry"]]
    lon2d, lat2d = np.meshgrid(stack.lon.values, stack.lat.values)
    pts = gpd.GeoDataFrame({"idx": np.arange(lon2d.size)},
                           geometry=gpd.points_from_xy(lon2d.ravel(), lat2d.ravel()),
                           crs=4326)
    j = gpd.sjoin_nearest(pts, polys, max_distance=0.04, how="left")   # ~4 km tolerance
    j = j.drop_duplicates("idx").sort_values("idx")
    z = j["zone"].values.reshape(lon2d.shape).astype(float)
    z[~water.values] = np.nan
    return z


# ------------------------------------------------------------------ PLOTTING
def draw_base(ax, stack, water, zones):
    lon, lat = stack.lon.values, stack.lat.values
    land = np.where(water.values, np.nan, 1.0)
    ax.pcolormesh(lon, lat, land, cmap=ListedColormap(["0.78"]), shading="auto")
    ax.set_xlim(*BBOX["lon"]); ax.set_ylim(*BBOX["lat"])
    ax.set_aspect(1 / np.cos(np.deg2rad(38.2)))
    return lon, lat


def add_zone_lines(ax, stack, zones):
    zf = np.where(np.isnan(zones), -1, zones)
    ax.contour(stack.lon.values, stack.lat.values, zf, levels=[0.5, 1.5, 2.5],
               colors="k", linewidths=0.9, linestyles="--")


def map_chl(field, stack, water, zones, title, path, with_cbar=True):
    fig, ax = plt.subplots(figsize=(5.5, 7))
    lon, lat = draw_base(ax, stack, water, zones)
    m = ax.pcolormesh(lon, lat, field, cmap="viridis", norm=LogNorm(*CHL_RANGE), shading="auto")
    add_zone_lines(ax, stack, zones)
    ax.set_title(title, fontsize=11)
    ax.set_xlabel("Longitude"); ax.set_ylabel("Latitude")
    if with_cbar:
        fig.colorbar(m, ax=ax, shrink=0.7, label="Chlorophyll-a (µg/L)")
    ax.legend(handles=[plt.Line2D([], [], color="k", ls="--", lw=0.9, label="Salinity zone boundary")],
              loc="lower left", fontsize=8)
    fig.tight_layout(); fig.savefig(path, dpi=150); plt.close(fig)


def map_zones(stack, water, zones, path):
    fig, ax = plt.subplots(figsize=(5.5, 7))
    lon, lat = draw_base(ax, stack, water, zones)
    ax.pcolormesh(lon, lat, zones, cmap=ListedColormap(ZONE_COLORS), vmin=-0.5, vmax=3.5,
                  shading="auto")
    ax.legend(handles=[Patch(color=c, label=n) for c, n in zip(ZONE_COLORS, ZONE_NAMES)],
              loc="lower left", fontsize=8, title="Salinity zone (psu)")
    ax.set_title("Salinity zones on the MODIS 4 km grid")
    fig.tight_layout(); fig.savefig(path, dpi=150); plt.close(fig)


# ------------------------------------------------------------------ MAIN
def main():
    os.makedirs(OUT_DIR, exist_ok=True)
    os.makedirs(os.path.join(OUT_DIR, "composites"), exist_ok=True)
    stack = build_stack()
    water = stack.notnull().any("time")                 # pixels that EVER have data
    print(f"{stack.sizes['time']} days, grid {stack.sizes['lat']}x{stack.sizes['lon']}, "
          f"{int(water.sum())} water pixels")

    zones = zones_insitu(stack, water) if ZONE_METHOD == "insitu" else zones_shapefile(stack, water)
    zda = xr.DataArray(zones, coords=[stack.lat, stack.lon], dims=["lat", "lon"], name="zone")
    zda.attrs["legend"] = "0=TF 1=OH 2=MH 3=PH"
    zda.to_netcdf(os.path.join(OUT_DIR, "salinity_zones.nc"))
    map_zones(stack, water, zones, os.path.join(OUT_DIR, "zone_map.png"))

    # coverage per day
    cov = (stack.notnull().where(water).sum(("lat", "lon")) / water.sum()).to_series()
    cov.rename("valid_fraction").to_csv(os.path.join(OUT_DIR, "coverage_by_day.csv"))

    # zone time series
    parts = []
    for i, z in enumerate(ZONES):
        m = zda == i
        if int(m.sum()) == 0:
            continue
        sub = stack.where(m)
        parts.append(pd.DataFrame({
            "date": stack.time.values, "zone": z,
            "n_zone_pixels": int(m.sum()),
            "n_valid": sub.notnull().sum(("lat", "lon")).values,
            "chl_mean": sub.mean(("lat", "lon")).values,
            "chl_median": sub.median(("lat", "lon")).values,
            "frac_above_threshold": ((sub > THRESH[z]).where(sub.notnull())
                                     .mean(("lat", "lon"))).values}))
    pd.concat(parts).to_csv(os.path.join(OUT_DIR, "zone_timeseries.csv"), index=False)

    # summer composites per year
    years = sorted(set(stack.time.dt.year.values.tolist()))
    comps = {}
    for y in years:
        s = stack.sel(time=(stack.time.dt.year == y) & stack.time.dt.month.isin([6, 7, 8, 9]))
        if s.sizes["time"] < 5:
            continue
        mean = s.mean("time").where(s.notnull().sum("time") >= 3)
        comps[y] = mean.values
        map_chl(mean.values, stack, water, zones,
                f"Summer (Jun-Sep) mean chlorophyll-a, {y}",
                os.path.join(OUT_DIR, "composites", f"summer_{y}.png"))

    # small-multiples panel
    if comps:
        n = len(comps); nc = min(5, n); nr = int(np.ceil(n / nc))
        fig, axes = plt.subplots(nr, nc, figsize=(3 * nc, 4 * nr), squeeze=False)
        for ax in axes.ravel():
            ax.axis("off")
        for ax, (y, f) in zip(axes.ravel(), comps.items()):
            ax.axis("on"); draw_base(ax, stack, water, zones)
            m = ax.pcolormesh(stack.lon.values, stack.lat.values, f, cmap="viridis",
                              norm=LogNorm(*CHL_RANGE), shading="auto")
            add_zone_lines(ax, stack, zones)
            ax.set_title(str(y), fontsize=10); ax.set_xticks([]); ax.set_yticks([])
        fig.colorbar(m, ax=axes.ravel().tolist(), shrink=0.5, label="Chlorophyll-a (µg/L)")
        fig.savefig(os.path.join(OUT_DIR, "summer_panel.png"), dpi=130, bbox_inches="tight")
        plt.close(fig)

    # daily maps
    if MAKE_DAILY_MAPS:
        os.makedirs(os.path.join(OUT_DIR, "daily"), exist_ok=True)
        good = cov[cov >= DAILY_MIN_COVERAGE].index
        print(f"Making {len(good)} daily maps...")
        for t in good:
            d = pd.Timestamp(t)
            map_chl(stack.sel(time=d).values, stack, water, zones,
                    f"MODIS Aqua chlorophyll-a  {d:%Y-%m-%d}",
                    os.path.join(OUT_DIR, "daily", f"chl_{d:%Y%m%d}.png"))
    print("Done. Outputs in", OUT_DIR)


if __name__ == "__main__":
    main()