"""
Download Chesapeake Bay DataHub water-quality data: every station, every parameter.

Output:  <OUT_DIR>/tidal/<STATION>/<STATION>_<YEAR>.csv
         <OUT_DIR>/non_tidal/<STATION>/<STATION>_<YEAR>.csv
         <OUT_DIR>/unknown/...   (stations the API gave no location info for)

HOW TO USE: edit START_YEAR / END_YEAR, run `python download_chesapeake_wq.py`,
then edit the years and run again for the next decade (API max = 10 years per run).
Re-running the same years resumes. Station folders from earlier runs that are not
yet sorted into tidal / non_tidal are moved automatically at the start.
"""
import csv, io, itertools, json, re, shutil, time
from pathlib import Path
import requests

# ===================== EDIT THESE =====================
START_YEAR = 2000        # END_YEAR - START_YEAR must be <= 9
END_YEAR   = 2009
TEST_N     = 0           # set to e.g. 5 to try only the first 5 stations; 0 = all
# ======================================================

OUT_DIR = Path("/glade/derecho/scratch/zacharys/HAB_Prediction/data/stations")
BASE    = "https://datahub.chesapeakebay.net/api"
BATCH   = 30             # IDs per request (API max is 60). Lower if requests time out.

assert END_YEAR - START_YEAR <= 9, "API allows at most 10 years per run"
OUT_DIR.mkdir(parents=True, exist_ok=True)

session = requests.Session()
session.headers.update({"User-Agent": "Mozilla/5.0 (X11; Linux x86_64) HAB-Prediction-capstone",
                        "Accept": "*/*"})


def get(url, allow_404=False, tries=5):
    """Download a URL, retrying a few times. Returns text (None if 404 and allowed)."""
    for attempt in range(tries):
        try:
            r = session.get(url, timeout=(30, 600))
            if r.status_code == 404 and allow_404:
                return None
            r.raise_for_status()
            return r.text
        except Exception as e:
            print(f"  retry {attempt + 1}/{tries}: {e}")
            time.sleep(5 * 2 ** attempt)   # 5s, 10s, 20s, 40s, 80s
    raise RuntimeError(f"Failed: {url}")


def get_json(endpoint):
    return session.get(f"{BASE}/{endpoint}?format=json", timeout=60).json()


def chunks(items, n=BATCH):
    return [items[i:i + n] for i in range(0, len(items), n)]


def csv_ids(ids):
    return ",".join(map(str, ids))


def clean(name):
    return re.sub(r"[^A-Za-z0-9._-]+", "_", str(name).strip())


# 1. Get the list of WATER QUALITY stations (not all 78,000 stations in DataHub)
#    Ask the API for the water-quality stations inside every HUC8 watershed and every
#    Bay segment. Each result already includes lat/lon and the Bay segment (CBSeg2003),
#    so we can classify tidal vs non-tidal without any extra lookups.
info_path = OUT_DIR.parent / "wq_station_info.csv"
FIELDS = ["station", "kind", "latitude", "longitude", "cbSeg2003", "fallLine", "state", "description"]
info = {}                                  # station name -> row
if info_path.exists():
    with open(info_path, newline="") as f:
        info = {r["station"]: r for r in csv.DictReader(f)}
    print(f"Loaded {len(info)} water-quality stations from {info_path} (delete it to refresh)")
else:
    def fetch_stations(geo_type, ids):
        """Fetch station details for a list of geography ids; falls back to one at a time."""
        for batch in chunks(ids, 20):
            text = None
            try:
                text = get(f"{BASE}/WaterQuality/Station/{geo_type}/{csv_ids(batch)}?format=json",
                           allow_404=True, tries=3)
                parts = [text]
            except RuntimeError:
                parts = []
                for i in batch:
                    try:
                        parts.append(get(f"{BASE}/WaterQuality/Station/{geo_type}/{i}?format=json",
                                         allow_404=True, tries=2))
                    except RuntimeError:
                        print(f"  could not fetch {geo_type} {i}")
            for text in parts:
                for d in json.loads(text) if text else []:
                    name = clean(d["station"])
                    tidal = (d.get("cbSeg2003") or "").strip() != ""
                    info[name] = {"station": name, "kind": "tidal" if tidal else "non_tidal",
                                  "latitude": d.get("latitude"), "longitude": d.get("longitude"),
                                  "cbSeg2003": d.get("cbSeg2003"), "fallLine": d.get("fallLine"),
                                  "state": d.get("state"), "description": d.get("stationDescription")}
            time.sleep(1)
        print(f"  after {geo_type}: {len(info)} stations")

    print("Finding water-quality stations (this takes a few minutes, only the first time)...")
    fetch_stations("CBSeg2003", sorted(r["cbSegment2003Id"] for r in get_json("GeographicAttribute/CBSeg2003")))
    fetch_stations("HUC8", sorted(r["huc8Id"] for r in get_json("GeographicAttribute/HUC8")))
    if info:
        with open(info_path, "w", newline="") as f:
            w = csv.DictWriter(f, fieldnames=FIELDS)
            w.writeheader()
            w.writerows(info.values())

kind = {name: r["kind"] for name, r in info.items()}

# The data query needs station IDs, so match station names to IDs
name_to_id = {clean(r["stationName"]): r["stationId"] for r in get_json("GeographicAttribute/Station")}
wq_names = sorted(info)
if TEST_N:
    wq_names = wq_names[:TEST_N]
stations = sorted(name_to_id[n] for n in wq_names if n in name_to_id)
missing = [n for n in wq_names if n not in name_to_id]
if missing:
    print(f"  {len(missing)} stations have no ID match and will be skipped: {missing[:5]}")

substances = sorted({r["substanceId"] for r in get_json("MetaDataAttribute/Substance")})
programs = sorted({r["programId"] for r in get_json("MetaDataAttribute/WaterQualityPrograms")})
projects = sorted({r["projectId"] for r in get_json("MetaDataAttribute/WaterQualityProjects")})
n_t = sum(kind[n] == "tidal" for n in wq_names)
print(f"{len(stations)} water-quality stations ({n_t} tidal, {len(wq_names) - n_t} non-tidal), "
      f"{len(substances)} substances")

# 3. Move station folders from earlier runs into tidal/ or non_tidal/
for old in [p for p in OUT_DIR.iterdir() if p.is_dir() and p.name not in ("tidal", "non_tidal", "unknown")]:
    new = OUT_DIR / kind.get(old.name, "unknown") / old.name
    new.mkdir(parents=True, exist_ok=True)
    for f in old.glob("*.csv"):
        if (new / f.name).exists():          # same year already there: append rows, skip header
            with open(f) as src, open(new / f.name, "a") as dst:
                next(src, None)
                dst.writelines(src)
            f.unlink()
        else:
            shutil.move(str(f), str(new / f.name))
    try:
        old.rmdir()
    except OSError:
        pass
    print(f"  moved {old.name} -> {new.parent.name}/")

# 4. Download in batches (API limits each parameter to 60 IDs)
start, end = f"01-01-{START_YEAR}", f"12-31-{END_YEAR}"
jobs = list(itertools.product(chunks(stations), chunks(substances),
                              chunks(programs, 60), chunks(projects, 60)))
done_file = OUT_DIR.parent / f"done_{START_YEAR}_{END_YEAR}.txt"
done = set(done_file.read_text().split()) if done_file.exists() else set()
print(f"{len(jobs)} requests needed for {START_YEAR}-{END_YEAR}; {len(done)} already done")
failed_jobs = []

for n, (st, sub, prog, proj) in enumerate(jobs, 1):
    key = f"{st[0]}-{sub[0]}-{prog[0]}-{proj[0]}"
    if key in done:
        continue
    print(f"[{n}/{len(jobs)}] downloading...")
    url = (f"{BASE}/WaterQuality/{start}/{end}/0,1/{csv_ids(prog)}/{csv_ids(proj)}"
           f"/Station/{csv_ids(st)}/{csv_ids(sub)}?format=csv")
    try:
        text = get(url, allow_404=True)      # 404 = no data in this batch
    except RuntimeError:                     # server refused: skip, retry on next run
        print("  FAILED (will be retried next run)")
        failed_jobs.append(n)
        continue

    # 5. Split the response into one file per station per year
    if text and text.strip():
        reader = csv.reader(io.StringIO(text, newline=""))
        header = next(reader)
        col = {h.lower(): i for i, h in enumerate(header)}
        groups, skipped = {}, 0
        for row in reader:
            if len(row) < len(header):       # blank or malformed line: skip it
                skipped += 1
                continue
            name = clean(row[col["station"]])
            year = row[col["sampledate"]][:4]
            groups.setdefault((name, year), []).append(row)
        for (name, year), rows in groups.items():
            path = OUT_DIR / kind.get(name, "unknown") / name / f"{name}_{year}.csv"
            path.parent.mkdir(parents=True, exist_ok=True)
            new = not path.exists()
            with open(path, "a", newline="") as f:
                w = csv.writer(f)
                if new:
                    w.writerow(header)
                w.writerows(rows)
        print(f"  saved {sum(map(len, groups.values())):,} rows"
              + (f" ({skipped} malformed lines skipped)" if skipped else ""))

    done.add(key)
    done_file.write_text("\n".join(sorted(done)))
    time.sleep(0.5)

print(f"\nDONE. {len(jobs) - len(done)} requests still not done"
      + (f" ({len(failed_jobs)} failed this run: re-run the script to retry them)" if failed_jobs else ""))
for k in ("tidal", "non_tidal", "unknown"):
    d = OUT_DIR / k
    print(f"  {k}: {sum(p.is_dir() for p in d.iterdir()) if d.exists() else 0} station folders")