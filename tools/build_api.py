# Build a multi-day static API from headerless CSVs via GitHub Pages.
# We only read: data/*userRecord.NAVIGATION.csv  (NO .TOTAL files)
# Each row: time,userID,username,county,screen,latency
# Outputs under docs/api/:
#   /api/summary.json
#   /api/byCounty/{county}.json
#   /api/days.json
#   /api/days/{day}/summary.json
#   /api/days/{day}/byCounty/{county}.json
#   /api/trends/summary_by_day.json

import csv, json, pathlib, re
from collections import defaultdict
from datetime import datetime

DATA_DIR = pathlib.Path("data")
OUT_ROOT = pathlib.Path("docs/api")
TOP_N_PER_COUNTY = 200  # cap per-county lists to keep JSON small

def _strip_hash(s: str) -> str:
    return s.replace("#", "") if isinstance(s, str) else s

def _to_latency(v):
    if v is None: return None
    s = str(v).strip().replace(",", "")
    if s == "" or s.upper() in {"NA", "NULL"}: return None
    try:
        return int(float(s))   # handles "3534" and "3534.0"
    except ValueError:
        return None

def _parse_day_from_name(name: str):
    """
    Accept YYMMDD or YYYYMMDD at the start of the filename; return 'YYYY-MM-DD'.
    Example: 250407.userRecord.NAVIGATION.csv -> '2025-04-07'
    """
    m = re.match(r"^(\d{6,8})", name)
    if not m:
        return None
    token = m.group(1)
    if len(token) == 6:
        dt = datetime.strptime("20" + token, "%Y%m%d")  # assume 2000s
    else:
        dt = datetime.strptime(token, "%Y%m%d")
    return dt.strftime("%Y-%m-%d")

def read_headerless_nav(path: pathlib.Path):
    """
    Expect rows: time,userID,username,county,screen,latency (exactly).
    If a file accidentally has a header, the 'latency' row is skipped automatically.
    Extra trailing columns (if any) are ignored.
    """
    rows = []
    with open(path, newline="", encoding="utf-8-sig") as f:
        r = csv.reader(f)
        for cols in r:
            if not cols or len(cols) < 6:
                continue
            time, user_id, username, county, screen, latency_raw = cols[:6]
            latency = _to_latency(latency_raw)
            if latency is None:
                # skips a header line like: time,userID,username,county,screen,latency
                continue
            rows.append({
                "time": time.strip(),
                "userID": _strip_hash(str(user_id).strip()),
                "Username": str(username).strip(),
                "County": str(county).strip().upper(),
                "Screen": str(screen).strip(),
                "Latency": latency,
            })
    return rows

def percentile(values, p: float):
    if not values: return 0
    s = sorted(values)
    i = int(p * (len(s) - 1))
    return s[i]

def summarize(rows):
    lat = [r["Latency"] for r in rows]
    by_cnty_rows = defaultdict(list)
    for r in rows:
        by_cnty_rows[r["County"]].append(r)
    byCountyAvg = {c: (sum(x["Latency"] for x in arr) / len(arr)) for c, arr in by_cnty_rows.items()}
    summary = {
        "count": len(rows),
        "mean": (sum(lat) / len(lat)) if lat else 0,
        "p50": percentile(lat, 0.50),
        "p95": percentile(lat, 0.95),
        "p99": percentile(lat, 0.99),
        "byCountyAvg": byCountyAvg,
    }
    return summary, by_cnty_rows

def write_json(path: pathlib.Path, obj):
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(obj, f, indent=2)

def build():
    OUT_ROOT.mkdir(parents=True, exist_ok=True)

    # ONLY read non-TOTAL NAVIGATION files
    files = sorted(DATA_DIR.glob("*userRecord.NAVIGATION.csv"))

    days = []
    all_rows = []

    for p in files:
        day = _parse_day_from_name(p.name)
        if not day:
            continue
        days.append(day)

        rows = read_headerless_nav(p)

        # Per-day summary
        day_summary, by_cnty = summarize(rows)
        write_json(OUT_ROOT / "days" / day / "summary.json", day_summary)

        # Per-day per-county rows (top N by latency desc)
        for c, arr in by_cnty.items():
            arr_sorted = sorted(arr, key=lambda r: r["Latency"], reverse=True)[:TOP_N_PER_COUNTY]
            write_json(OUT_ROOT / "days" / day / "byCounty" / f"{c or 'UNKNOWN'}.json", arr_sorted)

        all_rows.extend(rows)

    # Index of days
    write_json(OUT_ROOT / "days.json", {"days": sorted(days)})

    # All-days combined
    if all_rows:
        all_summary, all_by_cnty = summarize(all_rows)
        write_json(OUT_ROOT / "summary.json", all_summary)
        for c, arr in all_by_cnty.items():
            arr_sorted = sorted(arr, key=lambda r: r["Latency"], reverse=True)[:TOP_N_PER_COUNTY]
            write_json(OUT_ROOT / "byCounty" / f"{c or 'UNKNOWN'}.json", arr_sorted)

        # Trends (summary per day)
        trend = []
        for d in sorted(days):
            dsum = json.load(open(OUT_ROOT / "days" / d / "summary.json", encoding="utf-8"))
            trend.append({"day": d, **{k: dsum[k] for k in ["count","mean","p50","p95","p99"]}})
        write_json(OUT_ROOT / "trends" / "summary_by_day.json", trend)

if __name__ == "__main__":
    build()
