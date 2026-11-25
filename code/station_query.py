
import requests
import json
import csv
import hashlib
import time
import re
from pathlib import Path
from itertools import product
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry


# ============================================================
# CONFIGURATION
# ============================================================

BASE_URL = "https://datahub.chesapeakebay.net/api"

OUTPUT_DIR = Path("datahub_water_quality")
METADATA_DIR = OUTPUT_DIR / "metadata"
RAW_DIR = OUTPUT_DIR / "raw_json"

# IMPORTANT:
# Leave False for the first run.
# The script will find a real observation and verify a minimal query.
# After the test succeeds, change this to True and run again.
RUN_FULL_DOWNLOAD = False

# Leave blank to include every available substance.
# Example: "Dissolved Oxygen"
SUBSTANCE_FILTER = ""

# Number of stations to try during the initial test.
PROBE_STATIONS_LIMIT = 10

# API limits
MAX_SELECTIONS = 60

# Date windows. The API permits a maximum 10-year range.
DATE_WINDOWS = [
    ("01-01-2000", "12-31-2009"),
    ("01-01-2010", "12-31-2019"),
    ("01-01-2020", "12-31-2025"),
]

STREAM = "0,1"

GEO_TYPE = "Station"

OUTPUT_DIR.mkdir(exist_ok=True)
METADATA_DIR.mkdir(exist_ok=True)
RAW_DIR.mkdir(exist_ok=True)


# ============================================================
# HTTP SESSION
# ============================================================

session = requests.Session()

retry_strategy = Retry(
    total=5,
    connect=5,
    read=5,
    backoff_factor=2,
    status_forcelist=[429, 500, 502, 503, 504],
    allowed_methods=["GET"],
)

adapter = HTTPAdapter(max_retries=retry_strategy)

session.mount("https://", adapter)
session.mount("http://", adapter)

session.headers.update({
    "Accept": "application/json",
    "User-Agent": "ChesapeakeBayWaterQualityResearch/1.0",
})


def get_json(url):
    """Request JSON and fail clearly on API errors."""

    response = session.get(url, timeout=180)

    if not response.ok:
        raise RuntimeError(
            f"API request failed: {response.status_code}\n"
            f"URL: {url}\n"
            f"Response: {response.text[:2000]}"
        )

    try:
        data = response.json()
    except ValueError:
        raise RuntimeError(
            f"API did not return valid JSON.\n"
            f"URL: {url}\n"
            f"Response: {response.text[:1000]}"
        )

    if not isinstance(data, list):
        raise RuntimeError(
            f"Expected a JSON list but received {type(data).__name__}.\n"
            f"URL: {url}\n"
            f"Response: {str(data)[:1000]}"
        )

    return data


def save_json(path, data):
    """Save JSON safely using an atomic file replacement."""

    path.parent.mkdir(parents=True, exist_ok=True)

    temporary_path = path.with_suffix(path.suffix + ".tmp")

    with open(temporary_path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)

    temporary_path.replace(path)


def load_or_download_metadata(name, endpoint):
    """Download metadata and save a local copy."""

    path = METADATA_DIR / f"{name}.json"

    print(f"Downloading metadata: {name}")

    data = get_json(f"{BASE_URL}/{endpoint}?format=json")

    save_json(path, data)

    print(f"  Retrieved {len(data):,} records")

    return data


# ============================================================
# GENERAL HELPERS
# ============================================================

def chunks(items, size=MAX_SELECTIONS):
    """Split a list into API-compatible groups."""

    for i in range(0, len(items), size):
        yield items[i:i + size]


def normalize(value):
    """Normalize station and metadata names for matching."""

    if value is None:
        return ""

    return re.sub(r"\s+", " ", str(value).strip()).upper()


def match_metadata_id(value, records, id_field, text_fields):
    """Find an exact metadata match for a returned observation field."""

    target = normalize(value)

    if not target:
        return None

    matches = []

    for record in records:
        for field in text_fields:
            if normalize(record.get(field)) == target:
                matches.append(record[id_field])
                break

    matches = list(dict.fromkeys(matches))

    if len(matches) == 1:
        return matches[0]

    return None


# ============================================================
# DOWNLOAD METADATA
# ============================================================

def download_metadata():

    print("\nDownloading DataHub metadata...\n")

    streams = load_or_download_metadata(
        "data_streams",
        "MetaDataAttribute/DataStream"
    )

    programs = load_or_download_metadata(
        "programs",
        "MetaDataAttribute/WaterQualityPrograms"
    )

    projects = load_or_download_metadata(
        "projects",
        "MetaDataAttribute/WaterQualityProjects"
    )

    substances = load_or_download_metadata(
        "substances",
        "MetaDataAttribute/Substance"
    )

    segments = load_or_download_metadata(
        "bay_segments",
        "GeographicAttribute/CBSeg2003"
    )

    stations = load_or_download_metadata(
        "all_stations",
        "GeographicAttribute/Station"
    )

    if not programs or not projects or not substances:
        raise RuntimeError(
            "One or more metadata endpoints returned no records. "
            "Stopping rather than making incomplete queries."
        )

    print("\nData stream metadata:")
    for item in streams:
        print(" ", item)

    print("\nAvailable programs:", len(programs))
    print("Available projects:", len(projects))
    print("Available substances:", len(substances))
    print("Available Chesapeake Bay segments:", len(segments))
    print("All station metadata records:", len(stations))

    return {
        "streams": streams,
        "programs": programs,
        "projects": projects,
        "substances": substances,
        "segments": segments,
        "stations": stations,
    }


# ============================================================
# IDENTIFY CHESAPEAKE BAY STATIONS
# ============================================================

def get_bay_stations(metadata):

    print("\nIdentifying Chesapeake Bay stations...")

    segment_ids = [
        str(x["cbSegment2003Id"])
        for x in metadata["segments"]
    ]

    if not segment_ids:
        raise RuntimeError("No CBSeg2003 segment IDs were returned.")

    station_locations = []

    # This endpoint returns station locations within the selected
    # Chesapeake Bay segments.
    for segment_batch in chunks(segment_ids):

        segment_string = ",".join(segment_batch)

        url = (
            f"{BASE_URL}/WaterQuality/Station/"
            f"CBSeg2003/{segment_string}?format=json"
        )

        results = get_json(url)

        station_locations.extend(results)

        print(
            f"  Retrieved {len(results):,} station locations "
            f"for {len(segment_batch)} segments"
        )

    # Build a mapping from stationName to stationId.
    station_lookup = {}

    for station in metadata["stations"]:

        name = normalize(station.get("stationName"))

        if not name:
            continue

        station_lookup.setdefault(name, []).append(
            station["stationId"]
        )

    bay_station_names = {
        normalize(x.get("station"))
        for x in station_locations
        if x.get("station")
    }

    station_ids = []
    unmatched = []
    ambiguous = []

    for name in sorted(bay_station_names):

        matches = station_lookup.get(name, [])

        if len(matches) == 1:
            station_ids.append(str(matches[0]))

        elif len(matches) == 0:
            unmatched.append(name)

        else:
            ambiguous.append({
                "station": name,
                "station_ids": matches
            })

    station_ids = sorted(set(station_ids), key=int)

    # Save the station matching results for inspection.
    save_json(
        METADATA_DIR / "bay_station_locations.json",
        station_locations
    )

    save_json(
        METADATA_DIR / "bay_station_ids.json",
        station_ids
    )

    save_json(
        METADATA_DIR / "unmatched_stations.json",
        unmatched
    )

    save_json(
        METADATA_DIR / "ambiguous_stations.json",
        ambiguous
    )

    print("\nStation matching results:")
    print("  Bay station names:", len(bay_station_names))
    print("  Matched station IDs:", len(station_ids))
    print("  Unmatched names:", len(unmatched))
    print("  Ambiguous names:", len(ambiguous))

    if unmatched or ambiguous:
        raise RuntimeError(
            "Some Bay station names could not be matched uniquely "
            "to stationId values. Inspect unmatched_stations.json "
            "and ambiguous_stations.json before proceeding."
        )

    if not station_ids:
        raise RuntimeError("No Chesapeake Bay station IDs were found.")

    return station_ids


# ============================================================
# FILTER SUBSTANCES
# ============================================================

def select_substances(substances):

    if not SUBSTANCE_FILTER.strip():
        return substances

    search = normalize(SUBSTANCE_FILTER)

    selected = []

    for substance in substances:

        searchable = " ".join([
            str(substance.get("substanceIdentificationName", "")),
            str(substance.get("substanceIdentificationDescription", "")),
        ])

        if search in normalize(searchable):
            selected.append(substance)

    if not selected:
        raise RuntimeError(
            f"No substances matched: {SUBSTANCE_FILTER}"
        )

    print(
        f"\nSelected {len(selected)} substances matching "
        f"'{SUBSTANCE_FILTER}'"
    )

    return selected


# ============================================================
# BUILD WATER QUALITY REQUEST
# ============================================================

def water_quality_url(
    start,
    end,
    stream,
    program_ids,
    project_ids,
    station_ids,
    substance_ids
):

    return (
        f"{BASE_URL}/WaterQuality/"
        f"{start}/{end}/"
        f"{stream}/"
        f"{','.join(map(str, program_ids))}/"
        f"{','.join(map(str, project_ids))}/"
        f"{GEO_TYPE}/"
        f"{','.join(map(str, station_ids))}/"
        f"{','.join(map(str, substance_ids))}"
        f"?format=json"
    )


# ============================================================
# PREFLIGHT: FIND A REAL OBSERVATION
# ============================================================

def find_valid_minimal_query(metadata, station_ids, substances):

    print("\n" + "=" * 65)
    print("PREFLIGHT: FINDING A REAL WATER QUALITY OBSERVATION")
    print("=" * 65)

    programs = metadata["programs"]
    projects = metadata["projects"]

    program_ids = [x["programId"] for x in programs]
    project_ids = [x["projectId"] for x in projects]
    substance_ids = [x["substanceId"] for x in substances]

    # The probe uses a 10-year window and one station at a time.
    # It searches the available program/project/substance selections
    # in batches of no more than 60.
    start, end = "01-01-2016", "12-31-2025"

    program_batches = list(chunks(program_ids))
    project_batches = list(chunks(project_ids))
    substance_batches = list(chunks(substance_ids))

    stations_to_try = station_ids[:PROBE_STATIONS_LIMIT]

    probe_path = OUTPUT_DIR / "successful_probe.json"

    for station_id in stations_to_try:

        print(f"\nTesting station ID {station_id}...")

        for prog_batch, proj_batch, sub_batch in product(
            program_batches,
            project_batches,
            substance_batches
        ):

            url = water_quality_url(
                start,
                end,
                STREAM,
                prog_batch,
                proj_batch,
                [station_id],
                sub_batch
            )

            results = get_json(url)

            if results:

                print(
                    f"  Found {len(results):,} observations "
                    f"at station ID {station_id}"
                )

                save_json(probe_path, results)

                # Find the metadata IDs corresponding to the first
                # returned observation.
                row = results[0]

                program_id = match_metadata_id(
                    row.get("program"),
                    programs,
                    "programId",
                    ["programName", "programIdentifier"]
                )

                project_id = match_metadata_id(
                    row.get("project"),
                    projects,
                    "projectId",
                    ["projectName", "projectIdentifier"]
                )

                substance_id = match_metadata_id(
                    row.get("parameter"),
                    substances,
                    "substanceId",
                    [
                        "substanceIdentificationName",
                        "substanceIdentificationDescription",
                    ]
                )

                print("\nExample observation:")
                print(json.dumps(row, indent=2))

                if None in (program_id, project_id, substance_id):
                    raise RuntimeError(
                        "The API returned observations, but the "
                        "program/project/substance values could not "
                        "be matched uniquely to metadata IDs. "
                        "The returned rows are saved in "
                        "successful_probe.json. Inspect that file "
                        "before proceeding."
                    )

                # Now verify a genuinely small request:
                # one station, one program, one project, one substance.
                # Test stream 0 and 1 individually, then the combined
                # stream if neither individual request returns data.
                valid_stream = None

                for stream in ["0", "1", "0,1"]:

                    test_url = water_quality_url(
                        start,
                        end,
                        stream,
                        [program_id],
                        [project_id],
                        [station_id],
                        [substance_id]
                    )

                    test_results = get_json(test_url)

                    if test_results:
                        valid_stream = stream
                        save_json(
                            OUTPUT_DIR / "minimal_query_test.json",
                            test_results
                        )
                        break

                if valid_stream is None:
                    raise RuntimeError(
                        "The broad probe returned observations, "
                        "but the single-ID query did not. "
                        "Inspect successful_probe.json."
                    )

                print("\nMINIMAL QUERY VERIFIED")
                print("  Station ID:", station_id)
                print("  Program ID:", program_id)
                print("  Project ID:", project_id)
                print("  Substance ID:", substance_id)
                print("  Stream:", valid_stream)
                print("  Observations:", len(test_results))

                print(
                    "\nThe smallest successful request is saved in "
                    "minimal_query_test.json."
                )

                return True

    raise RuntimeError(
        "No observations were found in the first "
        f"{len(stations_to_try)} stations tested. "
        "This does NOT prove that the API has no observations. "
        "Increase PROBE_STATIONS_LIMIT or choose a station known "
        "to have measurements."
    )


# ============================================================
# FULL DOWNLOAD
# ============================================================

def download_all_observations(metadata, station_ids, substances):

    programs = [
        x["programId"] for x in metadata["programs"]
    ]

    projects = [
        x["projectId"] for x in metadata["projects"]
    ]

    substance_ids = [
        x["substanceId"] for x in substances
    ]

    station_batches = list(chunks(station_ids))
    program_batches = list(chunks(programs))
    project_batches = list(chunks(projects))
    substance_batches = list(chunks(substance_ids))

    total_requests = (
        len(DATE_WINDOWS)
        * len(station_batches)
        * len(program_batches)
        * len(project_batches)
        * len(substance_batches)
    )

    print("\n" + "=" * 65)
    print("STARTING FULL DOWNLOAD")
    print("=" * 65)

    print("Stations:", len(station_ids))
    print("Programs:", len(programs))
    print("Projects:", len(projects))
    print("Substances:", len(substance_ids))
    print("Date windows:", len(DATE_WINDOWS))
    print("Station batches:", len(station_batches))
    print("Program batches:", len(program_batches))
    print("Project batches:", len(project_batches))
    print("Substance batches:", len(substance_batches))
    print("Maximum possible requests:", total_requests)

    completed = 0
    failed = 0
    total_records = 0

    for (start, end) in DATE_WINDOWS:

        window_name = (
            start.replace("-", "")
            + "_"
            + end.replace("-", "")
        )

        window_dir = RAW_DIR / window_name
        window_dir.mkdir(parents=True, exist_ok=True)

        for prog_batch, proj_batch, station_batch, sub_batch in product(
            program_batches,
            project_batches,
            station_batches,
            substance_batches
        ):

            url = water_quality_url(
                start,
                end,
                STREAM,
                prog_batch,
                proj_batch,
                station_batch,
                sub_batch
            )

            request_hash = hashlib.sha256(
                url.encode("utf-8")
            ).hexdigest()[:20]

            output_path = window_dir / f"{request_hash}.json"

            # A valid saved JSON list, including an empty list, is
            # a completed request. This makes reruns resumable.
            if output_path.exists():

                try:
                    with open(output_path, encoding="utf-8") as f:
                        cached = json.load(f)

                    if isinstance(cached, list):
                        completed += 1
                        total_records += len(cached)
                        continue

                except (json.JSONDecodeError, OSError):
                    pass

            try:

                results = get_json(url)

                save_json(output_path, results)

                completed += 1
                total_records += len(results)

                print(
                    f"[{completed}/{total_requests}] "
                    f"{window_name}: "
                    f"{len(results):,} observations"
                )

                # Small pause to avoid hammering the API.
                time.sleep(0.15)

            except Exception as error:

                failed += 1

                print("\nREQUEST FAILED")
                print("URL:", url)
                print("Error:", error)

                # Do not create a checkpoint for failed requests.
                # They can be retried on the next run.

    print("\nDownload requests completed:", completed)
    print("Failed requests:", failed)
    print("Total observations retrieved:", f"{total_records:,}")

    if failed:
        print(
            "\nSome requests failed. Rerun the script to retry them. "
            "Successful requests are already saved and will be skipped."
        )

    return failed


# ============================================================
# COMBINE RAW JSON INTO ONE CSV
# ============================================================

def combine_json_to_csv(station_metadata):

    print("\nCombining downloaded JSON files into CSV...")

    # BaseWaterQuality fields from the uploaded OpenAPI schema.
    fieldnames = [
        "station",
        "stationId",
        "fieldActivityId",
        "cruise",
        "program",
        "project",
        "dataCollector",
        "dataProvider",
        "latitude",
        "longitude",
        "SampleDate",
        "SampleTime",
        "totalDepthM",
        "upperPycnoclineDepthM",
        "lowerPycnoclineDepthM",
        "sampleDepthM",
        "layer",
        "sampleType",
        "sampleReplicate",
        "parameter",
        "qualifier",
        "measureValue",
        "measureUnit",
        "method",
        "lab",
        "problem",
        "precisionPC",
        "biasPC",
        "details",
        "tierLevel",
    ]

    station_lookup = {
        normalize(x.get("stationName")): x["stationId"]
        for x in station_metadata
        if x.get("stationName")
    }

    output_csv = OUTPUT_DIR / "water_quality_2000_2025.csv"

    files = sorted(RAW_DIR.rglob("*.json"))

    total_rows = 0

    with open(
        output_csv,
        "w",
        newline="",
        encoding="utf-8-sig"
    ) as f:

        writer = csv.DictWriter(
            f,
            fieldnames=fieldnames,
            extrasaction="ignore"
        )

        writer.writeheader()

        for i, path in enumerate(files, start=1):

            try:
                with open(path, encoding="utf-8") as jf:
                    records = json.load(jf)

                if not isinstance(records, list):
                    continue

                for record in records:

                    row = dict(record)

                    row["stationId"] = station_lookup.get(
                        normalize(row.get("station"))
                    )

                    writer.writerow(row)
                    total_rows += 1

            except (json.JSONDecodeError, OSError) as error:
                print(f"Could not read {path}: {error}")

            if i % 100 == 0:
                print(
                    f"  Processed {i:,}/{len(files):,} files"
                )

    print("\nCSV created:")
    print(output_csv.resolve())
    print("Total rows:", f"{total_rows:,}")


# ============================================================
# MAIN
# ============================================================

def main():

    metadata = download_metadata()

    station_ids = get_bay_stations(metadata)

    substances = select_substances(
        metadata["substances"]
    )

    # Always verify that the API returns actual observations
    # before launching the full download.
    find_valid_minimal_query(
        metadata,
        station_ids,
        substances
    )

    if not RUN_FULL_DOWNLOAD:

        print("\n" + "=" * 65)
        print("PREFLIGHT SUCCESSFUL")
        print("=" * 65)

        print(
            "A minimal query returned real observations. "
            "Set RUN_FULL_DOWNLOAD = True near the top of this "
            "script to download the full 2000-2025 dataset."
        )

        return

    failed = download_all_observations(
        metadata,
        station_ids,
        substances
    )

    combine_json_to_csv(metadata["stations"])

    if failed:
        print(
            "\nThe CSV was created, but some requests failed. "
            "Rerun the script to retry the missing requests."
        )


if __name__ == "__main__":
    main()
