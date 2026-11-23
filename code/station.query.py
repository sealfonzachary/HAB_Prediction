
#HOW TO USE: edit START_YEAR / END_YEAR,
import csv, io, itertools, re, time
from pathlib import Path
import requests

# ===================== EDIT THESE =====================
START_YEAR = 2000        # END_YEAR - START_YEAR must be <= 9
END_YEAR   = 2009
TEST_N     = 0           # set to e.g. 5 to try only the first 5 stations; 0 = all
# ======================================================

OUT_DIR  = Path("/glade/derecho/scratch/zacharys/HAB_Prediction/data/stations")
BASE     = "https://datahub.chesapeakebay.net/api"
BATCH    = 30            # IDs per request (API max is 60). Lower if requests time out.

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


def get_ids(endpoint, key):
    """Fetch a metadata list and return its sorted IDs."""
    rows = requests.get(f"{BASE}/{endpoint}?format=json", timeout=60).json()
    return sorted({row[key] for row in rows})


def chunks(items, n=BATCH):
    return [items[i:i + n] for i in range(0, len(items), n)]


def csv_ids(ids):
    return ",".join(map(str, ids))


# 1. Get every station, substance (parameter), program and project ID
stations = get_ids("GeographicAttribute/Station", "stationId")
if TEST_N:
    stations = stations[:TEST_N]
substances = get_ids("MetaDataAttribute/Substance", "substanceId")
programs = get_ids("MetaDataAttribute/WaterQualityPrograms", "programId")
projects = get_ids("MetaDataAttribute/WaterQualityProjects", "projectId")
print(f"{len(stations)} stations, {len(substances)} substances")

# 2. Loop over batches (API limits each parameter to 60 IDs)
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

    # 3. Split the response into one file per station per year
    if text and text.strip():
        reader = csv.reader(io.StringIO(text, newline=""))
        header = next(reader)
        col = {h.lower(): i for i, h in enumerate(header)}
        groups = {}
        for row in reader:
            name = re.sub(r"[^A-Za-z0-9._-]+", "_", row[col["station"]])
            year = row[col["sampledate"]][:4]
            groups.setdefault((name, year), []).append(row)
        for (name, year), rows in groups.items():
            path = OUT_DIR / name / f"{name}_{year}.csv"
            path.parent.mkdir(exist_ok=True)
            new = not path.exists()
            with open(path, "a", newline="") as f:
                w = csv.writer(f)
                if new:
                    w.writerow(header)
                w.writerows(rows)
        print(f"  saved {sum(map(len, groups.values())):,} rows")

    done.add(key)
    done_file.write_text("\n".join(sorted(done)))
    time.sleep(0.5)

print("DONE")