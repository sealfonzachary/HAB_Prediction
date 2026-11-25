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
START_YEAR = 2014        # END_YEAR - START_YEAR must be <= 9
END_YEAR   = 2023
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


# 1. Get every station, substance (parameter), program and project ID
station_rows = get_json("GeographicAttribute/Station")
stations = sorted({s["stationId"] for s in station_rows})
if TEST_N:
    stations = stations[:TEST_N]
substances = sorted({r["substanceId"] for r in get_json("MetaDataAttribute/Substance")})
programs = sorted({r["programId"] for r in get_json("MetaDataAttribute/WaterQualityPrograms")})
projects = sorted({r["projectId"] for r in get_json("MetaDataAttribute/WaterQualityProjects")})
print(f"{len(stations)} stations, {len(substances)} substances")

# 2. Classify stations: tidal = has a Chesapeake Bay segment (CBSeg2003); else non-tidal
#    Results are cached in station_info.csv, so later runs only look up new stations.
info_path = OUT_DIR.parent / "station_info.csv"
info = {}                                  # station name -> row
if info_path.exists():
    with open(info_path, newline="") as f:
        info = {r["station"]: r for r in csv.DictReader(f)}
kind = {name: r["kind"] for name, r in info.items()}


def lookup(ids):
    """Fetch station details; returns True if the request worked."""
    try:
        text = get(f"{BASE}/WaterQuality/Station/Station/{csv_ids(ids)}?format=json", allow_404=True, tries=2)
    except RuntimeError:
        return False
    for d in json.loads(text) if text else []:
        name = clean(d["station"])
        kind[name] = "tidal" if (d.get("cbSeg2003") or "").strip() else "non_tidal"
        info[name] = {"station": name, "kind": kind[name], "latitude": d.get("latitude"),
                      "longitude": d.get("longitude"), "cbSeg2003": d.get("cbSeg2003"),
                      "fallLine": d.get("fallLine"), "state": d.get("state"),
                      "description": d.get("stationDescription")}
    return True


names = {s["stationId"]: clean(s["stationName"]) for s in station_rows}
todo = [i for i in stations if names.get(i) not in kind]
print(f"{len(kind)} stations already classified, looking up {len(todo)} more")
failed = []
for batch in chunks(todo, 20):
    if not lookup(batch):                  # batch refused: retry one station at a time
        for i in batch:
            time.sleep(1)
            if not lookup([i]):
                failed.append(names.get(i, i))
    time.sleep(1)
if failed:
    print(f"  could not classify {len(failed)} stations (they go in unknown/): {failed[:10]}")
if info:
    with open(info_path, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=["station", "kind", "latitude", "longitude",
                                          "cbSeg2003", "fallLine", "state", "description"])
        w.writeheader()
        w.writerows(info.values())
n_t = sum(v == "tidal" for v in kind.values())
print(f"Classified {n_t} tidal, {len(kind) - n_t} non-tidal  (saved {info_path})")

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