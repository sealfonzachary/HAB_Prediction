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
import csv, io, itertools, re, shutil, time
from pathlib import Path
import requests

# ===================== EDIT THESE =====================
START_YEAR = 2000       # END_YEAR - START_YEAR must be <= 9
END_YEAR   = 2009
TEST_N     = 0           # set to e.g. 5 to try only the first 5 stations; 0 = all
# ======================================================

OUT_DIR = Path("/glade/derecho/scratch/zacharys/HAB_Prediction/data/stations")
BASE    = "https://datahub.chesapeakebay.net/api"
BATCH   = 30             # IDs per request (API max is 60). Lower if requests time out.

assert END_YEAR - START_YEAR <= 9, "API allows at most 10 years per run"
OUT_DIR.mkdir(parents=True, exist_ok=True)


def get(url, allow_404=False):
    """Download a URL, retrying a few times. Returns text (None if 404 and allowed)."""
    for attempt in range(5):
        try:
            r = requests.get(url, timeout=(30, 600))
            if r.status_code == 404 and allow_404:
                return None
            r.raise_for_status()
            return r.text
        except Exception as e:
            print(f"  retry {attempt + 1}/5: {e}")
            time.sleep(2 ** attempt)
    raise RuntimeError(f"Failed: {url}")


def get_json(endpoint):
    return requests.get(f"{BASE}/{endpoint}?format=json", timeout=60).json()


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
kind = {}                      # station name -> "tidal" / "non_tidal"
info_path = OUT_DIR.parent / "station_info.csv"
info_rows = []
for batch in chunks(stations, 60):
    details = get(f"{BASE}/WaterQuality/Station/Station/{csv_ids(batch)}?format=json", allow_404=True)
    if not details:
        continue
    import json
    for d in json.loads(details):
        name = clean(d["station"])
        kind[name] = "tidal" if (d.get("cbSeg2003") or "").strip() else "non_tidal"
        info_rows.append({"station": name, "kind": kind[name], "latitude": d.get("latitude"),
                          "longitude": d.get("longitude"), "cbSeg2003": d.get("cbSeg2003"),
                          "fallLine": d.get("fallLine"), "state": d.get("state"),
                          "description": d.get("stationDescription")})
if info_rows:
    with open(info_path, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(info_rows[0]))
        w.writeheader()
        w.writerows(info_rows)
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

for n, (st, sub, prog, proj) in enumerate(jobs, 1):
    key = f"{st[0]}-{sub[0]}-{prog[0]}-{proj[0]}"
    if key in done:
        continue
    print(f"[{n}/{len(jobs)}] downloading...")
    url = (f"{BASE}/WaterQuality/{start}/{end}/0,1/{csv_ids(prog)}/{csv_ids(proj)}"
           f"/Station/{csv_ids(st)}/{csv_ids(sub)}?format=csv")
    text = get(url, allow_404=True)          # 404 = no data in this batch

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

print("DONE")